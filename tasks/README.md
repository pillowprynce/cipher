# Tasks

Task records live here. The Coordinator creates and updates them; specialists mark progress.

## Schema

Minimal fields (YAML or Markdown front matter + body):

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Stable id, e.g. `T-001` |
| `goal` | string | What done looks like for this slice |
| `assignee` | string | Role or agent id (`research`, `builder`, …) |
| `status` | enum | `pending` \| `claimed` \| `running` \| `blocked` \| `done` \| `abandoned` |
| `deps` | list[string] | Task ids that must be `done` first |

Optional: `budget`, `permissions`, `created`, `updated`, `notes`, `artifacts[]`, `evidence[]` (required before Verifier).

## Example

```yaml
id: T-001
goal: Survey prior art on multi-agent coding swarms; note 5 systems and tradeoffs.
assignee: research
status: pending
deps: []
budget: medium
```

```markdown
# T-001

Survey prior art...

## Notes
- (agent fills during run)
```

## Lifecycle

1. Coordinator decomposes goal → writes tasks with `deps`
2. `assign()` marks `assignee` + `claimed` (or immediately `running`) — this is the v0 claim mechanism
3. Agent updates notes / links artifacts
4. On success → `done`; on dead end → `abandoned` (Coordinator replans)
5. Critic/Verifier read completed tasks + memory before verdict

## Conventions

- One concern per task when possible
- Prefer parallel independent tasks (authorized “cheat”: multiple approaches)
- Abandon failed approaches explicitly—do not leave zombie `running` tasks
