"""Cipher execution loop (MVP runtime).

Canonical design from DESIGN.md / Copilot share:

    while not goal.completed:
        tasks = coordinator.decompose(goal)
        agents = assign(tasks)
        results = run_agents(agents)
        memory.update(results)
        critique = red_team(results)
        decision = coordinator.evaluate(results, critique)
        if verifier.passed(decision):
            return decision
        coordinator.replan()

Safety: aggressive persistence only inside an authorized sandbox.
Never bypass security, steal credentials/data, evade safeguards, or break in.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


@dataclass
class Goal:
    description: str
    completed: bool = False
    acceptance: list[str] = field(default_factory=list)


@dataclass
class Task:
    id: str
    goal: str
    assignee: str
    status: str = "pending"  # pending|running|blocked|done|abandoned
    deps: list[str] = field(default_factory=list)
    budget: str = "medium"


@dataclass
class Decision:
    summary: str
    evidence: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)


class Memory:
    """Shared memory facade — backs memory/findings.md + state.md later."""

    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def update(self, results: list[dict[str, Any]]) -> None:
        self.entries.extend(results)


class Coordinator:
    """Coordinator: decomposes goals into tasks, evaluates results, replans on failure."""

    def decompose(self, goal: Goal) -> list[Task]:
        """Break goal into concrete tasks with dependencies.

        MVP: deterministic three-task decomposition for all goals.
        """
        return [
            Task(
                id="T-001",
                goal="Inspect repository structure and context",
                assignee="research",
                status="pending",
                deps=[],
                budget="medium",
            ),
            Task(
                id="T-002",
                goal="Analyze findings and summarize the highest-priority issue",
                assignee="analyst",
                status="pending",
                deps=["T-001"],
                budget="medium",
            ),
            Task(
                id="T-003",
                goal="Verify evidence exists and is valid",
                assignee="verifier",
                status="pending",
                deps=["T-002"],
                budget="small",
            ),
        ]

    def evaluate(
        self, results: list[dict[str, Any]], critique: dict[str, Any]
    ) -> Decision:
        """Bundle results + critique into a Decision.

        MVP: collects evidence and artifacts from successful tasks.
        """
        all_evidence: list[str] = []
        all_artifacts: list[str] = []
        summary_parts: list[str] = []

        for result in results:
            if result.get("status") == "success":
                all_evidence.extend(result.get("evidence", []))
                all_artifacts.extend(result.get("artifacts", []))
                if "summary" in result:
                    summary_parts.append(result["summary"])

        summary = " → ".join(summary_parts) if summary_parts else "Goal executed"

        return Decision(
            summary=summary,
            evidence=all_evidence,
            artifacts=all_artifacts,
        )

    def replan(self) -> None:
        """Replan on failure.

        MVP: Just print. Later, modify task list and retry.
        """
        print("[Coordinator] Replanning after failure...")


class Verifier:
    """Verifier: checks evidence and artifacts before declaring success."""

    def passed(self, decision: Decision) -> bool:
        """Refuse success without evidence."""
        if not decision.evidence:
            print("[Verifier] No evidence was produced.")
            return False

        for evidence_path in decision.evidence:
            path = Path(evidence_path)
            if not path.exists():
                print(f"[Verifier] Missing evidence: {evidence_path}")
                return False

        for artifact_path in decision.artifacts:
            path = Path(artifact_path)
            if not path.exists():
                print(f"[Verifier] Missing artifact: {artifact_path}")
                return False

        return True


def assign(tasks: list[Task]) -> list[tuple[Task, Any]]:
    """Attach runtime fields: role, goal, context, tools, memory, permissions, budget.

    MVP: map tasks to deterministic local agents from the registry.
    """
    from src.agents import AGENT_REGISTRY

    assignments = []
    for task in tasks:
        agent = AGENT_REGISTRY.get(task.assignee)
        if agent is None:
            raise ValueError(f"Unknown assignee: {task.assignee}")
        assignments.append((task, agent))
    return assignments


def run_agents(assignments: list[tuple[Task, Any]]) -> list[dict[str, Any]]:
    """Execute agents sequentially.

    MVP: deterministic local agents that produce evidence files.
    """
    results = []
    repo_root = Path(__file__).resolve().parents[1]
    log_dir = repo_root / "logs"
    log_dir.mkdir(exist_ok=True)
    run_log = log_dir / "run-mvp.log"

    with run_log.open("a", encoding="utf-8") as log_handle:
        for task, agent in assignments:
            print(f"[Executor] Running {task.id} ({task.assignee})...")
            task.status = "running"
            log_handle.write(f"[Executor] Running {task.id} ({task.assignee})\n")

            try:
                agent_result = agent.run(task)
                result = {
                    "task_id": agent_result.task_id,
                    "status": agent_result.status,
                    "evidence": agent_result.evidence,
                    "artifacts": agent_result.artifacts,
                    "summary": agent_result.summary,
                    "notes": agent_result.notes,
                }
                results.append(result)
                task.status = "done" if agent_result.status == "success" else "abandoned"
                log_handle.write(f"  ✓ {agent_result.summary}\n")
                print(f"  ✓ {agent_result.summary}")
            except Exception as exc:  # pragma: no cover - defensive
                task.status = "abandoned"
                result = {
                    "task_id": task.id,
                    "status": "failed",
                    "evidence": [],
                    "artifacts": [],
                    "summary": f"Task failed: {exc}",
                    "notes": str(exc),
                }
                results.append(result)
                log_handle.write(f"  ✗ {exc}\n")
                print(f"  ✗ FAILED: {exc}")

    return results


def red_team(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Critic / red-team: attack assumptions.

    MVP: deterministic checks for missing evidence/artifacts.
    """
    findings = {"blocking": [], "warnings": []}

    for result in results:
        if result.get("status") == "failed":
            findings["blocking"].append(
                f"Task {result['task_id']} failed: {result['summary']}"
            )

        if result.get("status") == "success" and not result.get("evidence"):
            findings["warnings"].append(
                f"Task {result['task_id']} has no evidence"
            )

        for evidence_path in result.get("evidence", []):
            if not Path(evidence_path).exists():
                findings["blocking"].append(
                    f"Evidence missing for {result['task_id']}: {evidence_path}"
                )

        for artifact_path in result.get("artifacts", []):
            if not Path(artifact_path).exists():
                findings["blocking"].append(
                    f"Artifact missing for {result['task_id']}: {artifact_path}"
                )

    return findings


