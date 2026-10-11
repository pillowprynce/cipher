"""Sandboxed agent tools.

Every tool is scoped to the repo sandbox root:
  - relative paths resolve under the root; absolute paths and `..` escapes
    are rejected with ToolDenied;
  - shell exec is an allowlist (no shell=True, ever): python3/python/pytest/
    ls/cat/grep and read-only git subcommands;
  - arguments matching credential/secret patterns are rejected;
  - shell metacharacters that enable injection are rejected;
  - there is deliberately NO network tool: no HTTP client, no sockets, no
    credential store. Agents cannot exfiltrate because no channel exists.

Denials are raised as ToolDenied (permission problem) or ToolError
(execution problem); both are returned to the calling agent as tool results
so the agent can adapt.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Callable, Optional

from .config import Config


class ToolDenied(Exception):
    """A tool call was refused by policy (permissions, sandbox, secrets)."""


class ToolError(Exception):
    """A tool call was allowed but failed during execution."""


# ---------------------------------------------------------------------------
# Policy tables
# ---------------------------------------------------------------------------

CMD_ALLOWLIST = {"python3", "python", "pytest", "ls", "cat", "grep", "git"}
GIT_READONLY = {"status", "diff", "log", "show", "rev-parse"}

SECRET_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"api[_-]?key",
        r"secret",
        r"passwd",
        r"password",
        r"private[_-]?key",
        r"credential",
        r"authorization",
        r"-----begin",
        r"\.pem$",
        r"\.key$",
        r"\.p12$",
    )
]

# Injection metacharacters. Note: with shell=False these would be inert, but
# we reject them anyway as defense-in-depth. `$` and `*` are permitted so
# that grep patterns like "foo$" keep working; `$(` subshell syntax is banned.
SHELL_META = re.compile(r"[;&|`\n\r]")
SUBSHELL = re.compile(r"\$\(")


def _check_arg_safety(arg: str) -> None:
    for pat in SECRET_PATTERNS:
        if pat.search(arg):
            raise ToolDenied(f"argument looks like a secret/credential and is blocked: {arg[:40]!r}")
    if SHELL_META.search(arg) or SUBSHELL.search(arg):
        raise ToolDenied(f"argument contains shell metacharacters and is blocked: {arg[:40]!r}")


# ---------------------------------------------------------------------------
# Evidence checks (used by the verifier; re-run deterministically by the loop)
# ---------------------------------------------------------------------------

def check_criterion(criterion: dict, sandbox_root: Path) -> tuple[bool, str]:
    """Evaluate one success_criteria entry. Returns (passed, detail).

    Supported check types:
      {"type": "file_exists", "path": "artifacts/foo.py"}
      {"type": "command", "cmd": ["python3", "artifacts/foo.py"],
                                 "expect_in_output": "hello"}
      {"type": "command", "cmd": [...], "expect_exit_code": 0}
    """
    ctype = criterion.get("type")
    try:
        if ctype == "file_exists":
            p = _resolve_within(sandbox_root, criterion["path"])
            ok = p.is_file()
            return ok, f"file_exists {criterion['path']}: {'found' if ok else 'MISSING'}"
        if ctype == "command":
            cmd = criterion["cmd"]
            if not isinstance(cmd, list) or not cmd:
                return False, "command check needs a non-empty cmd list"
            proc = subprocess.run(
                [str(c) for c in cmd],
                cwd=str(sandbox_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
            out = proc.stdout + proc.stderr
            if "expect_in_output" in criterion:
                want = str(criterion["expect_in_output"])
                ok = want in out
                return ok, f"command {' '.join(cmd)}: {'output matched' if ok else 'OUTPUT MISMATCH'} (exit {proc.returncode})"
            want_code = int(criterion.get("expect_exit_code", 0))
            ok = proc.returncode == want_code
            return ok, f"command {' '.join(cmd)}: exit {proc.returncode} (wanted {want_code})"
    except (ToolDenied, KeyError, ValueError) as e:
        return False, f"check error: {e}"
    except subprocess.TimeoutExpired:
        return False, "check error: command timed out"
    return False, f"unknown check type: {ctype!r}"


def _resolve_within(sandbox_root: Path, rel: str) -> Path:
    p = (sandbox_root / rel).resolve()
    try:
        p.relative_to(sandbox_root.resolve())
    except ValueError:
        raise ToolDenied(f"path escapes the sandbox: {rel!r}")
    return p


# ---------------------------------------------------------------------------
# Tool belt
# ---------------------------------------------------------------------------

SpawnHandler = Callable[[dict, "ToolBelt"], dict]

TOOL_SCHEMAS: list[dict] = [
    {
        "name": "read_file",
        "description": "Read a text file inside the sandbox. Path is relative to the repo root.",
        "args": {"path": "string, relative path"},
    },
    {
        "name": "write_file",
        "description": "Write (create or overwrite) a text file inside the sandbox. Path is relative to the repo root.",
        "args": {"path": "string, relative path", "content": "string"},
    },
    {
        "name": "list_dir",
        "description": "List a directory inside the sandbox.",
        "args": {"path": "string, relative path (default '.')"},
    },
    {
        "name": "run_cmd",
        "description": (
            "Run a command inside the sandbox WITHOUT a shell. Allowed programs: "
            "python3, python, pytest, ls, cat, grep, and read-only git "
            "(status/diff/log/show/rev-parse). Arguments that look like secrets "
            "or contain shell metacharacters are rejected."
        ),
        "args": {"argv": "list of strings, e.g. ['python3', 'artifacts/hello.py']"},
    },
    {
        "name": "memory_append",
        "description": "Append a structured finding to shared memory (visible to later phases).",
        "args": {"finding": "object with claim/evidence fields"},
    },
    {
        "name": "memory_read",
        "description": "Read shared findings recorded so far in this run (plus your spawn context).",
        "args": {},
    },
    {
        "name": "spawn_subagent",
        "description": (
            "Spawn a specialized sub-agent for a focused sub-goal (e.g. test-writer, "
            "api-explorer, optimizer). The child gets a narrow goal, a SUBSET of your "
            "tools (never more than you have), its own tool-call budget carved out of "
            "yours, and only the context slice you provide. Children are tracked in a "
            "spawn tree; you can inspect their findings in memory. Max spawn depth and "
            "total sub-agents per run are enforced by the runtime."
        ),
        "args": {
            "specialist": "string, e.g. 'test-writer'",
            "goal": "string, the child's focused sub-goal",
            "tools": "list of tool names (must be a subset of your tools)",
            "max_tool_iterations": "int, child's tool budget",
            "context": "string, relevant memory slice for the child (not whole memory)",
        },
    },
]


class ToolBelt:
    """The tools available to one agent invocation, already permission-scoped."""

    def __init__(
        self,
        *,
        cfg: Config,
        sandbox_root: Path,
        memory,  # MemoryStore (duck-typed to avoid a cycle)
        run_id: str,
        role: str,
        agent_id: str,
        depth: int,
        tools_allowed: list[str],
        spawn_handler: Optional[SpawnHandler] = None,
        tool_budget: int | None = None,
    ) -> None:
        self.cfg = cfg
        self.sandbox_root = sandbox_root.resolve()
        self.memory = memory
        self.run_id = run_id
        self.role = role
        self.agent_id = agent_id
        self.depth = depth
        self.tools_allowed = list(tools_allowed)
        self.spawn_handler = spawn_handler
        self.tool_budget = tool_budget if tool_budget is not None else cfg.max_tool_iterations
        self.tools_used = 0

    # -- path handling ----------------------------------------------------
    def _resolve(self, rel: str) -> Path:
        if not isinstance(rel, str) or not rel:
            raise ToolDenied("path must be a non-empty string")
        if Path(rel).is_absolute():
            raise ToolDenied(f"absolute paths are blocked: {rel!r}")
        return _resolve_within(self.sandbox_root, rel)

    # -- file tools --------------------------------------------------------
    def read_file(self, path: str) -> dict:
        p = self._resolve(path)
        if not p.is_file():
            raise ToolError(f"no such file: {path!r}")
        try:
            return {"ok": True, "path": path, "content": p.read_text(encoding="utf-8")}
        except UnicodeDecodeError:
            raise ToolError(f"not a text file: {path!r}")

    def write_file(self, path: str, content: str) -> dict:
        p = self._resolve(path)
        if not isinstance(content, str):
            raise ToolError("content must be a string")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"ok": True, "path": path, "bytes": len(content.encode("utf-8"))}

    def list_dir(self, path: str = ".") -> dict:
        p = self._resolve(path)
        if not p.is_dir():
            raise ToolError(f"no such directory: {path!r}")
        return {"ok": True, "path": path, "entries": sorted(e.name for e in p.iterdir())}

    # -- exec ---------------------------------------------------------------
    def run_cmd(self, argv: list[str]) -> dict:
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) for a in argv):
            raise ToolDenied("argv must be a non-empty list of strings")
        prog = Path(argv[0]).name
        if prog not in CMD_ALLOWLIST:
            raise ToolDenied(f"command not on the allowlist: {argv[0]!r}")
        if prog == "git":
            if len(argv) < 2 or argv[1] not in GIT_READONLY:
                raise ToolDenied("only read-only git subcommands are allowed: status/diff/log/show/rev-parse")
        for a in argv[1:]:
            _check_arg_safety(a)
        try:
            proc = subprocess.run(
                argv,
                cwd=str(self.sandbox_root),
                capture_output=True,
                text=True,
                timeout=30,
            )
        except subprocess.TimeoutExpired:
            raise ToolError("command timed out after 30s")
        except OSError as e:
            # e.g. FileNotFoundError when the binary isn't installed.
            # Report it as a tool error so the agent can adapt (try a
            # different command) instead of crashing the whole run.
            raise ToolError(f"command failed to start: {e.strerror or e}")
        return {
            "ok": True,
            "argv": argv,
            "exit_code": proc.returncode,
            "stdout": proc.stdout[-4000:],
            "stderr": proc.stderr[-4000:],
        }

    # -- memory --------------------------------------------------------------
    def memory_append(self, finding: dict) -> dict:
        if not isinstance(finding, dict):
            raise ToolError("finding must be an object")
        fid = self.memory.append_finding(self.role, finding, agent_id=self.agent_id)
        return {"ok": True, "finding_id": fid}

    def memory_read(self) -> dict:
        return {"ok": True, "findings": self.memory.read_findings(agent_id=self.agent_id)}

    # -- spawn ----------------------------------------------------------------
    def spawn_subagent(self, spec: dict) -> dict:
        if self.spawn_handler is None:
            raise ToolDenied("spawning is not enabled for this agent")
        if not isinstance(spec, dict):
            raise ToolError("spawn spec must be an object")
        return self.spawn_handler(spec, self)

    # -- evidence ---------------------------------------------------------------
    def check_evidence(self, criterion: dict) -> dict:
        passed, detail = check_criterion(criterion, self.sandbox_root)
        return {"ok": True, "passed": passed, "detail": detail}

    # -- dispatch ---------------------------------------------------------------
    def describe_tools(self) -> list[dict]:
        allowed = set(self.tools_allowed)
        out = []
        for schema in TOOL_SCHEMAS:
            if schema["name"] in allowed:
                out.append(schema)
        # check_evidence is available to the verifier role via run_cmd/read_file;
        # expose it explicitly when allowed.
        if "check_evidence" in allowed:
            out.append({
                "name": "check_evidence",
                "description": "Deterministically evaluate one task success_criterion (file_exists / command).",
                "args": {"criterion": "object, one entry from the task's success_criteria"},
            })
        return out

    def call(self, name: str, args: dict | None) -> dict:
        """Dispatch one tool call with permission + budget enforcement."""
        args = args or {}
        if name not in self.tools_allowed:
            raise ToolDenied(f"role {self.role!r} may not use tool {name!r}")
        if self.tools_used >= self.tool_budget:
            raise ToolDenied(f"tool budget exhausted ({self.tool_budget} calls)")
        self.tools_used += 1
        try:
            if name == "read_file":
                return self.read_file(args["path"])
            if name == "write_file":
                return self.write_file(args["path"], args["content"])
            if name == "list_dir":
                return self.list_dir(args.get("path", "."))
            if name == "run_cmd":
                return self.run_cmd(args["argv"])
            if name == "memory_append":
                return self.memory_append(args["finding"])
            if name == "memory_read":
                return self.memory_read()
            if name == "spawn_subagent":
                return self.spawn_subagent(args)
            if name == "check_evidence":
                return self.check_evidence(args["criterion"])
        except KeyError as e:
            raise ToolError(f"missing argument: {e}")
        raise ToolDenied(f"unknown tool: {name!r}")
