# Cipher

**Cipher** is a multi-agent coding swarm: agents collaborate, disagree, investigate, and adapt until a goal is actually solved — not merely attempted.

This repo is a **GitHub-native reference architecture + runnable prototype** (repos, PRs, issues, Actions). It is not a hosted SaaS.

Source design notes: see `DESIGN.md` (full architecture).

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

The agents are **real LLM agents** (primary path): each role is an LLM call
whose system prompt is built from its spec in `agents/`, and which acts
through a ReAct tool loop — strict-JSON tool calls executed by the runtime
inside the sandbox, results fed back, bounded by a tool budget.

Agents get a role, goal, context, tools, memory, permissions, and a budget.
They can challenge the coordinator, reject each other's conclusions,
**spawn specialized sub-agents** (e.g. `test-writer`, `api-explorer`) when a
focused skill is needed, inspect shared work, retry, backtrack, and change
strategy — inside an authorized sandbox.

## Safety boundary (non-negotiable)

Aggressive persistence applies **only inside an authorized sandbox**.

Cipher never designs or directs agents to:

- Bypass security controls
- Steal credentials or private data
- Evade safeguards
- Break into systems
- Produce malware or unauthorized access tooling

"Cheat" means authorized rule-bending *inside the sandbox*:

- Try multiple approaches in parallel
- Challenge the coordinator
- Reject weak or unsupported conclusions
- Abandon failed approaches automatically
- Spawn specialized sub-agents
- Inspect each other's work
- Use every authorized tool
- Retry, backtrack, and replan
- Red-team assumptions
- Require evidence before declaring success

Elevated permissions are requested through normal channels — never worked around.

This boundary is enforced in code: see `src/tools.py` (command allowlist,
sandbox-rooted file access, secret-pattern rejection, no network tooling)
and the agent specs in `agents/`.

## Workspace layout

```
/cipher
  README.md       # this file
  DESIGN.md       # architecture, loop, tools, memory, spawn model
  /agents/        # role specs (coordinator, research, builder, analyst, critic, verifier)
  /tasks/         # task schema + instance files
  /memory/        # findings, state, shared notes, spawn tree
  /artifacts/     # deliverables produced by agents
  /logs/          # run logs
  /tests/         # verifier evidence & unit tests
  /src/           # Python runtime (loop, tools, LLM client, spawn runtime)
```

## How to run

Python 3 stdlib only — no dependencies.

**Real agents (primary path):**

```bash
export CIPHER_API_KEY=...          # OpenAI-compatible Chat Completions key
# optional: CIPHER_API_BASE (default https://api.openai.com/v1)
# optional: CIPHER_MODEL    (default gpt-4o-mini)
python -m src.loop --goal "Write a fizzbuzz program to artifacts/fizzbuzz.py"
python -m src.loop --task tasks/example-hello-task.json
```

The key is sent only as an HTTPS Bearer header. It is never logged,
printed, persisted to files, or written to memory/logs.

**Dry-run (no key):** deterministic stub agents use the same tool belt,
spawn tree, and verifier, so the pipeline is genuinely exercised — only the
"thinking" is stubbed. Selected automatically when no key is set, or forced:

```bash
CIPHER_DRY_RUN=1 python -m src.loop --task tasks/example-hello-task.json
```

Until auth and packaging land:

1. Read `DESIGN.md` and the role specs in `agents/`.
2. Drop a goal into `tasks/` using the schema in `tasks/README.md`.
3. Run `python -m src.loop --task tasks/<your-task>.json`.
4. Agents write findings to `memory/`, artifacts to `artifacts/`, evidence to `tests/`.
5. Critic → Verifier → **PASS** deliver / **FAIL** replan.

## Status

- [x] Workspace scaffold
- [x] Design doc + role specs (+ strict JSON response contracts)
- [x] Real-agent runtime: stdlib LLM client, ReAct tool loop, spawn/sub-agent runtime
- [x] Dry-run stub mode — **verified end-to-end** (example task PASSES, spawn tree exercised)
- [x] Unit tests — **verified** (`python -m unittest discover -s tests`: 29 tests pass)
- [ ] Live LLM run — **not yet verified** (no API key in this environment); the live path is code-reviewed but untested against a real endpoint
- [ ] GitHub repo + CI (`git push` pending account connection)
- [ ] First end-to-end goal run with real agents
