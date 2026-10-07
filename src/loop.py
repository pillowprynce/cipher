"""Cipher execution loop (stub).

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

from dataclasses import dataclass, field
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
    def decompose(self, goal: Goal) -> list[Task]:
        raise NotImplementedError("coordinator.decompose")

    def evaluate(self, results: list[dict[str, Any]], critique: dict[str, Any]) -> Decision:
        raise NotImplementedError("coordinator.evaluate")

    def replan(self) -> None:
        raise NotImplementedError("coordinator.replan")


class Verifier:
    def passed(self, decision: Decision) -> bool:
        """Refuse success without evidence."""
        if not decision.evidence:
            return False
        raise NotImplementedError("verifier.passed — wire evidence checks")


def assign(tasks: list[Task]) -> list[dict[str, Any]]:
    """Attach runtime fields: role, goal, context, tools, memory, permissions, budget."""
    raise NotImplementedError("assign")


def run_agents(agents: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raise NotImplementedError("run_agents")


def red_team(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Critic / red-team: attack assumptions."""
    raise NotImplementedError("red_team")


def run(goal: Goal, *, max_iterations: int = 32) -> Optional[Decision]:
    """Main Cipher loop. Returns Decision on PASS, None if budget exhausted."""
    coordinator = Coordinator()
    verifier = Verifier()
    memory = Memory()

    for _ in range(max_iterations):
        if goal.completed:
            break

        tasks = coordinator.decompose(goal)
        agents = assign(tasks)
        results = run_agents(agents)
        memory.update(results)
        critique = red_team(results)
        decision = coordinator.evaluate(results, critique)

        if verifier.passed(decision):
            goal.completed = True
            return decision

        coordinator.replan()

    return None


if __name__ == "__main__":
    print("Cipher loop stub — wire Coordinator/Verifier before running goals.")
    print("See DESIGN.md for architecture and safety boundaries.")
