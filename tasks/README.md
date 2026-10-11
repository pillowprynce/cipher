# tasks/

Task instances are JSON files validated against `schema.json` (see
`src/tasks.py`). Drop a goal here, then run:

```bash
python -m src.loop --task tasks/<your-task>.json
```

## Schema

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Unique task id |
| `goal` | yes | The goal statement agents work toward |
| `context` | no | Background the agents should know |
| `constraints` | no | Hard limits, e.g. `["stdlib only", "no network"]` |
| `budget` | no | `{"max_retries": N, "max_steps": N}` (defaults from env/config) |
| `success_criteria` | yes | Non-empty list of checkable criteria |

Each success criterion:

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Criterion id |
| `description` | yes | Human-readable description |
| `type` | yes | `file_exists` or `command` |
| `path` | for `file_exists` | Relative path that must exist |
| `cmd` | for `command` | argv list to run in the sandbox |
| `expect_in_output` | no | Substring that must appear in stdout+stderr |
| `expect_exit_code` | no | Expected exit code (default 0) |

The verifier checks every criterion; the loop independently re-runs every
check before accepting a PASS. There is no partial credit.
