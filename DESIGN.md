# Cipher — Design Document

## 1. Goal

A multi-agent coding swarm that solves a goal rather than merely attempting
it: agents collaborate, disagree, investigate, and adapt. When a verifier
cannot confirm success with evidence, the swarm backtracks and replans
instead of declaring victory. Agents are **real LLM agents**; deterministic
stubs exist only for keyless dry-runs.

## 2. Agent loop (phase machine)

The coordinator drives every run through these phases:

```
PLAN        coordinator turns the goal + task schema into a plan and budget
RESEARCH    research gathers facts (reads files, searches memory, inspects the sandbox)
BUILD       builder produces or modifies artifacts (code, docs, configs)
ANALYZE     analyst inspects what was built (read, run, measure) and records findings
CRITIQUE    critic / red-team tries to break it: challenges assumptions,
            rejects weak conclusions, re-runs claims against evidence
VERIFY      verifier checks success_criteria with evidence and returns PASS or FAIL
REVISE      on FAIL: coordinator replans (backtrack to BUILD or ANALYZE,
            possibly RESEARCH), consuming retry budget
DONE        on PASS: deliver artifacts + evidence; on exhausted budget: fail loudly
```

Loop invariant: **no phase may declare success without evidence the
verifier can independently re-check.** A phase output is a structured record
(goal, claims, evidence paths, confidence). Opinions without evidence are
rejected at CRITIQUE.

### Phase transitions

| From     | To       | Trigger                                   |
|----------|----------|-------------------------------------------|
| PLAN     | RESEARCH | plan accepted by coordinator              |
| RESEARCH | BUILD    | findings recorded in memory               |
| BUILD    | ANALYZE  | artifacts written                         |
| ANALYZE  | CRITIQUE | findings recorded                         |
| CRITIQUE | VERIFY   | critique addressed or waived by coordinator|
| VERIFY   | DONE     | PASS → deliver                            |
| VERIFY   | REVISE   | FAIL → retry if budget remains            |
| REVISE   | RESEARCH | plan changed strategy                     |
| REVISE   | BUILD    | same strategy, new attempt                |
| REVISE   | DONE     | budget exhausted → FAILED run             |

`max_retries` bounds the loop. The prototype counts a retry each time VERIFY
returns FAIL; when retries are exhausted the run ends FAILED and the log
records why. The loop always terminates: retries are finite, and each phase
is a bounded function call.

## 3. Real agents: LLM calls + ReAct tool loop

Each role executes as an LLM call (`src/agents.py::run_role_live`):

1. **System prompt** is built from the role's spec file (`agents/<role>.md`)
   plus the safety boundary, the tool list, the ReAct protocol, and the
   role's strict JSON response contract (`src/roles.py`).
2. **User message** carries the task goal, context, constraints, the phase
   instruction, and a shared-memory summary.
3. **ReAct loop**: the model must reply with exactly one strict JSON object
   per turn — either
   `{"type": "tool_call", "tool": "<name>", "args": {...}}` or
   `{"type": "final", "result": {...}}`.
   The runtime executes the tool inside the sandbox and returns
   `{"tool": "<name>", "result": {...}}` (or an error object on denial).
   Bounded by `max_tool_iterations` (`CIPHER_MAX_TOOL_ITERS`).
4. **Strict JSON contract**: the final result must contain the role's
   contract keys (defined in `agents/roles.yaml`, e.g. verifier →
   `results/verdict/reasons`). Malformed output gets **one** re-prompt naming
   the problem; a second failure raises `AgentError` and fails loudly.
5. The LLM client (`src/llm.py`) is stdlib-only (`urllib`) against an
   OpenAI-compatible Chat Completions endpoint. Config (`src/config.py`):
   `CIPHER_API_KEY` (key, never logged/persisted), `CIPHER_API_BASE`,
   `CIPHER_MODEL` (default `gpt-4o-mini`), `CIPHER_TIMEOUT_S`,
   `CIPHER_JSON_MODE`.

**Dry-run fallback:** when `CIPHER_DRY_RUN=1` or no key is set, deterministic
stub agents run instead. Stubs use the *same* tool belt, spawn runtime,
memory, and verifier — only the reasoning is stubbed — so dry-run genuinely
exercises the pipeline.

## 4. Role contracts

Each role has a spec in `agents/<role>.md` and an entry in
`agents/roles.yaml`. The contract for every role:

- **Goal**: what this role is optimizing for.
- **Inputs**: which prior phases' outputs it may read (via shared memory).
- **Outputs**: structured records it must write (claims + evidence).
- **Tools**: subset of the tool allowlist it may use.
- **Challenge rules**: whose conclusions it may reject, and how a rejection
  is recorded (a rejection is itself a finding with evidence, not a veto).
