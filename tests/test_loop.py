"""Contract tests for src/loop.py stubs.

Documents implemented behavior (Memory, empty-evidence Verifier) and
where stubs raise NotImplementedError. Does not require full loop wiring.
"""

from __future__ import annotations

import pytest

from loop import (
    Coordinator,
    Decision,
    Goal,
    Memory,
    Task,
    Verifier,
    assign,
    red_team,
    run,
    run_agents,
)


# --- dataclasses ---


def test_goal_defaults():
    g = Goal(description="ship feature")
    assert g.description == "ship feature"
    assert g.completed is False
    assert g.acceptance == []


def test_task_defaults():
    t = Task(id="T-000", goal="scaffold", assignee="builder")
    assert t.status == "pending"
    assert t.deps == []


def test_decision_defaults():
    d = Decision(summary="ok")
    assert d.evidence == []
    assert d.artifacts == []


def test_goal_acceptance_is_independent_per_instance():
    a = Goal(description="a")
    b = Goal(description="b")
    a.acceptance.append("x")
    assert b.acceptance == []


# --- Memory (implemented) ---


def test_memory_update_extends_entries():
    mem = Memory()
    assert mem.entries == []
    mem.update([{"agent": "builder", "ok": True}])
    mem.update([{"agent": "critic", "ok": False}])
    assert mem.entries == [
        {"agent": "builder", "ok": True},
        {"agent": "critic", "ok": False},
    ]


def test_memory_update_empty_is_noop():
    mem = Memory()
    mem.update([])
    assert mem.entries == []


# --- Verifier (partial) ---


def test_verifier_passed_false_without_evidence():
    v = Verifier()
    assert v.passed(Decision(summary="claim", evidence=[])) is False


def test_verifier_passed_raises_when_evidence_present():
    v = Verifier()
    with pytest.raises(NotImplementedError, match="verifier.passed"):
        v.passed(Decision(summary="claim", evidence=["tests/test_loop.py"]))


# --- Coordinator / assign / run_agents / red_team stubs ---


def test_coordinator_decompose_raises():
    with pytest.raises(NotImplementedError, match="coordinator.decompose"):
        Coordinator().decompose(Goal(description="x"))


def test_coordinator_evaluate_raises():
    with pytest.raises(NotImplementedError, match="coordinator.evaluate"):
        Coordinator().evaluate([], {})


def test_coordinator_replan_raises():
    with pytest.raises(NotImplementedError, match="coordinator.replan"):
        Coordinator().replan()


def test_assign_raises():
    with pytest.raises(NotImplementedError, match="assign"):
        assign([])


def test_run_agents_raises():
    with pytest.raises(NotImplementedError, match="run_agents"):
        run_agents([])


def test_red_team_raises():
    with pytest.raises(NotImplementedError, match="red_team"):
        red_team([])


# --- run() hits first stub ---


def test_run_raises_on_decompose_stub():
    with pytest.raises(NotImplementedError, match="coordinator.decompose"):
        run(Goal(description="anything"), max_iterations=1)


def test_run_returns_none_when_goal_already_completed():
    g = Goal(description="done", completed=True)
    assert run(g, max_iterations=3) is None
