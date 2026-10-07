# Tests / evidence

Verifier looks here for proof: unit tests, checklists, golden files, command transcripts.

No PASS without evidence linked from the verdict.

## Run locally

```bash
cd /workspace/cipher
python3 -m venv .venv          # once
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
# or: python -m pytest -q  (if pytest on PATH / venv active)
```

`pyproject.toml` sets `pythonpath = ["src"]` so imports resolve without install.

## Current suite

- `tests/test_loop.py` — Goal/Task/Decision defaults, Memory.update, Verifier empty-evidence → False, stub NotImplementedError contracts, `run()` early paths
- `tests/test_tools.py` — TOOL_NAMES, ToolRegistry allowlist/KeyError, tool body stubs

Transcript for Verifier: `logs/pytest-2026-10-07.txt` (copy: `artifacts/pytest-transcript.txt`)