def write_task_records(tasks: list[Task]) -> None:
    """Write task records using the repo's existing task format."""
    repo_root = Path(__file__).resolve().parents[1]
    tasks_dir = repo_root / "tasks"
    tasks_dir.mkdir(exist_ok=True)

    for task in tasks:
        record_path = tasks_dir / f"{task.id}.md"
        if record_path.exists():
            continue

        record_path.write_text(
            "\n".join(
                [
                    f"# {task.id}",
                    "",
                    f"Goal: {task.goal}",
                    f"Assignee: {task.assignee}",
                    f"Status: {task.status}",
                    f"Dependencies: {', '.join(task.deps) if task.deps else 'none'}",
                    f"Budget: {task.budget}",
                    "",
                    "## Notes",
                    "- Deterministic MVP execution",
                ]
            ) + "\n",
            encoding="utf-8",
        )


def run(goal: Goal, *, max_iterations: int = 32) -> Optional[Decision]:
    """Main Cipher loop. Returns Decision on PASS, None if budget exhausted."""
    coordinator = Coordinator()
    verifier = Verifier()
    memory = Memory()

    print(f"\n[Loop] Goal: {goal.description}")

    for iteration in range(max_iterations):
        if goal.completed:
            break

        print(f"\n[Loop] Iteration {iteration + 1}")
        tasks = coordinator.decompose(goal)
        write_task_records(tasks)

        print(f"[Loop] Decomposed into {len(tasks)} tasks:")
        for task in tasks:
            deps_str = f" (depends on {', '.join(task.deps)})" if task.deps else ""
            print(f"  {task.id}: {task.assignee}{deps_str}")

        assignments = assign(tasks)
        results = run_agents(assignments)
        memory.update(results)

        critique = red_team(results)
        if critique["blocking"]:
            print("[Loop] Blocking findings:")
            for finding in critique["blocking"]:
                print(f"  - {finding}")
        if critique["warnings"]:
            print("[Loop] Warnings:")
            for warning in critique["warnings"]:
                print(f"  - {warning}")

        decision = coordinator.evaluate(results, critique)
        print(f"\n[Loop] Summary: {decision.summary}")
        print(f"  Evidence: {len(decision.evidence)} items")
        print(f"  Artifacts: {len(decision.artifacts)} items")

        if verifier.passed(decision):
            print("\n[Loop] Verifier passed")
            goal.completed = True
            return decision

        print("\n[Loop] Verifier failed. Replanning...")
        coordinator.replan()

    return None


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Cipher: multi-agent coding swarm"
    )
    parser.add_argument(
        "--goal",
        type=str,
        required=True,
        help="Goal for the swarm to execute",
    )
    args = parser.parse_args()

    print(f"Goal: {args.goal}")
    goal = Goal(description=args.goal)
    decision = run(goal)

    if decision is not None:
        print("RESULT: PASS")
        print(f"Decision: {decision.summary}")
        print(f"Evidence: {len(decision.evidence)}")
        print(f"Artifacts: {len(decision.artifacts)}")
        return 0

    print("RESULT: FAIL")
    return 1


if __name__ == "__main__":
    sys.exit(main())
