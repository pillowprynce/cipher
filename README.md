# Cipher

**Cipher** is a multi-agent coding swarm: agents collaborate, disagree, investigate, and adapt until a goal is *actually* solved—not merely attempted.

This repo is a **GitHub-native reference architecture + runnable prototype** (repos, PRs, issues, Actions). It is not a hosted SaaS.

Source design notes: see `../cipher-copilot-share.md` (Copilot share summary) and [`DESIGN.md`](./DESIGN.md).

---

## What Cipher does

```
GOAL → COORDINATOR → RESEARCH / BUILDER / ANALYST
                 ↓
           SHARED MEMORY
                 ↓
         CRITIC / RED TEAM
                 ↓
             VERIFIER
            ↙        ↘
       FAILED       PASSED
     revise/retry   deliver
```

Agents get a role, goal, context, tools, memory, permissions, and budget. They can challenge the coordinator, reject each other's conclusions, spawn specialized sub-agents, inspect shared work, retry, backtrack, and change strategy—inside an authorized sandbox.

---

## Safety boundary (non-negotiable)

**Aggressive persistence applies only inside an authorized sandbox.**

Cipher **never** designs or directs agents to:

- Bypass security controls
- Steal credentials or private data
- Evade safeguards
- Break into systems
- Produce malware or unauthorized access tooling

**“Cheat” means authorized rule-bending inside the sandbox:**

- Try multiple approaches in parallel
- Challenge the coordinator
- Reject weak or unsupported conclusions
- Abandon failed approaches automatically
- Spawn specialized sub-agents
- Inspect each other’s work
- Use every *authorized* tool
- Retry, backtrack, and replan
- Red-team assumptions
- Require evidence before declaring success

Elevated permissions are requested through normal channels—not worked around.

---

## Product decisions (locked)

| Decision | Choice |
|----------|--------|
| Surface | GitHub-native first (repos, PRs, issues, Actions) |
| Shape | Reference architecture + runnable prototype (not SaaS yet) |
| Safety | Aggressive only within authorized scope |

---

## Workspace layout

```
/cipher
  README.md       # this file
  DESIGN.md       # architecture, loop, tools, memory model
  /agents/        # role specs (coordinator, research, builder, analyst, critic, verifier)
  /tasks/         # task schema + instance files
  /memory/        # findings, state, shared notes
  /artifacts/     # deliverables produced by agents
  /logs/          # run logs
  /tests/         # verifier evidence & unit tests
  /src/           # Python runtime sketch (loop, tools)
```

---

## How to run (later)

Prototype runtime is under `src/`. Planned entrypoint (not wired yet):

```bash
# from repo root once dependencies exist
python -m cipher.src.loop --goal "…"
# or, after package install:
# cipher run --goal "…"
```

Until auth and packaging land:

1. Read [`DESIGN.md`](./DESIGN.md) and role specs in [`agents/`](./agents/).
2. Drop a goal into `tasks/` using the schema in [`tasks/README.md`](./tasks/README.md).
3. Agents write findings to `memory/`, artifacts to `artifacts/`, evidence to `tests/`.
4. Critic → Verifier → PASS deliver / FAIL replan.

GitHub push is pending account connection; scaffold lives on the box under `/workspace/cipher`.

---

## Status

- [x] Workspace scaffold
- [x] Design doc + role specs
- [x] Loop / tools stubs
- [ ] Wire real coordinator runtime
- [ ] GitHub repo + CI
- [ ] First end-to-end goal run
