"""Agent invocations: real LLM agents (primary) and deterministic stubs (dry-run).

Every role runs through one entry point:

    run_role(cfg, role, ctx, instruction) -> dict  # PhaseResult-ish

In live mode the role is executed by an LLM with a ReAct tool loop
(`react_loop`): the model emits strict JSON tool calls, the runtime executes
them inside the sandbox, results are fed back, bounded by max tool
iterations. Malformed output gets ONE re-prompt, then a loud failure.

In dry-run mode (CIPHER_DRY_RUN=1 or no API key) deterministic stub agents
use the SAME tool belt (writes, exec, memory) so the pipeline, spawn tree,
and verifier are genuinely exercised — only the "thinking" is stubbed.

No API keys are invented or required here; live mode fails loudly via
config.require_api_key inside src/llm.py.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from .config import Config
from .llm import LLMError, chat_complete
from .roles import (
    build_specialist_prompt,
    build_system_prompt,
    get_role,
)
from .tools import ToolBelt, ToolDenied, ToolError


class AgentError(Exception):
    """A role failed: malformed output, tool-loop exhaustion, or LLM error."""


# ---------------------------------------------------------------------------
# ReAct tool loop (live agents)
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """Pull a JSON object out of model output (tolerates code fences)."""
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    start = t.find("{")
    end = t.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise AgentError(f"no JSON object found in model output: {text[:200]!r}")
    try:
        obj = json.loads(t[start : end + 1])
    except json.JSONDecodeError as e:
        raise AgentError(f"model output is not valid JSON: {e}; raw: {text[:200]!r}")
    if not isinstance(obj, dict):
        raise AgentError("model output JSON must be an object")
    return obj


def react_loop(
    cfg: Config,
    belt: ToolBelt,
    system: str,
    user_message: str,
    contract_keys: list[str],
    log,
) -> dict:
    """Run the ReAct loop until the model emits {"type": "final", ...}."""
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_message},
    ]
    malformed_retries = 1
    for it in range(cfg.max_tool_iterations + 1):
        try:
            raw = chat_complete(cfg, messages)
        except LLMError as e:
            raise AgentError(f"LLM call failed: {e}")
        try:
            msg = _extract_json(raw)
        except AgentError as e:
            if malformed_retries > 0:
                malformed_retries -= 1
                messages.append({"role": "assistant", "content": raw})
                messages.append({
                    "role": "user",
                    "content": f"Your last output was malformed: {e}. Reply with ONE strict JSON object only.",
                })
                log(f"[{belt.role}] malformed output, re-prompting")
                continue
            raise
        mtype = msg.get("type")
        if mtype == "tool_call":
            tool = msg.get("tool")
            args = msg.get("args", {})
            log(f"[{belt.role}] tool_call {tool} {str(args)[:160]}")
            try:
                result = belt.call(tool, args)
                reply = {"tool": tool, "result": result}
            except (ToolDenied, ToolError) as e:
                reply = {"tool": tool, "error": f"{type(e).__name__}: {e}"}
                log(f"[{belt.role}] tool {tool} denied/failed: {e}")
            messages.append({"role": "assistant", "content": json.dumps(msg)})
            messages.append({"role": "user", "content": json.dumps(reply)})
            continue
        if mtype == "final":
            result = msg.get("result")
            if not isinstance(result, dict):
                raise AgentError("final result must be an object")
            missing = [k for k in contract_keys if k not in result]
            if missing:
                if malformed_retries > 0:
                    malformed_retries -= 1
                    messages.append({"role": "assistant", "content": raw})
                    messages.append({
                        "role": "user",
                        "content": f"Your final result is missing required keys {missing}. "
                                   f"Reply with ONE strict JSON final object containing them.",
                    })
                    log(f"[{belt.role}] final missing keys {missing}, re-prompting")
                    continue
                raise AgentError(f"final result missing required keys: {missing}")
            return result
        # Unknown type: one re-prompt, then fail.
        if malformed_retries > 0:
            malformed_retries -= 1
            messages.append({"role": "assistant", "content": raw})
            messages.append({
                "role": "user",
                "content": 'Unknown message type. Use {"type": "tool_call", ...} or {"type": "final", ...} only.',
            })
            continue
        raise AgentError(f"unknown message type: {mtype!r}")
    raise AgentError("tool iteration budget exhausted without a final result")


# ---------------------------------------------------------------------------
# Run context (provided by the loop)
# ---------------------------------------------------------------------------

@dataclass
class RunContext:
    cfg: Config
    run_id: str
    task: dict
    memory: Any          # MemoryStore
    make_belt: Any       # (role, agent_id, depth, tool_budget) -> ToolBelt
    log: Any             # (str) -> None


# ---------------------------------------------------------------------------
# Live role entry point
# ---------------------------------------------------------------------------

def run_role_live(cfg: Config, role: str, ctx: RunContext, instruction: str) -> dict:
    belt = ctx.make_belt(role, agent_id="root", depth=0, tool_budget=cfg.max_tool_iterations)
    system = build_system_prompt(role, belt)
    contract = get_role(role).get("response_contract", {})
    user_message = (
        f"## Task\nGoal: {ctx.task['goal']}\n\n"
        f"Context: {ctx.task.get('context', '')}\n\n"
        f"Constraints: {json.dumps(ctx.task.get('constraints', []))}\n\n"
        f"## Your instruction for this phase\n{instruction}\n\n"
        f"## Shared memory so far\n{ctx.memory.context_summary(agent_id='root')}\n"
    )
    result = react_loop(cfg, belt, system, user_message, list(contract.keys()), ctx.log)
    belt.memory_append({"claim": f"{role} completed phase", "evidence": json.dumps(result)[:2000]})
    return result


# ---------------------------------------------------------------------------
# Specialist (spawned sub-agent) entry point — live
# ---------------------------------------------------------------------------

def run_specialist_live(
    cfg: Config,
    *,
    specialist: str,
    goal: str,
    context: str,
    parent_role: str,
    belt: ToolBelt,   # already scoped: tool subset of parent, own budget
    log,
) -> dict:
    system = build_specialist_prompt(
        specialist=specialist,
        goal=goal,
        context=context,
        parent_role=parent_role,
        belt=belt,
        depth=belt.depth,
        max_depth=cfg.max_spawn_depth,
    )
    user_message = (
        f"You are the specialist '{specialist}', spawned by {parent_role}.\n"
        f"Your narrow goal: {goal}\n\n"
        f"Parent-provided context:\n{context or '(none)'}\n\n"
        "Use your tools, then return your final result."
    )
    return react_loop(cfg, belt, system, user_message,
                      ["summary", "outputs", "evidence"], log)


# ---------------------------------------------------------------------------
# Dry-run stubs — deterministic, use the real tool belt
# ---------------------------------------------------------------------------

def _stub_ok(**kw: Any) -> dict:
    return {"status": "ok", **kw}


def stub_coordinator(ctx: RunContext, instruction: str) -> dict:
    """Stub coordinator: writes a plan, then demonstrates spawning by
    creating a 'test-writer' specialist for the example task."""
    belt = ctx.make_belt("coordinator", agent_id="root", depth=0,
                         tool_budget=ctx.cfg.max_tool_iterations)
    plan = {
        "strategy": "Build the artifact, spawn a test-writer specialist for the test, then verify.",
        "steps": ["research", "spawn test-writer", "build", "analyze", "critique", "verify"],
        "budget": ctx.task.get("budget", {}),
    }
    ctx.memory.write_plan(plan)
    belt.memory_append({"claim": "plan created", "evidence": "memory plan.json"})
    ctx.log("[coordinator] plan written; spawning test-writer specialist")

    # Demonstrate the spawn tree: coordinator delegates test authorship.
    spawn_result = belt.call("spawn_subagent", {
        "specialist": "test-writer",
        "goal": (
            "Write a test file at tests/test_hello_cipher.py that runs "
            "artifacts/hello.py as a subprocess and asserts its stdout contains "
            "'Hello, Cipher!'. Use only the tools you were given."
        ),
        "tools": ["write_file", "read_file", "run_cmd", "memory_append", "memory_read"],
        "max_tool_iterations": 6,
        "context": (
            f"Task goal: {ctx.task['goal']}. "
            "The builder will create artifacts/hello.py printing 'Hello, Cipher!'. "
            "Your test must be runnable with: python3 -m pytest tests/test_hello_cipher.py -q "
            "or: python3 tests/test_hello_cipher.py"
        ),
    })
    belt.memory_append({
        "claim": "spawned test-writer specialist",
        "evidence": json.dumps(spawn_result)[:1500],
    })
    return _stub_ok(plan=plan, spawn=spawn_result.get("result", {}))


def stub_research(ctx: RunContext, instruction: str) -> dict:
    belt = ctx.make_belt("research", agent_id="root", depth=0,
                         tool_budget=ctx.cfg.max_tool_iterations)
    listing = belt.call("list_dir", {"path": "."})
    belt.memory_append({
        "claim": "repo layout inspected",
        "evidence": f"top-level entries: {listing['entries'][:12]}",
    })
    return _stub_ok(findings=["repo layout inspected"], summary="context gathered")


def stub_builder(ctx: RunContext, instruction: str) -> dict:
    belt = ctx.make_belt("builder", agent_id="root", depth=0,
                         tool_budget=ctx.cfg.max_tool_iterations)
    script = '#!/usr/bin/env python3\n"""Hello program built by the Cipher builder agent."""\n\n\ndef main() -> None:\n    print("Hello, Cipher!")\n\n\nif __name__ == "__main__":\n    main()\n'
    belt.call("write_file", {"path": "artifacts/hello.py", "content": script})
    belt.memory_append({"claim": "artifacts/hello.py written", "evidence": "file exists, prints 'Hello, Cipher!'"})
    return _stub_ok(artifacts_written=["artifacts/hello.py"], changes="created hello.py")


def stub_analyst(ctx: RunContext, instruction: str) -> dict:
    belt = ctx.make_belt("analyst", agent_id="root", depth=0,
                         tool_budget=ctx.cfg.max_tool_iterations)
    run = belt.call("run_cmd", {"argv": ["python3", "artifacts/hello.py"]})
    out = run["stdout"].strip()
    belt.memory_append({"claim": "hello.py executes", "evidence": f"stdout={out!r} exit={run['exit_code']}"})
    return _stub_ok(observations=[f"stdout={out!r}"], test_results=["manual run ok"])


def stub_critic(ctx: RunContext, instruction: str) -> dict:
    belt = ctx.make_belt("critic", agent_id="root", depth=0,
                         tool_budget=ctx.cfg.max_tool_iterations)
    findings = belt.call("memory_read", {})["findings"]
    weak = [f for f in findings if not f.get("evidence")]
    verdict = "reject" if weak else "accept"
    objections = [
        {"target": f.get("id"), "reason": "claim without evidence",
         "evidence_demanded": "file path or command output"}
        for f in weak
    ]
    belt.memory_append({"claim": f"critic verdict: {verdict}",
                        "evidence": f"{len(findings)} findings reviewed, {len(weak)} weak"})
    return _stub_ok(verdict=verdict, objections=objections)


def stub_verifier(ctx: RunContext, instruction: str) -> dict:
    """Stub verifier: evaluates every success_criterion with the deterministic
    evidence checker (the same check the loop re-runs independently)."""
    belt = ctx.make_belt("verifier", agent_id="root", depth=0,
                         tool_budget=ctx.cfg.max_tool_iterations)
    results = []
    for crit in ctx.task.get("success_criteria", []):
        res = belt.call("check_evidence", {"criterion": crit})
        results.append({
            "criterion_id": crit.get("id"),
            "passed": res["passed"],
            "evidence": res["detail"],
        })
    verdict = "PASS" if all(r["passed"] for r in results) else "FAIL"
    reasons = [r["evidence"] for r in results if not r["passed"]]
    belt.memory_append({"claim": f"verifier verdict: {verdict}",
                        "evidence": json.dumps(results)[:2000]})
    return _stub_ok(results=results, verdict=verdict, reasons=reasons)


def stub_specialist(ctx: RunContext, belt: ToolBelt, specialist: str, goal: str) -> dict:
    """Dry-run specialist. The test-writer writes a real test via the belt."""
    ctx.log(f"[specialist:{specialist}] dry-run executing goal")
    if specialist == "test-writer":
        test_code = '''"""Test written by the Cipher test-writer specialist (spawned sub-agent)."""
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "artifacts" / "hello.py"


def test_hello_script_prints_greeting():
    assert SCRIPT.is_file(), f"missing artifact: {SCRIPT}"
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        capture_output=True, text=True, timeout=30, cwd=str(REPO),
    )
    assert proc.returncode == 0, f"non-zero exit: {proc.stderr[-500:]}"
    assert "Hello, Cipher!" in proc.stdout, f"unexpected stdout: {proc.stdout!r}"


if __name__ == "__main__":
    test_hello_script_prints_greeting()
    print("test_hello_cipher: PASS")
'''
        belt.call("write_file", {"path": "tests/test_hello_cipher.py", "content": test_code})
        belt.memory_append({
            "claim": "test-writer wrote tests/test_hello_cipher.py",
            "evidence": "file exists; asserts subprocess stdout contains 'Hello, Cipher!'",
        })
        return {"summary": "wrote tests/test_hello_cipher.py",
                "outputs": ["tests/test_hello_cipher.py"],
                "evidence": "test asserts artifacts/hello.py stdout contains 'Hello, Cipher!'"}
    # Generic fallback specialist: records its goal as addressed.
    belt.memory_append({"claim": f"specialist {specialist} completed",
                        "evidence": f"goal was: {goal[:200]}"})
    return {"summary": f"dry-run specialist {specialist} completed",
            "outputs": [], "evidence": "dry-run stub"}


STUBS = {
    "coordinator": stub_coordinator,
    "research": stub_research,
    "builder": stub_builder,
    "analyst": stub_analyst,
    "critic": stub_critic,
    "verifier": stub_verifier,
}


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

def run_role(cfg: Config, role: str, ctx: RunContext, instruction: str) -> dict:
    if cfg.dry_run:
        stub = STUBS.get(role)
        if stub is None:
            raise AgentError(f"no dry-run stub for role {role!r}")
        ctx.log(f"[{role}] dry-run stub")
        return stub(ctx, instruction)
    return run_role_live(cfg, role, ctx, instruction)
