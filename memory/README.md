# Shared memory

Durable swarm state. All agents may read; write according to role permissions.

| File | Purpose |
|------|---------|
| `findings.md` | Research, analysis, critique excerpts |
| `state.md` | Current goal, phase, open questions, last verdict |
| (future) | Structured JSON/SQLite if concurrency demands it |

Handoff pattern: **goal → findings → artifact → critique → verdict**
