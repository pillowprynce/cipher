# Cipher Design

Architecture distilled from the Copilot share summary  
[`../cipher-copilot-share.md`](../cipher-copilot-share.md)  
(share id `406c5226-41a4-8490-a851-fe46645d00d6`), plus locked product answers.

---

## 1. Goal

Cipher is a multi-agent system where agents **collaborate, disagree, investigate, and adapt** until a goal is accomplished. The system keeps trying until the goal is *solved*, not just attempted.

---

## 2. Safety

### Hard boundaries

Aggressive and persistent **inside an authorized sandbox only**. Cipher does **not**:

- Bypass security
- Steal credentials or data
- Evade safeguards
- Break into systems

Otherwise the swarm becomes a “tiny digital felony factory”—we refuse that path.

### “Cheating” (authorized sandbox rule-bending)

| Allowed inside sandbox | Forbidden |
|------------------------|-----------|
| Parallel approaches | Unauthorized access |
| Challenge coordinator | Credential/data theft |
| Reject other agents’ conclusions | Evading safeguards |
| Abandon failed approaches | Malware / break-ins |
| Spawn specialized sub-agents | Unlimited unrestricted tools |
| Inspect each other’s work | Working around permission channels |
| Use all *authorized* tools | |
| Retry / backtrack / replan | |
| Red-team weaknesses | |
| Verifier demands evidence | |

Elevated access: request through proper channels, never work around.

Tools are exposed only through a **controlled interface** (see §6).

---

## 3. Architecture pipeline

```
                         ┌──────────────┐
                         │    GOAL      │
                         └──────┬───────┘
                                │
                       ┌────────▼────────┐
                       │   COORDINATOR   │
                       │ decomposes goal │
                       └────────┬────────┘
                                │
             ┌──────────────────┼──────────────────┐
             ▼                  ▼                  ▼
       ┌──────────┐       ┌──────────┐       ┌──────────┐
       │ RESEARCH │       │ BUILDER  │       │ ANALYST  │
       │  AGENT   │       │  AGENT   │       │  AGENT   │
       └────┬─────┘       └────┬─────┘       └────┬─────┘
            │                  │                  │
            └──────────────────┼──────────────────┘
                               ▼
                      ┌─────────────────┐
                      │ SHARED MEMORY   │
                      │ findings/tools/ │
                      │ artifacts/state │
                      └────────┬────────┘
                               │
                    ┌──────────▼──────────┐
                    │   CRITIC / RED TEAM │
                    │ attacks assumptions │
                    └──────────┬──────────┘
                               │
                         ┌─────▼─────┐
                         │ VERIFIER  │
                         └─────┬─────┘
                               │
                 ┌─────────────┴─────────────┐
                 │                           │
              FAILED                      PASSED
                 │                           │
                 ▼                           ▼
          revise / retry                 deliver
```

Role specs live in [`agents/`](./agents/).

---

## 4. Six core components

### 4.1 Coordinator

**Flow:** Goal → tasks → agents → dependencies → final decision.

Responsibilities:

- Decompose the goal into tasks with dependencies
- Assign agents (and budgets/permissions)
- Evaluate results + critique
- Replan on verifier FAIL
- May be challenged by other agents

See [`agents/coordinator.md`](./agents/coordinator.md).

### 4.2 Agent runtime

Every agent instance receives:

| Field | Meaning |
|-------|---------|
| `role` | Spec identity (research, builder, …) |
| `goal` | Current objective slice |
| `context` | Relevant memory / task deps |
| `tools` | Authorized tool set |
| `memory` | Read/write to shared workspace |
| `permissions` | Scope of allowed actions |
| `budget` | Steps, tokens, or wall-clock cap |

### 4.3 Shared workspace

```
/cipher
  /agents      # role specs
  /tasks       # task records
  /memory      # findings + state
  /artifacts   # deliverables
  /logs        # run history
  /tests       # evidence for verifier
```

### 4.4 Tool system

Agents do **not** get unlimited capabilities. Controlled interface (stubs in [`src/tools.py`](./src/tools.py)):

- `web_search()`
- `read_file()`
- `write_file()`
- `run_test()`
- `run_code()`
- `inspect_repo()`
- `create_agent()`

### 4.5 Debate / verification

For important decisions:

1. Agent A — proposal  
2. Agent B — criticism  
3. Agent C — alternative  
4. Agent D — evidence check  
5. Coordinator — decision  
6. Verifier — PASS / FAIL  

A verifier **refuses to declare success without evidence**.

### 4.6 Execution loop

Canonical loop (implemented as a stub in [`src/loop.py`](./src/loop.py)):

```python
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
```

---

## 5. Product decisions (locked)

| Question (from Copilot) | Answer |
|-------------------------|--------|
| GitHub-native vs general-purpose? | **GitHub-native first** (repos, PRs, issues, Actions) |
| Framework / service / reference? | **Reference architecture + runnable prototype** (not SaaS yet) |
| Aggressive only in authorized scope? | **Yes** |
| Elevated perms via proper channels? | **Yes** |

---

## 6. Memory model (starter)

| Path | Purpose |
|------|---------|
| `memory/findings.md` | Durable research / analysis notes |
| `memory/state.md` | Current goal, phase, open questions |
| `artifacts/` | Built outputs |
| `logs/` | Per-run traces |
| `tests/` | Verifier evidence |

Handoff format (suggested):  
`goal → findings → artifact → critique → verdict`

---

## 7. Task schema (summary)

See [`tasks/README.md`](./tasks/README.md). Minimal fields: `id`, `goal`, `assignee`, `status`, `deps`.

---

## 8. Open work

- Wire coordinator runtime to real agent teammates / LLM backends
- GitHub repo creation + Actions CI once auth is ready
- First end-to-end goal through the loop
- ADRs for memory concurrency and tool permissioning

---

## 9. Notable quotes (from share)

- “Otherwise your swarm becomes less ‘coding agent’ and more ‘tiny digital felony factory.’”
- “A verifier refuses to declare success without evidence.”
- “Agents shouldn’t directly get unlimited capabilities. Give them tools through a controlled interface.”
- “The system keeps trying until the goal is actually solved, not just attempted.”
