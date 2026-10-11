"""Cipher coordinator loop.

Pipeline:
    PLAN -> RESEARCH -> BUILD -> ANALYZE -> CRITIQUE -> VERIFY -> DONE
                                                  VERIFY --FAIL--> REVISE
    REVISE -> (retry: BUILD | backtrack: RESEARCH | replan: RESEARCH | abort: DONE)

Bounded: max_retries VERIFY->REVISE cycles and max_steps total phase
executions. The loop always terminates.

Spawning: any role with the `spawn_subagent` tool may spawn specialists.
The runtime enforces:
  - max spawn depth (config.max_spawn_depth),
  - max total sub-agents per run (config.max_subagents_per_run),
  - no permission escalation (child tools ⊆ parent tools),
  - spawn-cycle detection (a (specialist, goal) pair may not repeat in one
    ancestor chain),
  - child tool budget carved out of the parent's remaining budget.

The spawn tree is recorded in memory/<run-id>/spawn_tree.json and in the
run log. Sub-agent findings are namespaced: memory/<run-id>/spawns/<id>/.

CLI:
    export CIPHER_API_KEY=...   # real-agent mode (default/primary path)
    python -m src.loop --goal "Write a fizzbuzz program to artifacts/fizzbuzz.py"
    python -m src.loop --task tasks/example-hello-task.json

    CIPHER_DRY_RUN=1 python -m src.loop --task tasks/example-hello-task.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .agents import AgentError, RunContext, run_role, run_specialist_live, stub_specialist
from .config import Config, load_config
from .memory import MemoryStore
from .roles import SAFETY_BOUNDARY, get_role
from .tasks import TaskError, load_task
from .tools import ToolBelt, ToolDenied, ToolError, check_criterion

REPO_ROOT = Path(__file__).resolve().parent.parent

PHASES = ["research", "build", "analyze", "critique", "verify"]
ROLE_FOR_PHASE = {
    "research": "research",
    "build": "builder",
    "analyze": "analyst",
    "critique": "critic",
    "verify": "verifier",
}


# ---------------------------------------------------------------------------
# Spawn registry
# ---------------------------------------------------------------------------

@dataclass
class SpawnRegistry:
    cfg: Config
    memory: MemoryStore
    log: Any = None
    count: int = 0

    def _ancestors(self, belt: ToolBelt) -> list[dict]:
        """Ancestor chain of the requesting belt, root-first."""
        chain: list[dict] = []
        node_id = belt.agent_id
        tree = {r["spawn_id"]: r for r in self.memory.read_spawn_tree()}
        seen = set()
        while node_id not in ("root", "", None) and node_id not in seen:
            seen.add(node_id)
            rec = tree.get(node_id)
            if not rec:
                break
            chain.append(rec)
            node_id = rec.get("parent_id")
        return list(reversed(chain))

    def handle(self, spec: dict, parent_belt: ToolBelt) -> dict:
        """Execute a spawn_subagent request. Returns a result dict for the parent."""
        specialist = str(spec.get("specialist", "")).strip()
        goal = str(spec.get("goal", "")).strip()
        if not specialist or not goal:
            raise ToolError("spawn_subagent needs 'specialist' and 'goal'")
        requested_tools = spec.get("tools") or []
        if not isinstance(requested_tools, list):
            raise ToolError("'tools' must be a list of tool names")

        # 1. Depth limit.
        child_depth = parent_belt.depth + 1
        if child_depth > self.cfg.max_spawn_depth:
            raise ToolDenied(
                f"spawn refused: depth {child_depth} exceeds max_spawn_depth={self.cfg.max_spawn_depth}"
            )
        # 2. Total sub-agent limit.
        if self.count >= self.cfg.max_subagents_per_run:
            raise ToolDenied(
                f"spawn refused: already at max_subagents_per_run={self.cfg.max_subagents_per_run}"
            )
        # 3. No permission escalation: child tools ⊆ parent tools.
        parent_tools = set(parent_belt.tools_allowed)
        illegal = [t for t in requested_tools if t not in parent_tools]
        if illegal:
            raise ToolDenied(f"spawn refused: tools {illegal} exceed parent's permissions")
        # 4. Cycle detection: same (specialist, goal) must not repeat in the
        #    ancestor chain (prevents A->B->A ping-pong).
        for anc in self._ancestors(parent_belt):
            if anc.get("specialist") == specialist and anc.get("goal") == goal:
                raise ToolDenied(
                    f"spawn refused: cycle detected — ({specialist!r}, goal) already in ancestor chain"
                )
        # 5. Carve the child's tool budget out of the parent's remaining budget.
        parent_remaining = max(0, parent_belt.tool_budget - parent_belt.tools_used)
        try:
            wanted = int(spec.get("max_tool_iterations", self.cfg.max_specialist_tool_iters))
        except (TypeError, ValueError):
            raise ToolError("'max_tool_iterations' must be an integer")
        child_budget = max(1, min(wanted, parent_remaining, self.cfg.max_specialist_tool_iters))
        parent_belt.tools_used += child_budget  # carve out up front

        spawn_id = f"s{self.count + 1:02d}-{uuid.uuid4().hex[:6]}"
        self.count += 1
        context = str(spec.get("context", ""))[:4000]

        record = {
            "spawn_id": spawn_id,
            "parent_id": parent_belt.agent_id,
            "parent_role": parent_belt.role,
            "specialist": specialist,
            "goal": goal,
            "depth": child_depth,
            "tools": sorted(set(requested_tools) & parent_tools),
            "tool_budget": child_budget,
            "status": "running",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self.memory.record_spawn(record)
        self._log(f"[spawn] {parent_belt.role}/{parent_belt.agent_id} -> "
                  f"{specialist}/{spawn_id} (depth {child_depth}, budget {child_budget})")

        child_belt = ToolBelt(
            cfg=self.cfg,
            sandbox_root=REPO_ROOT,
            memory=self.memory,
            run_id=parent_belt.run_id,
            role=f"specialist:{specialist}",
            agent_id=spawn_id,
            depth=child_depth,
            tools_allowed=record["tools"],
            spawn_handler=self.handle,  # children may spawn within the depth limit
            tool_budget=child_budget,
        )
        # Seed the child's namespaced memory with the parent-provided context.
        self.memory.append_finding(
            f"specialist:{specialist}",
            {"claim": "spawn context from parent",
             "evidence": context or "(no context provided)"},
            agent_id=spawn_id,
        )
        try:
            if self.cfg.dry_run:
                result = stub_specialist(_ctx_for(self, parent_belt), child_belt, specialist, goal)
            else:
                result = run_specialist_live(
                    self.cfg, specialist=specialist, goal=goal, context=context,
                    parent_role=parent_belt.role, belt=child_belt, log=self._log,
                )
            status = "completed"
        except Exception as e:  # noqa: BLE001 - record child failure, don't crash the run
            result = {"summary": f"child failed: {type(e).__name__}: {e}",
                      "outputs": [], "evidence": "child raised an exception"}
            status = "failed"
        self.memory.append_finding(
            f"specialist:{specialist}",
            {"claim": f"child {spawn_id} {status}: {result.get('summary', '')}",
             "evidence": json.dumps(result)[:2000]},
            agent_id=spawn_id,
        )
        self.memory.update_spawn(spawn_id, status=status,
                                 finished_at=time.strftime("%Y-%m-%dT%H:%M:%S"))
        self._log(f"[spawn] {spawn_id} {status}: {str(result.get('summary'))[:120]}")
        # The parent inspects / accepts / rejects / retries via memory + follow-ups.
        return {"ok": True, "spawn_id": spawn_id, "status": status, "result": result}

    def _log(self, msg: str) -> None:
        if self.log:
            self.log(msg)


def _ctx_for(registry: SpawnRegistry, belt: ToolBelt) -> RunContext:
    # Minimal context for dry-run specialists (they only need cfg + log).
    from .agents import RunContext as RC
    return RC(cfg=registry.cfg, run_id=belt.run_id, task={},
              memory=belt.memory, make_belt=None, log=registry._log)


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------

@dataclass
class RunResult:
    run_id: str
    verdict: str  # PASS | FAIL
    retries_used: int
    steps: int
    spawns: int
    evidence_path: str
    log_path: str


class Loop:
    def __init__(self, cfg: Config, task: dict, run_id: str | None = None) -> None:
        self.cfg = cfg
        self.task = task
        self.run_id = run_id or f"run-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
        self.memory = MemoryStore(REPO_ROOT, self.run_id)
        self.log_path = REPO_ROOT / cfg.logs_dir / f"{self.run_id}.log"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self._log_fh = open(self.log_path, "a", encoding="utf-8")
        self.registry = SpawnRegistry(cfg, self.memory, log=self.log)
        # If this run id already has a spawn tree (resumed run), continue counting.
        self.registry.count = len(self.memory.read_spawn_tree())
        self.retries_used = 0
        self.steps = 0

    # -- logging ---------------------------------------------------------
    def log(self, msg: str) -> None:
        line = f"{time.strftime('%H:%M:%S')} {msg}"
        print(line, flush=True)
        self._log_fh.write(line + "\n")
        self._log_fh.flush()

    def make_belt(self, role: str, agent_id: str = "root",
                  depth: int = 0, tool_budget: int | None = None) -> ToolBelt:
        tools_allowed = get_role(role).get("tools_allowed", [])
        spawn_handler = self.registry.handle if "spawn_subagent" in tools_allowed else None
        return ToolBelt(
            cfg=self.cfg,
            sandbox_root=REPO_ROOT,
            memory=self.memory,
            run_id=self.run_id,
            role=role,
            agent_id=agent_id,
            depth=depth,
            tools_allowed=list(tools_allowed),
            spawn_handler=spawn_handler,
            tool_budget=tool_budget,
        )

    def ctx(self) -> RunContext:
        return RunContext(cfg=self.cfg, run_id=self.run_id, task=self.task,
                          memory=self.memory, make_belt=self.make_belt, log=self.log)

    # -- evidence ----------------------------------------------------------
    def write_evidence(self, results: list[dict]) -> Path:
        path = REPO_ROOT / self.cfg.tests_dir / f"evidence-{self.run_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"run_id": self.run_id, "task_id": self.task.get("id"),
                       "results": results}, f, indent=2)
        return path

    def independent_check(self) -> tuple[bool, list[dict]]:
        """The loop re-runs every success criterion itself. A verifier PASS
        only stands if this independent check also passes."""
        results = []
        for crit in self.task.get("success_criteria", []):
            passed, detail = check_criterion(crit, REPO_ROOT)
            results.append({"criterion_id": crit.get("id"), "passed": passed, "detail": detail})
        return all(r["passed"] for r in results), results

    # -- main ---------------------------------------------------------------
    def run(self) -> RunResult:
        budget = self.task.get("budget", {})
        max_retries = int(budget.get("max_retries", self.cfg.default_max_retries))
        max_steps = int(budget.get("max_steps", self.cfg.default_max_steps))
        mode = "dry-run (stubs)" if self.cfg.dry_run else f"live ({self.cfg.model})"
        self.log(f"=== Cipher run {self.run_id} [{mode}] ===")
        self.log(f"goal: {self.task['goal']}")
        self.log(f"budget: max_retries={max_retries} max_steps={max_steps} "
                 f"max_spawn_depth={self.cfg.max_spawn_depth} "
                 f"max_subagents={self.cfg.max_subagents_per_run}")
        self.memory.write_state({"phase": "plan", "retries": 0, "run_id": self.run_id})

        ctx = self.ctx()
        # PLAN
        self.steps += 1
        plan_result = run_role(self.cfg, "coordinator", ctx,
                               "Create the plan for this goal. Spawn specialists where useful.")
        self.memory.write_state({"phase": "research", "retries": 0, "run_id": self.run_id})

        verdict = "FAIL"
        evidence_results: list[dict] = []
        phase_idx = 0
        backtrack_to = 0  # on backtrack, restart phases from here

        while True:
            if self.steps >= max_steps:
                self.log("max_steps exhausted -> FAIL")
                break
            phase = PHASES[phase_idx]
            role = ROLE_FOR_PHASE[phase]
            self.steps += 1
            self.log(f"--- phase {phase} (step {self.steps}) ---")
            self.memory.write_state({"phase": phase, "retries": self.retries_used,
                                     "run_id": self.run_id})
            try:
                result = run_role(self.cfg, role, ctx, f"Execute the {phase} phase.")
            except (AgentError, ToolDenied, ToolError) as e:
                self.log(f"[{role}] ERROR: {type(e).__name__}: {e}")
                result = {"status": "error", "error": str(e)}

            if phase == "critique":
                v = result.get("verdict", "accept")
                self.log(f"[critic] verdict: {v} ({len(result.get('objections', []))} objections)")
            if phase == "verify":
                agent_verdict = result.get("verdict", "FAIL")
                self.log(f"[verifier] agent verdict: {agent_verdict}")
                ok, evidence_results = self.independent_check()
                self.write_evidence(evidence_results)
                self.log(f"[loop] independent evidence check: {'PASS' if ok else 'FAIL'}")
                if agent_verdict == "PASS" and ok:
                    verdict = "PASS"
                    break
                # FAIL path: revise / retry / backtrack
                self.retries_used += 1
                if self.retries_used > max_retries:
                    self.log("max_retries exhausted -> FAIL")
                    break
                reasons = result.get("reasons", []) or [r["detail"] for r in evidence_results
                                                        if not r["passed"]]
                self.log(f"[loop] revise #{self.retries_used}: {reasons}")
                decision = self._coordinator_revise(ctx, reasons)
                self.log(f"[coordinator] revise decision: {decision}")
                if decision["decision"] == "abort":
                    break
                target = decision.get("target_phase", "build")
                backtrack_to = PHASES.index(target) if target in PHASES else 1
                phase_idx = backtrack_to
                continue
            phase_idx += 1
            if phase_idx >= len(PHASES):
                # Should not happen (verify always breaks/continues), guard anyway.
                break

        tree = self.memory.read_spawn_tree()
        self.log(f"=== run {self.run_id}: {verdict} "
                 f"(steps={self.steps}, retries={self.retries_used}, spawns={len(tree)}) ===")
        for rec in tree:
            self.log(f"  spawn tree: {rec['parent_id']} -> "
                     f"{rec['specialist']}/{rec['spawn_id']} "
                     f"[depth {rec['depth']}, {rec['status']}]")
        self._log_fh.close()
        return RunResult(
            run_id=self.run_id,
            verdict=verdict,
            retries_used=self.retries_used,
            steps=self.steps,
            spawns=len(tree),
            evidence_path=str(REPO_ROOT / self.cfg.tests_dir / f"evidence-{self.run_id}.json"),
            log_path=str(self.log_path),
        )

    def _coordinator_revise(self, ctx: RunContext, reasons: list[str]) -> dict:
        """Ask the coordinator what to do after a FAIL. Dry-run: backtrack to
        build (fix) with simple heuristics; live: LLM decision."""
        if self.cfg.dry_run:
            return {"decision": "retry", "target_phase": "build",
                    "rationale": "dry-run: retry build phase to fix failed criteria"}
        belt = self.make_belt("coordinator")
        system = (
            "You are the Cipher coordinator. The verifier FAILED this run. "
            "Decide: retry (same plan, fix and rebuild), backtrack (assumptions wrong, "
            "redo research), replan (new strategy), or abort (out of scope / budget).\n"
            + SAFETY_BOUNDARY
            + "\nReply with ONE strict JSON object: "
            '{"type": "final", "result": {"decision": "retry|backtrack|replan|abort", '
            '"target_phase": "research|build|analyze", "rationale": "..."}}'
        )
        user = (f"Goal: {self.task['goal']}\nFailure reasons:\n"
                + "\n".join(f"- {r}" for r in reasons)
                + f"\n\nMemory:\n{self.memory.context_summary()}\n"
                + f"Retries used: {self.retries_used}")
        from .agents import react_loop
        try:
            return react_loop(self.cfg, belt, system, user,
                              ["decision", "target_phase", "rationale"], self.log)
        except AgentError as e:
            self.log(f"[coordinator] revise failed ({e}); defaulting to abort")
            return {"decision": "abort", "target_phase": "build",
                    "rationale": f"coordinator error: {e}"}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Cipher multi-agent coding swarm")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--goal", help="ad-hoc goal string")
    src.add_argument("--task", help="path to a task JSON file")
    ap.add_argument("--run-id", help="explicit run id (default: generated)")
    ap.add_argument("--dry-run", action="store_true",
                    help="force dry-run stub agents even if a key is set")
    args = ap.parse_args(argv)

    cfg = load_config()
    if args.dry_run:
        cfg.dry_run = True

    if args.task:
        try:
            task = load_task(args.task)
        except TaskError as e:
            print(f"task error: {e}", file=sys.stderr)
            return 2
    else:
        task = {
            "id": "adhoc",
            "goal": args.goal,
            "context": "",
            "constraints": ["stdlib only", "stay inside the repo sandbox"],
            "budget": {"max_retries": cfg.default_max_retries,
                       "max_steps": cfg.default_max_steps},
            "success_criteria": [],
        }
        if not task["success_criteria"]:
            print("note: ad-hoc goal has no success_criteria; verifier will trivially PASS "
                  "only if a goal file check is added — prefer --task", file=sys.stderr)

    # Fail fast with a helpful message in live mode without a key.
    if not cfg.dry_run and not cfg.api_key:
        # load_config already sets dry_run when the key is missing; this is
        # just a guard for explicit --dry-run=False style flows.
        pass

    loop = Loop(cfg, task, run_id=args.run_id)
    try:
        result = loop.run()
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130
    print(f"verdict: {result.verdict}  run_id: {result.run_id}  "
          f"steps: {result.steps}  retries: {result.retries_used}  spawns: {result.spawns}")
    print(f"log: {result.log_path}")
    print(f"evidence: {result.evidence_path}")
    return 0 if result.verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
