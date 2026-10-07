"""Coordinator: decomposes goals into tasks, evaluates results, replans on failure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.loop import Goal, Task, Decision


class Coordinator:
    """Deterministic task decomposition for MVP."""

    def decompose(self, goal: Goal) -> list[Task]:
        """Break goal into concrete tasks with dependencies.
        
        MVP: stupidly simple deterministic decomposition.
        No AI planning yet.
        """
        # For now, all goals follow this pattern:
        # 1. Research agent inspects
        # 2. Analyst summarizes
        # 3. Verifier checks evidence
        
        return [
            Task(
                id="T-001",
                goal="Inspect repository structure and context",
                assignee="research",
                status="pending",
                deps=[]
            ),
            Task(
                id="T-002",
                goal="Analyze findings and summarize",
                assignee="analyst",
                status="pending",
                deps=["T-001"]
            ),
            Task(
                id="T-003",
                goal="Verify evidence exists and is valid",
                assignee="verifier",
                status="pending",
                deps=["T-002"]
            )
        ]

    def evaluate(self, results: list[dict[str, Any]], critique: dict[str, Any]) -> Decision:
        """Bundle results + critique into a Decision.
        
        MVP: Just collect evidence and artifacts.
        """
        all_evidence = []
        all_artifacts = []
        summary_parts = []

        for result in results:
            all_evidence.extend(result.get("evidence", []))
            all_artifacts.extend(result.get("artifacts", []))
            if "summary" in result:
                summary_parts.append(result["summary"])

        summary = " → ".join(summary_parts) if summary_parts else "Goal executed"

        return Decision(
            summary=summary,
            evidence=all_evidence,
            artifacts=all_artifacts
        )

    def replan(self) -> None:
        """Replan on failure.
        
        MVP: Just print. Later, modify task list and retry.
        """
        print("[Coordinator] Replanning after failure...")