- **Response contract**: required keys of the final JSON result.

Roles in the pipeline:

| Role        | Job                                              |
|-------------|--------------------------------------------------|
| coordinator | plans, budgets, spawns specialists, resolves disputes, replans |
| research    | gathers facts, reads code, summarizes context    |
| builder     | writes/modifies artifacts                        |
| analyst     | inspects artifacts, runs them, records findings  |
| critic      | red-teams assumptions, rejects weak claims       |
| verifier    | checks success_criteria against evidence: PASS/FAIL |

### Challenge rules (who may reject whom)

- critic may reject research, builder, analyst conclusions (with evidence).
- verifier may reject any phase's claims (with a failed check).
- any role may challenge the coordinator's plan; the coordinator must
  record the challenge and either amend the plan or justify keeping it.
- builder may not reject verifier results; it may only produce new evidence.

## 5. Spawning specialized sub-agents

Any role whose `tools_allowed` includes `spawn_subagent` (coordinator,
research, builder, analyst) may spawn specialists — e.g. `test-writer`,
`api-explorer`, `optimizer` — when a sub-goal needs focused effort or a
distinct ability.

### Spawn request

```json
{
  "specialist": "test-writer",
  "goal": "narrow sub-goal in one or two sentences",
  "tools": ["write_file", "run_cmd"],
  "max_tool_iterations": 6,
  "context": "relevant memory slice for the child (not whole memory)"
}
```

### Specialist system prompt

Generated per spawn (`src/roles.py::build_specialist_prompt`):

- base agent contract (solve only the narrow goal; record findings;
  parent inspects/accepts/rejects/retries),
- the safety boundary (same non-negotiable text),
- specialist name + narrow goal + parent-provided context slice,
- the granted tool subset,
- the ReAct protocol and the specialist result contract
  `{summary, outputs, evidence}`.

### Hierarchy & tracking

- The runtime (`src/loop.py::SpawnRegistry`) tracks a **spawn tree**:
  `memory/<run-id>/spawn_tree.json` records every spawn
  (`spawn_id`, `parent_id`, `specialist`, `goal`, `depth`, `tools`,
  `tool_budget`, `status`).
- Sub-agent findings are namespaced:
  `memory/<run-id>/spawns/<spawn-id>/findings.jsonl`. The parent reads them
  via shared memory and records accept / reject / retry as findings —
  the same challenge rules as top-level agents.
- The run log prints the full spawn tree at the end of the run.

### Budget & limits (enforced, not advisory)

| Limit | Default | Env override |
|---|---|---|
| Max spawn depth (root = 0) | 2 | `CIPHER_MAX_SPAWN_DEPTH` |
| Max sub-agents per run | 8 | `CIPHER_MAX_SUBAGENTS` |
| Max tool iterations per specialist | 8 | `CIPHER_MAX_SPECIALIST_ITERS` |

- A child's tool budget is **carved out of the parent's remaining budget**
  (`min(requested, parent_remaining, cap)`) and debited up front.
- A spawn that would exceed depth or total limits is refused with
  `ToolDenied`; the parent sees the refusal as a tool error and adapts.
- **No permission escalation, ever**: requested tools must be a subset of
  the parent's `tools_allowed`, else refused.
- **Recursion guard**: a `(specialist, goal)` pair may not repeat within one
  ancestor chain (blocks A→B→A ping-pong); combined with the depth limit,
  unbounded recursion is impossible.

## 6. Shared memory model

All state lives in JSON files under `memory/`, namespaced by run id:

```
memory/<run-id>/
  plan.json        # coordinator's plan + budget
  findings.jsonl   # append-only: every role's structured findings
  state.json       # current phase, retry count, artifact pointers
  notes.md         # free-form shared notes
  spawn_tree.json  # parent -> children spawn records
  spawns/<id>/findings.jsonl   # per-sub-agent findings
```

`findings.jsonl` is append-only; nothing is deleted. Corrections are new
findings that supersede old ones (each finding has an `id` and optional
`supersedes` field). `src/memory.py` implements this store.

Memory is the *only* cross-role communication channel. Agents never share
hidden state; if it isn't in memory, it didn't happen.

## 7. Task schema

Tasks are JSON files validated against `tasks/schema.json` (`src/tasks.py`):

- `id`: unique task id
- `goal`: the goal statement
- `context`: background the agents should know
- `constraints`: hard limits (e.g. "stdlib only", "no network")
- `budget`: `{ "max_retries": N, "max_steps": N }`
- `success_criteria`: list of checkable criteria, each with an `id`,
  `description`, and `evidence` (how the verifier proves it)

