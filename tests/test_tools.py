"""Contract tests for src/tools.py stubs.

Documents ToolRegistry allowlist + unknown-tool behavior and that tool
bodies remain NotImplementedError until wired.
"""

from __future__ import annotations

import pytest

from tools import (
    TOOL_NAMES,
    ToolPermissionError,
    ToolRegistry,
    create_agent,
    inspect_repo,
    read_file,
    run_code,
    run_test,
    web_search,
    write_file,
)


def test_tool_names_tuple():
    assert TOOL_NAMES == (
        "web_search",
        "read_file",
        "write_file",
        "run_test",
        "run_code",
        "inspect_repo",
        "create_agent",
    )
    assert len(TOOL_NAMES) == 7
    assert len(set(TOOL_NAMES)) == 7  # unique


def test_registry_registers_all_tool_names():
    reg = ToolRegistry()
    for name in TOOL_NAMES:
        assert name in reg._tools


def test_call_denied_raises_tool_permission_error():
    reg = ToolRegistry()
    with pytest.raises(ToolPermissionError, match="web_search"):
        reg.call("web_search", allowed=set(), query="x")


def test_call_denied_lists_allowed_in_message():
    reg = ToolRegistry()
    with pytest.raises(ToolPermissionError, match="read_file"):
        reg.call("write_file", allowed={"read_file"}, path="a", content="b")


def test_call_unknown_tool_raises_keyerror_after_allowlist():
    """Allowlist passes first; missing registry entry then KeyErrors."""
    reg = ToolRegistry()
    reg._tools.pop("web_search", None)
    with pytest.raises(KeyError, match="unknown tool: web_search"):
        reg.call("web_search", allowed={"web_search"}, query="q")


def test_call_permission_checked_before_unknown():
    """Denied tools raise ToolPermissionError even if not registered."""
    reg = ToolRegistry()
    reg._tools.clear()
    with pytest.raises(ToolPermissionError):
        reg.call("web_search", allowed=set(), query="q")


def test_call_allowed_invokes_stub_notimplemented():
    reg = ToolRegistry()
    with pytest.raises(NotImplementedError, match="web_search stub"):
        reg.call("web_search", allowed={"web_search"}, query="cipher")


@pytest.mark.parametrize(
    "fn,kwargs,match",
    [
        (web_search, {"query": "q"}, "web_search stub"),
        (read_file, {"path": "x"}, "read_file stub"),
        (write_file, {"path": "x", "content": "y"}, "write_file stub"),
        (run_test, {}, "run_test stub"),
        (run_code, {"code": "1+1"}, "run_code stub"),
        (inspect_repo, {}, "inspect_repo stub"),
        (create_agent, {"role": "builder", "goal": "g"}, "create_agent stub"),
    ],
)
def test_tool_bodies_raise_not_implemented(fn, kwargs, match):
    with pytest.raises(NotImplementedError, match=match):
        fn(**kwargs)


def test_tool_permission_error_is_permission_error():
    assert issubclass(ToolPermissionError, PermissionError)
