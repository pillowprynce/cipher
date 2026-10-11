"""Role contracts and system-prompt construction.

Role specs live in agents/<role>.md (human-readable contract) and
agents/roles.yaml (machine-readable index: tools, challenge rules, response
contract keys). System prompts are built from the spec file so the contract
the operator reads is the contract the model gets.

Specialist (spawned sub-agent) prompts are generated: base agent contract +
safety boundary + specialist description + narrow goal + tool subset.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .tools import ToolBelt

REPO_ROOT = Path(__file__).resolve().parent.parent
AGENTS_DIR = REPO_ROOT / "agents"

SAFETY_BOUNDARY = """\
## Safety boundary (non-negotiable)
Aggressive persistence applies ONLY inside your authorized sandbox (this repo
working copy). You must NEVER: bypass security controls, steal credentials or
private data, evade safeguards, break into systems, or produce malware or
unauthorized access tooling. You have no network access and no credential
store — do not try to obtain one. If a goal would require leaving the
sandbox, refuse that step and report it. "Cheating" here means authorized
rule-bending inside the sandbox: try multiple approaches, challenge weak
conclusions, abandon failed approaches, retry and replan — never breaking
rules to do it.\
"""

TOOL_PROTOCOL = """\
## How you act (ReAct tool loop)
You work in turns. EVERY turn you must output exactly ONE strict JSON object,
no prose outside it, either:

1. A tool call:
   {"type": "tool_call", "tool": "<name>", "args": { ... }}

2. Your final result (only when done — no more tool calls needed):
   {"type": "final", "result": { ...contract below... }}

After each tool call I will reply with:
   {"tool": "<name>", "result": { ... } }
and you continue. Tool calls are bounded; if you run out, produce your best
final result from what you have. Record important conclusions with the
memory_append tool so later phases can see them.\
"""


def load_roles_index() -> dict[str, dict[str, Any]]:
    # Minimal YAML-subset parser: roles.yaml is written in a restricted style
    # (see agents/roles.yaml). We parse it without dependencies.
    text = (AGENTS_DIR / "roles.yaml").read_text(encoding="utf-8")
    return _parse_restricted_yaml(text)


def _parse_restricted_yaml(text: str) -> dict[str, Any]:
    """Parse the restricted YAML style used by agents/roles.yaml.

    Supports: nested mappings, block lists of scalars, inline lists [a, b],
    and scalar values. Two-space indentation. A `key:` line with no value
    becomes a mapping or a list depending on the next non-empty line.
    """
    raw_lines = [ln.rstrip() for ln in text.splitlines()
                 if ln.strip() and not ln.strip().startswith("#")]
    root: dict[str, Any] = {}
    # stack of (indent, container)
    stack: list[tuple[int, Any]] = [(-1, root)]
    n = len(raw_lines)
    for i, ln in enumerate(raw_lines):
        indent = len(ln) - len(ln.lstrip(" "))
        content = ln.strip()
        while stack and indent <= stack[-1][0]:
            stack.pop()
        if not stack:
            raise ValueError(f"bad yaml near: {ln}")
        parent = stack[-1][1]
        if content.startswith("- "):
            if not isinstance(parent, list):
                raise ValueError(f"bad yaml near: {ln}")
            parent.append(_scalar(content[2:].strip()))
            continue
        if content.endswith(":"):
            key = content[:-1].strip()
            # lookahead: list or mapping?
            nxt = raw_lines[i + 1].strip() if i + 1 < n else ""
            new: Any = [] if nxt.startswith("- ") else {}
            if not isinstance(parent, dict):
                raise ValueError(f"bad yaml near: {ln}")
            parent[key] = new
            stack.append((indent, new))
            continue
        key, _, val = content.partition(":")
        key, val = key.strip(), val.strip()
        if not isinstance(parent, dict):
            raise ValueError(f"bad yaml near: {ln}")
        parent[key] = _scalar(val)
    return root


def _scalar(val: str) -> Any:
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        return [_scalar(v.strip()) for v in inner.split(",")] if inner else []
    if val in ("true", "True"):
        return True
    if val in ("false", "False"):
        return False
    if val.startswith('"') and val.endswith('"'):
        return val[1:-1]
    if val.startswith("'") and val.endswith("'"):
        return val[1:-1]
    try:
        return int(val)
    except ValueError:
        return val


def get_role(role: str) -> dict[str, Any]:
    index = load_roles_index()
    roles = index.get("roles", {})
    if role not in roles:
        raise KeyError(f"unknown role: {role!r}")
    return roles[role]


def read_spec(role: str) -> str:
    p = AGENTS_DIR / f"{role}.md"
    if not p.exists():
        raise FileNotFoundError(f"missing role spec: {p}")
    return p.read_text(encoding="utf-8")


def build_system_prompt(role: str, belt: ToolBelt) -> str:
    """System prompt for a top-level role: spec file + safety + protocol + tools."""
    spec = read_spec(role)
    tools = belt.describe_tools()
    tool_lines = "\n".join(
        f"- {t['name']}{t['args']}: {t['description']}" for t in tools
    )
    contract = get_role(role).get("response_contract", {})
    return (
        f"# Role: {role}\n\n{spec}\n\n{SAFETY_BOUNDARY}\n\n"
        f"## Your available tools\n{tool_lines}\n\n"
        f"{TOOL_PROTOCOL}\n"
        f"## Final result contract\n"
        f"Your final result object MUST be a JSON object with these keys:\n{contract}\n"
        "Missing keys = malformed output. Evidence (file paths, command output) "
        "is required for every claim."
    )


def build_specialist_prompt(
    *,
    specialist: str,
    goal: str,
    context: str,
    parent_role: str,
    belt: ToolBelt,
    depth: int,
    max_depth: int,
) -> str:
    """Generated system prompt for a spawned specialist sub-agent."""
    tools = belt.describe_tools()
    tool_lines = "\n".join(
        f"- {t['name']}{t['args']}: {t['description']}" for t in tools
    )
    spawn_note = (
        "You may NOT spawn further sub-agents: you are at the maximum spawn depth."
        if depth >= max_depth
        else "You may spawn your own sub-agents only if truly necessary; depth is limited."
    )
    return (
        f"# Specialist sub-agent: {specialist}\n\n"
        f"You are a specialist spawned by the {parent_role} agent (spawn depth {depth}). "
        f"Your narrow goal:\n> {goal}\n\n"
        "## Base contract\n"
        "- Solve ONLY your narrow goal. Do not expand scope.\n"
        "- Record findings with memory_append; they are namespaced to your spawn id.\n"
        "- Your parent will inspect, accept, reject, or ask you to retry your output.\n"
        "- Your tools are a SUBSET of your parent's tools. You can NEVER escalate "
        "permissions beyond what your parent granted.\n"
        f"- {spawn_note}\n\n"
        f"{SAFETY_BOUNDARY}\n\n"
        f"## Context provided by your parent\n{context or '(none)'}\n\n"
        f"## Your available tools\n{tool_lines}\n\n"
        f"{TOOL_PROTOCOL}\n"
        "## Final result contract\n"
        "Your final result object MUST be a JSON object with these keys:\n"
        '{"summary": "string, what you did", '
        '"outputs": ["paths or findings you produced"], '
        '"evidence": "string, how it can be verified"}\n'
    )
