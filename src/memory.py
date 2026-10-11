"""Shared memory store: JSON files under memory/<run-id>/.

Layout:
  memory/<run-id>/plan.json              coordinator's plan + budget
  memory/<run-id>/findings.jsonl         append-only root-agent findings
  memory/<run-id>/state.json             current phase, retry count, pointers
  memory/<run-id>/notes.md               free-form shared notes
  memory/<run-id>/spawn_tree.json        parent -> children spawn records
  memory/<run-id>/spawns/<spawn-id>/findings.jsonl   per-sub-agent findings

Findings are append-only; corrections are new findings with a `supersedes`
field. Memory is the only cross-role channel: if it isn't in memory, it
didn't happen.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any


class MemoryStore:
    def __init__(self, root: Path, run_id: str) -> None:
        self.run_dir = root / "memory" / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        (self.run_dir / "spawns").mkdir(exist_ok=True)
        self.run_id = run_id

    # -- findings ---------------------------------------------------------
    def _findings_path(self, agent_id: str) -> Path:
        if agent_id in ("root", "", None):
            return self.run_dir / "findings.jsonl"
        d = self.run_dir / "spawns" / agent_id
        d.mkdir(parents=True, exist_ok=True)
        return d / "findings.jsonl"

    def append_finding(self, role: str, finding: dict, agent_id: str = "root") -> str:
        fid = f"{agent_id}-{int(time.time() * 1000)}-{abs(hash(json.dumps(finding, sort_keys=True))) % 10_000:04d}"
        record = {
            "id": fid,
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "role": role,
            "agent_id": agent_id,
            **finding,
        }
        with open(self._findings_path(agent_id), "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        return fid

    def read_findings(self, agent_id: str = "root") -> list[dict]:
        """Root agent sees all findings (root + every spawn). A sub-agent sees
        the root findings marked shareable plus its own — in practice the loop
        passes a context slice, so this returns root findings + own."""
        out: list[dict] = []
        root_path = self.run_dir / "findings.jsonl"
        if root_path.exists():
            out.extend(self._read_jsonl(root_path))
        if agent_id not in ("root", "", None):
            own = self._findings_path(agent_id)
            if own.exists():
                out.extend(self._read_jsonl(own))
        return out

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict]:
        out = []
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
        return out

    # -- plan / state / notes ---------------------------------------------
    def write_plan(self, plan: dict) -> None:
        self._write_json("plan.json", plan)

    def read_plan(self) -> dict:
        return self._read_json("plan.json", {})

    def write_state(self, state: dict) -> None:
        self._write_json("state.json", state)

    def read_state(self) -> dict:
        return self._read_json("state.json", {})

    def append_note(self, text: str) -> None:
        with open(self.run_dir / "notes.md", "a", encoding="utf-8") as f:
            f.write(text.rstrip() + "\n\n")

    def _write_json(self, name: str, obj: Any) -> None:
        with open(self.run_dir / name, "w", encoding="utf-8") as f:
            json.dump(obj, f, indent=2)

    def _read_json(self, name: str, default: Any) -> Any:
        p = self.run_dir / name
        if not p.exists():
            return default
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    # -- spawn tree ---------------------------------------------------------
    def record_spawn(self, record: dict) -> None:
        tree = self._read_json("spawn_tree.json", [])
        tree.append(record)
        self._write_json("spawn_tree.json", tree)

    def read_spawn_tree(self) -> list[dict]:
        return self._read_json("spawn_tree.json", [])

    def update_spawn(self, spawn_id: str, **fields: Any) -> None:
        tree = self._read_json("spawn_tree.json", [])
        for rec in tree:
            if rec.get("spawn_id") == spawn_id:
                rec.update(fields)
        self._write_json("spawn_tree.json", tree)

    # -- prompt context -------------------------------------------------------
    def context_summary(self, max_chars: int = 6000, agent_id: str = "root") -> str:
        findings = self.read_findings(agent_id=agent_id)
        lines = []
        for r in findings[-40:]:
            claim = r.get("claim") or r.get("summary") or r.get("decision") or ""
            ev = r.get("evidence") or ""
            lines.append(f"[{r.get('role')}/{r.get('agent_id')}] {str(claim)[:220]} | evidence: {str(ev)[:220]}")
        text = "\n".join(lines)
        if len(text) > max_chars:
            text = "...(truncated)...\n" + text[-max_chars:]
        return text or "(no findings yet)"
