"""Acceptance tests for the Cipher design-doc outline (T-001).

User lock: Verifier PASS requires real executable tests — not LLM judgment alone.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUTLINE = ROOT / "artifacts" / "design-doc-outline.md"
TASKS_README = ROOT / "tasks" / "README.md"
EVIDENCE_DIR = ROOT / "tests" / "evidence"


@pytest.fixture(scope="module")
def outline_text() -> str:
    assert OUTLINE.is_file(), f"missing outline: {OUTLINE}"
    return OUTLINE.read_text(encoding="utf-8")


def test_outline_has_safety_section(outline_text: str) -> None:
    assert "## 0. Safety boundary" in outline_text
    for phrase in (
        "Bypass security",
        "Steal credentials",
        "Evade safeguards",
        "Break into systems",
    ):
        assert phrase in outline_text


def test_outline_b4_sandbox_venues_stub(outline_text: str) -> None:
    assert "### 0.1 Operational sandbox stub" in outline_text
    assert "Box worktree" in outline_text
    assert "GH Actions runner" in outline_text
    assert "Forbidden" in outline_text


def test_outline_user_lock_real_tests(outline_text: str) -> None:
    assert "### 0.4 User product lock" in outline_text
    assert "No Verifier PASS on LLM judgment alone" in outline_text
    assert "LLM-only PASS is **banned**" in outline_text or "LLM-only PASS" in outline_text


def test_outline_b1_evidence_schema(outline_text: str) -> None:
    assert "### 3.0 Evidence schema" in outline_text
    assert "tests/evidence/<task_id>.yaml" in outline_text
    assert "git_sha" in outline_text
    assert "ci_run_url" in outline_text
    assert "log_path" in outline_text
    assert "HARD — user lock" in outline_text or "User product lock" in outline_text


def test_outline_b2_github_manual_vs_automated(outline_text: str) -> None:
    assert "v0 manual" in outline_text
    assert "v0.5 automated" in outline_text
    assert "GitHub App" in outline_text
    assert "**Reject**" in outline_text  # autonomous merge


def test_outline_b3_status_enum(outline_text: str) -> None:
    for status in ("pending", "claimed", "running", "blocked", "done", "abandoned"):
        assert f"`{status}`" in outline_text or status in outline_text


def test_tasks_readme_status_enum_matches() -> None:
    text = TASKS_README.read_text(encoding="utf-8")
    for status in ("pending", "claimed", "running", "blocked", "done", "abandoned"):
        assert status in text, f"tasks/README missing status {status}"


def test_outline_r1_verifier_only_verified(outline_text: str) -> None:
    assert "only Verifier" in outline_text or "Only Verifier" in outline_text
    assert "verified: yes" in outline_text or "`verified: yes`" in outline_text


def test_outline_vs_copilot_table(outline_text: str) -> None:
    assert "vs Copilot" in outline_text or "### 1.3 vs Copilot" in outline_text


def test_outline_forbidden_git_and_spawn(outline_text: str) -> None:
    assert "force" in outline_text.lower()
    assert "--no-verify" in outline_text
    assert "spawn depth" in outline_text.lower() or "v0 spawn depth" in outline_text


def test_evidence_schema_example_parses() -> None:
    """Schema example file must exist and be machine-checkable YAML."""
    example = EVIDENCE_DIR / "SCHEMA.example.yaml"
    assert example.is_file(), "missing tests/evidence/SCHEMA.example.yaml"
    data = yaml.safe_load(example.read_text(encoding="utf-8"))
    for key in ("task_id", "git_sha", "paths", "commands", "exit_codes", "checked_at"):
        assert key in data
    assert data.get("ci_run_url") or data.get("log_path")