See `tasks/README.md` and `tasks/example-hello-task.json`.

## 8. Tools available to agents

Implemented in `src/tools.py`. Every tool is sandbox-scoped to the repo
root (`SANDBOX_ROOT`): relative paths resolve under it, absolute paths and
`..` escapes are rejected.

- `read_file(path)` / `write_file(path, content)` — file IO inside the sandbox
- `list_dir(path)` — directory listing inside the sandbox
- `run_cmd(argv)` — shell exec, **allowlist only**: `python3`, `python`,
  `pytest`, `ls`, `cat`, `grep`, `git` (read-only subcommands: `status`,
  `diff`, `log`, `show`, `rev-parse`). Blocked: anything matching
  credential/secret patterns in arguments, shell metacharacters / `$(`
  subshell syntax, any path outside the sandbox. Never `shell=True`.
- `memory_append(finding)` / `memory_read()` — via `src/memory.py`
- `spawn_subagent(spec)` — spawn a specialist (see §5); granted only to
  roles with `can_spawn: true`
- `check_evidence(criterion)` — deterministic `file_exists` / `command`
  evaluation, for the verifier
- No network tools exist. There is deliberately no HTTP client, no socket
  access, and no credential store. Agents cannot exfiltrate because there is
  no channel.

The allowlist is enforced at the point of execution, not by convention.
Unknown or unpermitted calls raise `ToolDenied`, which is returned to the
agent as a tool error so it can adapt. Denials are logged.

## 9. Budget / permission model

Each run gets a budget from the task: `max_retries` (VERIFY→REVISE cycles)
and `max_steps` (total phase executions). The coordinator allocates effort
across phases; when the budget is exhausted the run fails loudly with a
recorded reason. Permissions are per-role tool subsets (see
`agents/roles.yaml`); requesting more than your subset raises `ToolDenied`
and is logged. Spawn budgets are carved from parents (§5).

## 10. Verifier pass/fail criteria and evidence

The verifier evaluates each `success_criteria` entry:

1. For each criterion, run its `evidence` check (a file to exist, a test to
   pass, a command whose output must match) — via `check_evidence` or
   equivalent tool calls it performs itself.
2. The runtime writes per-criterion results to `tests/evidence-<run-id>.json`
   (see `tests/evidence-example.json` for the shape).
3. PASS only if **every** criterion passes. Partial credit does not exist.
4. On FAIL, the verifier records *which* criterion failed and *what the
   evidence showed* — this is what REVISE plans against.
5. **Independent re-check**: the loop re-runs every criterion itself with
   `check_criterion`. A verifier PASS stands only if this also passes —
   the verifier cannot be gamed by a persuasive but false report.

Evidence must be reproducible: re-running the check must give the same
result. The verifier never trusts a role's claim; it re-runs the check
itself.

## 11. Failure handling: revise / retry / backtrack

On FAIL the coordinator receives the verifier's failure report and chooses:

- **Retry**: same plan, new attempt (e.g. builder fixes a bug) → back to BUILD.
- **Backtrack**: the plan's assumptions were wrong → back to RESEARCH with
  the failure as new context.
- **Replan**: change strategy → new plan, back to RESEARCH.
- **Abort**: budget exhausted or failure is out of scope → FAILED run.

Each choice is recorded in memory with its rationale. In live mode the
coordinator makes this decision as an LLM call with a strict
`{decision, target_phase, rationale}` contract; in dry-run it retries BUILD.

## 12. Safety enforcement summary

- Tools are allowlisted and sandbox-rooted (`src/tools.py`); secrets-looking
  arguments and shell metacharacters are rejected.
- No network, no credentials, no exfiltration channel exists in the tool belt.
- Spawned specialists inherit the sandbox and can never escalate beyond
  their parent's permissions.
- Every role spec restates the safety boundary; the coordinator rejects any
  plan step that requires leaving the sandbox.
- The API key (live mode) travels only as an HTTPS header; it is never
  logged, printed, persisted, or written to memory.
- Logs record every denied tool call and refused spawn.
- This prototype runs locally on the operator's own machine — the "sandbox"
  is the repo working copy. Real deployments must add OS-level isolation
  (containers, seccomp) before running untrusted goals.

## 13. Verification status

- **Verified**: dry-run end-to-end (example task PASSES; coordinator spawns a
  `test-writer` specialist; spawn tree recorded; verifier + independent
  evidence check agree), and 29 stdlib unit tests
  (`python -m unittest discover -s tests`).
- **Not verified**: the live LLM path (no API key in this environment). It is
  code-reviewed: prompt construction, ReAct parsing, one-retry malformed
  handling, budget bounds, and key hygiene were all inspected, but no call
  has been made against a real endpoint yet.
