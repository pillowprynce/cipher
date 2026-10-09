"""Compatibility tests for the active Cipher runtime.

The older stub-only contract in this file was superseded by the working
end-to-end MVP runtime tests in tests/test_mvp_runtime.py.
"""

from __future__ import annotations

from pathlib import Path

from src.loop import (
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


def test_goal_defaults() -> None:
    g = Goal(description="ship feature")
    assert g.description == "ship feature"
    assert g.completed is False
    assert g.acceptance == []


def test_task_defaults() -> None:
    t = Task(id="T-000", goal="scaffold", assignee="research")
    assert t.status == "pending"
    assert t.deps == []


def test_decision_defaults() -> None:
    d = Decision(summary="ok")
    assert d.evidence == []
    assert d.artifacts == []


def test_memory_update_extends_entries() -> None:
    mem = Memory()
    assert mem.entries == []
    mem.update([{"agent": "builder", "ok": True}])
    mem.update([{"agent": "critic", "ok": False}])
    assert mem.entries == [
        {"agent": "builder", "ok": True},
        {"agent": "critic", "ok": False},
    ]


def test_verifier_passed_false_without_evidence() -> None:
    v = Verifier()
    assert v.passed(Decision(summary="claim", evidence=[])) is False


def test_coordinator_decompose_creates_three_tasks() -> None:
    tasks = Coordinator().decompose(Goal(description="x"))
    assert [task.id for task in tasks] == ["T-001", "T-002", "T-003"]
    assert tasks[1].deps == ["T-001"]
    assert tasks[2].deps == ["T-002"]


def test_assign_maps_tasks_to_agents() -> None:
    tasks = [
        Task(id="T-001", goal="Inspect", assignee="research", deps=[]),
        Task(id="T-002", goal="Analyze", assignee="analyst", deps=["T-001"]),
        Task(id="T-003", goal="Verify", assignee="verifier", deps=["T-002"]),
    ]

    assignments = assign(tasks)
    assert len(assignments) == 3
    assert assignments[0][0].id == "T-001"
    assert assignments[1][0].id == "T-002"
    assert assignments[2][0].id == "T-003"


def test_run_agents_executes_sequentially() -> None:
    from src.agents import ResearchAgent

    tasks = [Task(id="T-001", goal="Test", assignee="research", deps=[])]
    results = run_agents([(tasks[0], ResearchAgent())])

    assert len(results) == 1
    assert results[0]["task_id"] == "T-001"
    assert results[0]["status"] == "success"


def test_red_team_finds_failed_tasks() -> None:
    results = [{
        "task_id": "T-001",
        "status": "failed",
        "evidence": [],
        "artifacts": [],
        "summary": "Task failed",
    }]
    findings = red_team(results)
    assert len(findings["blocking"]) > 0


def test_run_returns_decision_for_valid_goal() -> None:
    decision = run(Goal(description="Test inspection goal"), max_iterations=1)
    assert decision is not None
    assert len(decision.evidence) > 0
    assert len(decision.artifacts) > 0


def test_run_creates_task_records() -> None:
    run(Goal(description="Test inspection goal"), max_iterations=1)
    repo_root = Path(__file__).resolve().parents[1]
    tasks_dir = repo_root / "tasks"
    assert (tasks_dir / "T-001.md").exists()
    assert (tasks_dir / "T-002.md").exists()
    assert (tasks_dir / "T-003.md").exists()
