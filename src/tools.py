"""Controlled tool interface for Cipher agents.

Agents must not receive unlimited capabilities. Every side effect goes through
named tools with permission checks (to be enforced by the runtime).

Safety: tools operate only inside an authorized sandbox. They must never be
used to bypass security, steal credentials/data, evade safeguards, or break
into systems.
"""

from __future__ import annotations

from typing import Any, Callable, Optional


class ToolPermissionError(PermissionError):
    """Raised when an agent invokes a tool outside its authorized set."""


class ToolRegistry:
    """Maps tool names → callables; filters by agent permissions."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {
            "web_search": web_search,
            "read_file": read_file,
            "write_file": write_file,
            "run_test": run_test,
            "run_code": run_code,
            "inspect_repo": inspect_repo,
            "create_agent": create_agent,
        }

    def call(self, name: str, allowed: set[str], **kwargs: Any) -> Any:
        if name not in allowed:
            raise ToolPermissionError(f"tool '{name}' not in agent permissions: {sorted(allowed)}")
        if name not in self._tools:
            raise KeyError(f"unknown tool: {name}")
        return self._tools[name](**kwargs)


# --- stubs: replace bodies with real implementations ---

def web_search(query: str, limit: int = 5) -> list[dict[str, str]]:
    """Search the public web; return title/url/snippet dicts."""
    raise NotImplementedError("web_search stub — wire search provider later")


def read_file(path: str) -> str:
    """Read a file within the authorized workspace."""
    raise NotImplementedError("read_file stub — enforce workspace root later")


def write_file(path: str, content: str) -> None:
    """Write a file within the authorized workspace."""
    raise NotImplementedError("write_file stub — enforce workspace root later")


def run_test(target: str = "tests") -> dict[str, Any]:
    """Run tests; return {passed, failed, output} for the Verifier."""
    raise NotImplementedError("run_test stub — wire pytest/runner later")


def run_code(code: str, language: str = "python") -> dict[str, Any]:
    """Execute code in a sandbox; return {stdout, stderr, exit_code}."""
    raise NotImplementedError("run_code stub — wire sandbox executor later")


def inspect_repo(path: str = ".", pattern: Optional[str] = None) -> dict[str, Any]:
    """Inspect repository structure / search code (GitHub-native friendly)."""
    raise NotImplementedError("inspect_repo stub — wire git/tree/search later")


def create_agent(
    role: str,
    goal: str,
    *,
    tools: Optional[list[str]] = None,
    budget: Optional[str] = None,
) -> dict[str, Any]:
    """Spawn a specialized sub-agent (authorized sandbox only)."""
    raise NotImplementedError("create_agent stub — wire agent runtime later")


# Canonical names for docs / permission lists
TOOL_NAMES = (
    "web_search",
    "read_file",
    "write_file",
    "run_test",
    "run_code",
    "inspect_repo",
    "create_agent",
)
