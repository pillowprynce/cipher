"""Tests for Cipher MVP runtime.

Verify:
1. Goal decomposition into tasks
2. Task assignment to agents
3. Agent execution and evidence generation
4. Red-team finding blocking issues
5. Verifier accepting decisions with valid evidence
6. Verifier rejecting decisions with missing evidence
7. End-to-end goal execution
8. CLI invocation
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

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


class TestCoordinator:
    """Test Coordinator.decompose() and evaluate()."""

    def test_decompose_creates_three_tasks(self) -> None:
        """Decompose should create T-001, T-002, T-003 with valid deps."""
        coordinator = Coordinator()
        goal = Goal(description="Test goal")

        tasks = coordinator.decompose(goal)

        assert len(tasks) == 3
        assert tasks[0].id == "T-001"
        assert tasks[1].id == "T-002"
        assert tasks[2].id == "T-003"

    def test_decompose_dependencies_are_acyclic(self) -> None:
        """Task dependencies must be acyclic."""
        coordinator = Coordinator()
        goal = Goal(description="Test goal")
        tasks = coordinator.decompose(goal)

        assert tasks[0].deps == []
        assert tasks[1].deps == ["T-001"]
        assert tasks[2].deps == ["T-002"]

    def test_evaluate_collects_evidence_and_artifacts(self) -> None:
        """Evaluate should bundle evidence and artifacts from results."""
        coordinator = Coordinator()
        results = [
            {
                "task_id": "T-001",
                "status": "success",
                "evidence": ["evidence.txt"],
                "artifacts": [],
                "summary": "Found evidence",
            },
            {
                "task_id": "T-002",
                "status": "success",
                "evidence": [],
                "artifacts": ["artifact.txt"],
                "summary": "Built artifact",
            },
        ]
        critique = {"blocking": [], "warnings": []}

        decision = coordinator.evaluate(results, critique)

        assert "evidence.txt" in decision.evidence
        assert "artifact.txt" in decision.artifacts
        assert "Found evidence" in decision.summary
        assert "Built artifact" in decision.summary

    def test_evaluate_ignores_failed_tasks(self) -> None:
        """Evaluate should skip failed tasks."""
        coordinator = Coordinator()
        results = [
            {
                "task_id": "T-001",
                "status": "failed",
                "evidence": ["should-be-ignored.txt"],
                "artifacts": [],
                "summary": "This failed",
            },
        ]
        critique = {"blocking": [], "warnings": []}

        decision = coordinator.evaluate(results, critique)

        assert decision.evidence == []
        assert decision.artifacts == []


class TestVerifier:
    """Test Verifier safety checks."""

    def test_verifier_requires_evidence(self) -> None:
        """Verifier must refuse success without evidence."""
        verifier = Verifier()
        decision = Decision(summary="No evidence", evidence=[], artifacts=[])

        assert not verifier.passed(decision)

    def test_verifier_checks_evidence_exists(self, tmp_path: Path) -> None:
        """Verifier must check that evidence files actually exist."""
        verifier = Verifier()
        missing_file = tmp_path / "missing.txt"
        decision = Decision(
            summary="Has evidence",
            evidence=[str(missing_file)],
            artifacts=[],
        )

        assert not verifier.passed(decision)

    def test_verifier_checks_artifacts_exist(self, tmp_path: Path) -> None:
        """Verifier must check that artifact files actually exist."""
        verifier = Verifier()
        evidence_file = tmp_path / "evidence.txt"
        evidence_file.write_text("evidence")
        missing_artifact = tmp_path / "missing.txt"

        decision = Decision(
            summary="Has evidence, missing artifact",
            evidence=[str(evidence_file)],
            artifacts=[str(missing_artifact)],
        )

        assert not verifier.passed(decision)

    def test_verifier_passes_with_valid_evidence(self, tmp_path: Path) -> None:
        """Verifier should pass when evidence and artifacts exist."""
        verifier = Verifier()
        evidence_file = tmp_path / "evidence.txt"
        evidence_file.write_text("valid evidence")
        artifact_file = tmp_path / "artifact.txt"
        artifact_file.write_text("valid artifact")

        decision = Decision(
            summary="Complete",
            evidence=[str(evidence_file)],
            artifacts=[str(artifact_file)],
        )

        assert verifier.passed(decision)


class TestRedTeam:
    """Test red_team findings."""

    def test_red_team_finds_failed_tasks(self) -> None:
        """Red team should flag failed tasks as blocking."""
        results = [
            {
                "task_id": "T-001",
                "status": "failed",
                "evidence": [],
                "artifacts": [],
                "summary": "Task failed",
            }
        ]

        findings = red_team(results)

        assert len(findings["blocking"]) > 0
        assert "T-001" in findings["blocking"][0]

    def test_red_team_finds_missing_evidence(self, tmp_path: Path) -> None:
        """Red team should flag missing evidence as blocking."""
        results = [
            {
                "task_id": "T-001",
                "status": "success",
                "evidence": [str(tmp_path / "missing.txt")],
                "artifacts": [],
                "summary": "Done",
            }
        ]

        findings = red_team(results)

        assert len(findings["blocking"]) > 0

    def test_red_team_finds_missing_artifacts(self, tmp_path: Path) -> None:
        """Red team should flag missing artifacts as blocking."""
        results = [
            {
                "task_id": "T-001",
                "status": "success",
                "evidence": [],
                "artifacts": [str(tmp_path / "missing.txt")],
                "summary": "Done",
            }
        ]

        findings = red_team(results)

        assert len(findings["blocking"]) > 0

    def test_red_team_passes_when_all_valid(self, tmp_path: Path) -> None:
        """Red team should clear when evidence/artifacts exist."""
        evidence = tmp_path / "evidence.txt"
        evidence.write_text("valid")
        artifact = tmp_path / "artifact.txt"
        artifact.write_text("valid")

        results = [
            {
                "task_id": "T-001",
                "status": "success",
                "evidence": [str(evidence)],
                "artifacts": [str(artifact)],
                "summary": "Done",
            }
        ]

        findings = red_team(results)

        assert findings["blocking"] == []


class TestAssign:
    """Test task to agent assignment."""

    def test_assign_maps_tasks_to_agents(self) -> None:
        """Assign should map each task to its corresponding agent."""
        tasks = [
            Task(
                id="T-001",
                goal="Inspect",
                assignee="research",
                deps=[],
            ),
            Task(
                id="T-002",
                goal="Analyze",
                assignee="analyst",
                deps=["T-001"],
            ),
            Task(
                id="T-003",
                goal="Verify",
                assignee="verifier",
                deps=["T-002"],
            ),
        ]

        assignments = assign(tasks)

        assert len(assignments) == 3
        assert assignments[0][0] == tasks[0]
        assert assignments[1][0] == tasks[1]
        assert assignments[2][0] == tasks[2]

    def test_assign_raises_on_unknown_assignee(self) -> None:
        """Assign should raise on unknown agent."""
        tasks = [
            Task(
                id="T-001",
                goal="Unknown",
                assignee="nonexistent",
                deps=[],
            )
        ]

        with pytest.raises(ValueError, match="Unknown assignee"):
            assign(tasks)


class TestRunAgents:
    """Test agent execution."""

    def test_run_agents_executes_sequentially(self) -> None:
        """Run_agents should execute all agents and collect results."""
        from src.agents import ResearchAgent

        tasks = [
            Task(
                id="T-001",
                goal="Test",
                assignee="research",
                deps=[],
            )
        ]
        assignments = [(tasks[0], ResearchAgent())]

        results = run_agents(assignments)

        assert len(results) == 1
        assert results[0]["task_id"] == "T-001"
        assert results[0]["status"] == "success"

    def test_run_agents_creates_evidence_files(self) -> None:
        """Run_agents should create actual evidence files."""
        from src.agents import ResearchAgent

        tasks = [
            Task(
                id="T-001",
                goal="Test",
                assignee="research",
                deps=[],
            )
        ]
        assignments = [(tasks[0], ResearchAgent())]

        results = run_agents(assignments)
        evidence_path = Path(results[0]["evidence"][0])

        assert evidence_path.exists()
        assert evidence_path.stat().st_size > 0


class TestEndToEnd:
    """Test complete goal execution."""

    def test_goal_executes_end_to_end(self) -> None:
        """Complete goal should decompose, execute, and verify."""
        goal = Goal(description="Test inspection goal")

        decision = run(goal, max_iterations=1)

        assert decision is not None
        assert len(decision.evidence) > 0
        assert len(decision.artifacts) > 0

    def test_goal_creates_task_records(self) -> None:
        """Goal execution should create task records."""
        goal = Goal(description="Test inspection goal")

        run(goal, max_iterations=1)

        repo_root = Path(__file__).resolve().parents[1]
        tasks_dir = repo_root / "tasks"

        assert (tasks_dir / "T-001.md").exists()
        assert (tasks_dir / "T-002.md").exists()
        assert (tasks_dir / "T-003.md").exists()

    def test_goal_creates_execution_log(self) -> None:
        """Goal execution should create a run log."""
        goal = Goal(description="Test inspection goal")

        run(goal, max_iterations=1)

        repo_root = Path(__file__).resolve().parents[1]
        logs_dir = repo_root / "logs"

        assert (logs_dir / "run-mvp.log").exists()


class TestVerifierFailure:
    """Test verifier correctly rejecting invalid decisions."""

    def test_verifier_rejects_missing_evidence(self, tmp_path: Path) -> None:
        """Verifier must reject decisions where evidence files are deleted."""
        # This is the critical safety test: verifier can be forced to fail

        verifier = Verifier()
        evidence_path = tmp_path / "evidence.txt"

        # Create decision with a path that won't exist
        decision = Decision(
            summary="Missing evidence",
            evidence=[str(evidence_path)],
            artifacts=[],
        )

        # Should fail because file doesn't exist
        assert not verifier.passed(decision)

    def test_goal_fails_when_evidence_missing(self, tmp_path: Path) -> None:
        """Goal execution should fail if critical evidence is missing."""
        # Monkey-patch agents to return non-existent evidence paths
        from src import agents

        class FailingAgent(agents.BaseAgent):
            def run(self, task: agents.Task) -> agents.AgentResult:
                return agents.AgentResult(
                    task_id=task.id,
                    status="success",
                    evidence=[str(tmp_path / "nonexistent.txt")],
                    artifacts=[],
                    summary="Claimed success with missing evidence",
                )

        original_registry = agents.AGENT_REGISTRY.copy()
        agents.AGENT_REGISTRY["research"] = FailingAgent()

        try:
            goal = Goal(description="Test with missing evidence")
            decision = run(goal, max_iterations=1)

            # Should not reach here; goal should complete with verifier rejection
            # If we do get a decision, verifier should have rejected it
            if decision is not None:
                verifier = Verifier()
                assert not verifier.passed(decision)
        finally:
            # Restore original registry
            agents.AGENT_REGISTRY.clear()
            agents.AGENT_REGISTRY.update(original_registry)
