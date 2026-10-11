# memory/

Shared agent memory. The **only** cross-role communication channel: if it
isn't in memory, it didn't happen.

Per run (`memory/<run-id>/`):

| File | Written by | Contents |
|---|---|---|
| `plan.json` | coordinator | plan + budget |
| `findings.jsonl` | all roles | append-only structured findings (`claim` + `evidence`) |
| `state.json` | loop | current phase, retry count, run id |
| `notes.md` | any role | free-form shared notes |
| `spawn_tree.json` | runtime | parent → children spawn records |
| `spawns/<spawn-id>/findings.jsonl` | sub-agents | findings namespaced by spawn id |

Findings are append-only; corrections are new findings with a `supersedes`
field. Implemented in `src/memory.py`.
