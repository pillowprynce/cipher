# Findings

_Append-only notes from Research, Analyst, and Critic. Cite sources; mark confidence._

## Template entry

```
### YYYY-MM-DD — <agent> — <topic>
- Claim:
- Evidence:
- Confidence: low|medium|high
- Open questions:
```

## Seed (from Copilot share)

- Cipher goal: collaborate / disagree / investigate / adapt until goal is *solved*.
- Safety: aggressive inside authorized sandbox only; no security bypass, credential theft, safeguard evasion, or break-ins.
- “Cheat” = parallel approaches, challenge coordinator, reject bad conclusions, spawn sub-agents, backtrack, red-team, evidence-gated verify.
- Product: GitHub-native first; reference architecture + runnable prototype.
- See `../cipher-copilot-share.md` and `../DESIGN.md`.

### 2026-10-07 — Swarm Watch — 2026 papers informing DESIGN.md
- Claim: Coding swarms scale better with shared checked context + explicit task claiming than with a single coordinator as the only merge path; what breaks at scale is integration (merge conflicts, many agents fixing the same bug, new code breaking old).
- Evidence:
  - [Agensh](https://arxiv.org/abs/2609.26781) (Sep 2026, MSR): up to 1,024 identical coding agents, no central coordinator; shared Gitea PRs + chat + append-only notes board. Pandoc test pass 33.89%→55.06% from 1→1,024 agents; agents spontaneously formed integrator/reviewer roles. Code link was 404; project page https://agens-harness.github.io/project/
  - [DeLM](https://arxiv.org/abs/2606.10662) (Jun 2026): agents pull tasks from a queue; shared context holds only *checked* results. +≤10.5pp on SWE-bench Verified, ~50% lower cost. Open source: https://github.com/yuzhenmao/DeLM
  - [STORM](https://arxiv.org/abs/2605.20563) (May 2026): shared workspace routes edits so conflicts are caught at write time vs late git-worktree merges. +18.7 Commit0-Lite over worktree baseline. Open source: https://github.com/dreamyang-liu/STORM
  - [Parallel Claudes C compiler](https://www.anthropic.com/engineering/building-c-compiler) (Feb 2026): task claim via lock files in git; frequent merge conflicts; on one giant task agents all fixed the same bug and overwrote each other — needed a known-good reference (GCC) + CI. Repo: https://github.com/anthropics/claudes-c-compiler
  - [Anthropic multiagent patterns](https://www.anthropic.com/research/multiagent-systems) (Aug 2026): shared-codebase PR conflict/abandonment; bandwidth contention (2.4M requests / 117 accepted) when agents compete for a scarce resource.
- Implications for Cipher DESIGN (esp. §4.3 shared workspace, §8 ADR for memory concurrency):
  1. Keep findings append-only and prefer *verified* entries in the context agents read (DeLM pattern) — aligns with Verifier evidence gate.
  2. Add explicit task claiming (lock file or status=claimed) before Builder/Research run in parallel, to avoid same-bug overwrite.
  3. Prefer one shared workspace / conflict-at-write for code edits (STORM) over many divergent checkouts if multi-Builder is planned.
  4. Coordinator should replan and assign roles, but not be the only merge bottleneck; Verifier + tests/CI as the real gate (matches current pipeline).
  5. Budget scarce tools (rate limits, GPU, Actions minutes) or agents will flood them.
- Confidence: high for paper claims (primary sources checked Oct 5 2026); medium for Cipher mapping (design recommendation, not yet empirically validated in-repo).
- Open questions: Does Cipher stay coordinator-centric, or evolve toward DeLM/Agensh-style pull queues for coding subtasks? ADR needed for memory write concurrency.

### 2026-10-07 — Research — Prior art brief for Cipher design-doc pipeline
_Coordinator kickoff (design-doc pipeline). No formal task id assigned; Research executed on Coordinator message. Sources fetched/searched 2026-10-07 CT._

#### (1) Prior art — multi-agent coding systems (high-level)

##### Microsoft AutoGen → AG2 / Microsoft Agent Framework
- **What:** AutoGen pioneered multi-agent chat/orchestration at Microsoft Research; GitHub marks AutoGen in **maintenance mode** and steers new work to **Microsoft Agent Framework (MAF)** workflows. Community fork **AG2** continues the AutoGen lineage (`ag2` package + AG2 Classic for `import autogen`).
- **Orchestration:** AutoGen/AgentChat: two-agent chat, group chat, nested chats. AG2 v1: Hub + typed channels (Network) replacing GroupChat/swarms. MAF: graph Workflows — sequential, concurrent, handoff, group-chat, Magentic (manager coordinates specialists); tool-approval / human-in-the-loop pauses.
- **Memory / tools / verification:** Tool use + middleware/guardrails in MAF; context providers for memory/RAG; approval gates on sensitive tools. No first-class “evidence-gated Verifier” role like Cipher — success is workflow completion / human approval.
- **GitHub affinity:** General-purpose frameworks; not GitHub-native (PRs/issues/Actions) by default.
- **Citations:** https://github.com/microsoft/autogen · https://github.com/ag2ai/ag2 · https://learn.microsoft.com/en-us/agent-framework/journey/workflows · https://learn.microsoft.com/en-us/agent-framework/workflows/orchestrations/sequential
- **Confidence:** high (official README + Learn docs)

##### CrewAI
- **What:** Role-based multi-agent framework: **Crews** (collaborative agents + tasks) and **Flows** (event-driven production orchestration with persisted state).
- **Orchestration:** Sequential or hierarchical process; hierarchical needs `manager_llm` / `manager_agent`. Delegation (`allow_delegation`) and Ask-Question tools; Flows compose Crews with `@start` / `@listen` / `@router` / `@persist`.
- **Memory / tools / verification:** Unified `Memory` API (scopes, remember/recall, fact extraction after tasks); task `context` deps; optional task **guardrails** + retries. Verification = guardrails / manager validation / human_input — not a separate evidence Verifier with tests/ as gate.
- **GitHub affinity:** General-purpose; Enterprise deploy option; not PR/issue/Actions-first.
- **Citations:** https://docs.crewai.com/edge/en/concepts/crews · https://docs.crewai.com/edge/en/concepts/tasks · https://docs.crewai.com/edge/en/concepts/flows · https://docs.crewai.com/edge/en/concepts/memory · https://docs.crewai.com/edge/en/concepts/collaboration
- **Confidence:** high

##### MetaGPT
- **What:** “Software company as multi-agent system” — one-line requirement → user stories, designs, APIs, code, docs via SOP-driven roles (PM, architect, engineer, etc.). Philosophy: `Code = SOP(Team)`.
- **Orchestration:** Roles publish/observe Messages in an Environment; `_watch` upstream Actions; Team hire pattern; SOP pipelines rather than free-form debate.
- **Memory / tools / verification:** Shared Environment messages + ProjectRepo artifacts; tester/reviewer roles in tutorials. Strong SOP structure; weaker explicit red-team → evidence-gate loop than Cipher DESIGN.
- **GitHub affinity:** Generates project repos locally; not GitHub Actions/PR-native reference.
- **Citations:** https://github.com/FoundationAgents/MetaGPT · https://docs.deepwisdom.ai/main/en/guide/get_started/introduction.html · https://docs.deepwisdom.ai/v0.8/en/guide/tutorials/multi_agent_101.html
- **Confidence:** high

##### OpenDevin → OpenHands
- **What:** Open-source AI software-engineering platform (formerly OpenDevin): GUI, CLI, Python SDK, Agent Server; agents write/edit code, run bash, browse, track tasks in a **Workspace** (local / Docker / remote).
- **Orchestration:** Primarily **single agent + tools** (CodeAct-style action/observation loop); delegation to specialists possible; Conversation lifecycle. Multi-agent is secondary to sandboxed coding agent execution.
- **Memory / tools / verification:** Event/conversation history; FileEditor, Terminal, TaskTracker tools; Docker/remote sandbox recommended. Tests/linters via agent commands — no mandatory Critic→Verifier evidence pipeline in the product model.
- **GitHub affinity:** Cloud sign-in with GitHub/GitLab; issue→task automations in Agent Canvas narrative; still an agent platform, not a GitHub-native swarm reference architecture.
- **Citations:** https://github.com/OpenHands/OpenHands · https://docs.openhands.dev/sdk/getting-started · https://docs.openhands.dev/sdk/arch/agent-server · https://openhands.dev
- **Confidence:** high for product shape; medium for internal multi-agent delegation details (docs emphasize SDK agent + tools)

##### Aider-style coding agents
- **What:** Terminal AI pair-programmer tightly bound to a **git repo**: edit files, auto-commit with Conventional Commits messages, `/undo`, repo map for large codebases, lint/test hooks.
- **Orchestration:** Mostly **single-agent** (optionally architect/editor two-model mode); human drives chat; not a multi-role swarm.
- **Memory / tools / verification:** Chat history + repo map; git history as undo/audit; `/test` / `/lint` feedback into chat. Verification = human + tests, not Critic/Verifier roles.
- **GitHub affinity:** Excellent **local git** affinity (commits, branches, undo); PR/issue/Actions workflows are out-of-band (human or CI).
- **Citations:** https://aider.chat/docs/ · https://aider.chat/docs/git.html · https://github.com/Aider-AI/aider
- **Confidence:** high

##### GitHub Copilot cloud agent / coding-agent patterns (public docs only)
- **What:** Asynchronous **Copilot cloud agent** on GitHub.com: research repo, plan, edit, run tests/linters in an **ephemeral firewalled** environment, open/update PRs; also chat, code review, automations, Agentic Workflows (Markdown→Actions).
- **Orchestration:** Single delegated agent session per task (not a Research/Builder/Analyst fan-out swarm); human starts from issue/PR/chat; iterates via PR comments (`@copilot`). Session cap ~59 minutes; one branch / one PR per task; repo-scoped.
- **Memory / tools / verification:** Session logs; Copilot Memory (longer-term prefs — distinct from session context); CodeQL/secret scanning/dependency analysis on generated code; **human review required** before merge; Actions on agent PRs need write-user approval; no org/repo Actions secrets by default (only `copilot` environment secrets).
- **GitHub affinity:** **Highest** of surveyed systems — issues, PRs, Actions, branch protections, MCP, automations are first-class.
- **Citations:** https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent · https://docs.github.com/en/copilot/responsible-use/copilot-coding-agent · https://docs.github.com/en/copilot/tutorials/cloud-agent/build-guardrails · https://docs.github.com/en/copilot/how-tos/use-copilot-agents/cloud-agent
- **Confidence:** high (official docs)

##### Related (already in seed — do not re-litigate)
- 2026 papers (Agensh, DeLM, STORM, Parallel Claudes, Anthropic multiagent patterns) already logged above; they inform concurrency/claiming more than product frameworks.

#### (2) Gaps vs Cipher DESIGN.md

| Cipher DESIGN claim | Prior art status | Gap direction |
|---------------------|------------------|---------------|
| Coordinator + Research/Builder/Analyst fan-out → shared memory → Critic → Verifier evidence gate | Closest: MetaGPT SOP roles; CrewAI hierarchical + guardrails; MAF Magentic/group-chat. **None** package Critic + **evidence-gated Verifier** (tests/ artifacts) as a hard loop exit as explicitly as Cipher. | **Cipher differentiator** — keep and specify evidence schema |
| Controlled tool interface (not unlimited) | AutoGen/MAF tool approval; CrewAI tools; OpenHands tool allowlists; Copilot CLI permission prompts / cloud firewall | Cipher stubs exist (`src/tools.py`) but **permission ADR + allowlist enforcement** still open (DESIGN §8) |
| GitHub-native first (repos, PRs, issues, Actions) | Only Copilot cloud agent is truly GitHub-native; others are general or local-git (Aider) | **Cipher unique positioning** if it remains a *reference swarm* that *uses* GitHub primitives — DESIGN silent on concrete issue/PR/Actions mapping |
| Aggressive only in authorized sandbox | Copilot ephemeral firewall; OpenHands Docker; CLI directory scope | Cipher states boundary well; needs **operational** sandbox definition (box vs Actions runner vs Docker) |
| Shared workspace `memory/findings.md` + `state.md` + tasks/ | CrewAI Memory (vector scopes); DeLM checked-context; Agensh notes board; Aider git history | Cipher’s **markdown append-only board** is simpler/auditable; silent on concurrency locks, claim protocol, verified-vs-unchecked entries (seed papers flagged this) |
| Debate / challenge coordinator / abandon approaches | Group chat / Magentic / Crew delegation exist; “cheat” semantics are Cipher-specific | Others under-specify **authorized adversarial collaboration**; Cipher under-specifies **when** debate is mandatory vs optional |
| Budget / permissions on agent runtime | CrewAI `max_rpm`, budgets informal elsewhere; Copilot AI credits + 59m session | Cipher table exists; **no concrete budget units or enforcement** yet |
| `create_agent()` spawn | Copilot SDK sub-agents; CrewAI delegation; OpenHands delegation | DESIGN lists tool; **spawn policy / depth limits** unspecified |
| What others emphasize that DESIGN is silent on | Persistent vector memory (CrewAI); git auto-commit undo (Aider); firewalled ephemeral runners + secret isolation (Copilot); Flows/`@persist` crash-resume (CrewAI); Hub audit WAL (AG2); conflict-at-write / task claiming (STORM/DeLM/Agensh seed) | Recommend Analyst cover: **claim locks, CI-as-verifier, secret scopes, crash-resume, git commit discipline** |

**Assumptions for Critic (explicit):**
1. Cipher stays **reference architecture + prototype**, not competing with Copilot SaaS — GitHub-native means *integrating* Actions/PRs/issues, not replacing Copilot.
2. Markdown shared memory remains primary through v0; vector memory is optional later.
3. “Evidence” for Verifier means artifacts under `tests/` + logs, not merely LLM self-check.
4. Multi-Builder parallelism is desired eventually (seed papers) — not yet locked in DESIGN.

#### (3) Recommended memory / task schemas

Compatible with DESIGN §6–7 and `tasks/README.md`; informed by DeLM (checked context), Agensh (append-only board), CrewAI (facts + scopes), Copilot (session logs / human gate).

**`memory/findings.md` (keep append-only)**
- Continue dated entries: Claim / Evidence / Confidence / Open questions.
- Add optional fields per entry: `sources[]` (URLs), `verified: yes|no|partial` (only Verifier or Critic+tests flip to `yes`), `task_id`, `agent`.
- Prefer **atomic claims**; link heavy dumps to `artifacts/`.
- Convention: agents may append unchecked findings; Coordinator/Verifier promote summaries into `state.md` only after Critic pass or Verifier evidence.

**`memory/state.md`**
- Keep: Current goal, Phase, Pipeline status table, Last verdict, Open questions, Next.
- Add: `Active task ids`, `Blocked on`, `Repo URL`, `Safety reminder` one-liner (sandbox-only), `Budget spent` (optional).
- Last verdict shape: `PASS|FAIL|PENDING` + evidence paths + Critic summary link.

**`tasks/` schema (extend minimal fields, don’t break T-000)**
| Field | Rec | Notes |
|-------|-----|-------|
| `id`, `goal`, `assignee`, `status`, `deps` | required | existing |
| `status` values | keep + add `claimed` | or treat `running` as claimed; set immediately on assign to avoid dual-write (Parallel Claudes lesson) |
| `budget` | optional → recommended | e.g. `steps|tokens|minutes` |
| `permissions` | optional → recommended | subset of tools allowlist |
| `artifacts[]` | optional | paths under artifacts/ |
| `evidence[]` | new optional | paths under tests/logs for Verifier |
| `claim_file` / lock | new optional | e.g. `tasks/locks/T-001.lock` with agent id + timestamp |
| `parent` / `spawned_by` | new optional | for `create_agent()` lineage |
| `github` | new optional | `{issue, pr, branch, run_id}` for GitHub-native slices |

**Handoff (DESIGN §6):** keep `goal → findings → artifact → critique → verdict`; require Critic notes path + Verifier evidence list before PASS.

#### (4) Risks — GitHub-native reference + prototype

**Safety boundary (explicit, non-negotiable):** Cipher is aggressive **only inside an authorized sandbox**. It must **not** bypass security, steal credentials/data, evade safeguards, or break into systems. Elevated access only via proper channels. No security-bypass tooling, credential theft, or break-in workflows — ever.

1. **Prompt injection via issues/PRs/comments** — Untrusted issue bodies and review comments can instruct agents to exfiltrate secrets or widen scope. Mitigate: treat issue/PR text as untrusted data; strip hidden chars (Copilot pattern); allowlist tools; never pass repo secrets into agent context by default.
2. **Token / secret blast radius** — Fine-grained PATs, Actions secrets, `copilot` env secrets, MCP credentials. Mitigate: least-privilege tokens; separate bot account; no org secrets in agent jobs; rotate; never log tokens; sandbox FS without `~/.config` credentials.
3. **CI cost & Actions minute burn** — Swarm retries + matrix builds can exhaust minutes/quotas (Anthropic bandwidth contention lesson). Mitigate: budgets per task; cap concurrent jobs; fail-fast Verifier; cache.
4. **Branch / PR chaos** — Multiple agents pushing overlapping branches, force-pushes, skipping reviews. Mitigate: one writer branch per task claim; branch protection; require human merge; signed commits / co-author trail; no agent merge to default branch.
5. **Verifier theater** — LLM declares PASS without real tests. Mitigate: Verifier requires `tests/` or CI run_id evidence; Critic attacks assumptions before Verifier.
6. **Sandbox escape confusion** — “Authorized sandbox” undefined across laptop box vs GH Actions vs Docker. Mitigate: ADR naming allowed execution venues and forbidden host access.
7. **Supply chain / MCP trust** — Malicious or over-broad MCP servers (Copilot SDK warning). Mitigate: pin allowlisted MCP; CODEOWNERS on agent config.
8. **Legal/compliance on generated code** — Public-code matches, insecure suggestions. Mitigate: human review; secret scanning; dependency audit — same as Copilot responsible-use guidance.

- **Confidence (section overall):** high for prior-art descriptions; **medium** for Cipher gap mapping (design judgment); **medium** for schema extras pending Coordinator ADR.
- **Open questions:** Formal task id for this research? Coordinator-centric vs pull-queue for coding subtasks? Exact GitHub event triggers (issue labeled / PR comment) for prototype v0? Memory write concurrency ADR owner?

### 2026-10-07 — Analyst — Design-doc outline (tradeoffs + recs)
- Claim: v0 pillars should be (1) evidence-gated Critic→Verifier loop, (2) issue-driven GitHub mapping + Actions as Verifier evidence, (3) claim locks + append-only findings with `verified` flag; defer vector memory and multi-Builder conflict-at-write.
- Evidence: Artifact `artifacts/design-doc-outline.md` synthesizes Research prior-art brief, Swarm Watch papers, DESIGN.md §5 locks, tasks/README schema. Covers gaps vs prior art, memory/task schema proposals, GitHub-native options A–D with A+C recommended, risks/mitigations, open ADRs, suggested T-001–T-005.
- Confidence: high on gap table (sourced Research); medium on trigger/concurrency ADR choices (design judgment).
- Open questions: Formal task YAML still missing; Critic should attack assumptions in outline §1.2; Verifier PASS/FAIL vs design-doc goal.
- Safety: Sandbox-only; no security bypass / credential theft / safeguard evasion / break-ins — restated in outline §0.

### 2026-10-07 — Research — User lock: real tests required
- Claim: Verifier **must not** PASS on LLM judgment alone. Cipher v0 requires **real executable tests** (and/or CI run evidence) under `tests/` linked from the verdict. “Verifier theater” is a product FAIL, not a soft risk.
- Evidence: User directive 2026-10-07 CT: “We need real tests.” Aligns with DESIGN Verifier evidence gate, Research risk #5, Analyst outline §1.2 assumption 3, and `tests/README.md` (“No PASS without evidence”).
- Confidence: **high** (direct user product lock).
- Implications:
  1. Design doc: elevate from mitigation bullet → **hard acceptance criterion** for any Verifier PASS.
  2. Prototype: add runnable pytest (or equivalent) for `src/loop.py` / `src/tools.py` stubs ASAP — empty `tests/.gitkeep` is not enough.
  3. GitHub-native path: Actions workflow must run those tests; Verifier evidence includes green `run_id` or local pytest transcript path.
  4. Critic: attack any outline/doc that allows self-declared PASS.
- Open questions: Minimum first suite owner (Builder)? Framework (pytest recommended)? Required coverage for T-000 stubs before design-doc Verifier PASS?
- Safety: unchanged — sandbox-only; no bypass / credential theft / safeguard evasion / break-ins.

### 2026-10-07 — Critic — Red-team design-doc outline
- Claim: Analyst outline is the right shape but **not** Verifier-ready as a hard PASS. Four blockers: (B1) evidence schema still allows Verifier theater via and/or paths, (B2) GitHub A+C assumes automation/identity Cipher lacks, (B3) task status enum drift (README vs outline vs T-001 `in_progress`), (B4) authorized sandbox still undefined while treated as operational. Also: only Verifier may set `verified: yes`; single-writer for memory/ in v0; vs-Copilot table required; spawn depth cap; forbid force-push/--no-verify on shared branches.
- Evidence: Full critique in `artifacts/critique-design-doc-outline-2026-10-07.md`. Inputs: outline, findings (Research + Swarm Watch + Analyst), DESIGN.md, state.md, tasks/README.md, T-001-design-doc.yaml.
- Confidence: high on schema/status contradictions and theater hole (direct file reads); medium on GitHub actor split (design judgment).
- Open questions: Will Coordinator waive B1–B4 as residual risk, or require outline revision before Verifier PASS?
- Safety: Sandbox-only critique; no bypass / credential theft / safeguard evasion / break-ins.
- Critic signal: **CONDITIONAL / BLOCK** → Verifier should FAIL “ready to iterate” until B1–B4 fixed or explicitly waived.

### 2026-10-07 — Verifier — T-001 design-doc FAIL
- Claim: Outline is not ready to iterate on as a gated PASS. Critic B1–B4 confirmed by independent file checks; no Coordinator waive.
- Evidence:
  - Verdict log: `logs/verdict-T-001-2026-10-07.md`
  - Critique: `artifacts/critique-design-doc-outline-2026-10-07.md`
  - Outline still has theater hole (risk #5 and/or); no `tests/evidence/`; README status enum lacks `claimed`; §0 sandbox slogan only; §4.2 A+C without actor/manual split
  - User lock: real tests required (findings entry above)
- Verdict: **FAIL**
- Confidence: high (direct reads)
- Open questions: Analyst revise vs Coordinator waive B1–B4?
- Safety: Sandbox-only; no bypass / credential theft / safeguard evasion / break-ins.

### 2026-10-07 — Analyst — Outline v0.1 clears Critic B1–B4
- Claim: Revised `artifacts/design-doc-outline.md` (v0.1) addresses Critic blockers B1–B4 and required items R1–R6: machine-checkable evidence schema; manual v0 vs automated v0.5 GitHub actor split; unified task status enum; operational sandbox stub; Verifier-only `verified:yes`; single memory writer; vs-Copilot table; forbidden git actions; spawn depth 0 for specialists.
- Evidence: Outline §§0.1–0.3, 1.3–1.4, 3.0–3.4, 4.1–4.3, 8 disposition table; `tasks/README.md` enum includes `claimed`; `tasks/T-001-design-doc.yaml` notes updated (status `running`).
- Confidence: high that blockers are addressed in-doc; medium that Verifier will accept doc-only process evidence for this design-doc goal (no CI run_id for markdown).
- Open questions: Verifier PASS/FAIL on v0.1; whether Coordinator waives any residual ADR depth.
- Safety: Sandbox venues stubbed; untrusted intake + forbidden force-push/--no-verify restated.

### 2026-10-07 — Builder — pytest scaffold
- Claim: Executable pytest suite now covers `src/loop.py` and `src/tools.py` contracts (implemented Memory + empty-evidence Verifier False + ToolRegistry permissions; stubs still raise NotImplementedError). Green local run is Verifier-citable evidence; empty `tests/.gitkeep` alone is no longer the only presence under `tests/`.
- Evidence:
  - `tests/test_loop.py`, `tests/test_tools.py`, `tests/conftest.py`
  - `pyproject.toml` (`pythonpath = ["src"]`), `requirements-dev.txt`
  - Transcript: `logs/pytest-2026-10-07.txt` (copy `artifacts/pytest-transcript.txt`) — **31 passed**, exit 0
  - Command: `cd /workspace/cipher && .venv/bin/python -m pytest -q` (venv created under `.venv/`, gitignored)
- Confidence: **high** (local green run captured)
- Open questions: Wire real tool/loop bodies later; CI Actions `run_id` still blocked on gh auth / push.
- Safety: Sandbox-only under `/workspace/cipher`; no bypass / credential theft / safeguard evasion / break-ins.

### 2026-10-07 — Verifier — T-001 design-doc PASS (re-verify)
- Claim: Outline v0.1 addresses Critic B1–B4 + R1–R6; design doc is ready to iterate on. Stub pytest suite is executable (31 passed).
- Evidence:
  - `artifacts/design-doc-outline.md` v0.1 (§0.1, §3.0, §3.3, §4.1, disposition §8)
  - `tasks/README.md` unified status enum
  - `tests/evidence/T-001.yaml` + `logs/T-001-run_test.log` (exit 0, 31 passed)
  - Prior FAIL: `logs/verdict-T-001-2026-10-07.md`; PASS log: `logs/verdict-T-001-2026-10-07-pass.md`
- Verdict: **PASS** (`verified: yes` for this design-doc claim)
- Confidence: high
- Open questions: formalize into DESIGN.md; CI `ci_run_url` still future
- Safety: Sandbox-only; no bypass / credential theft / safeguard evasion / break-ins.

### 2026-10-07 — Analyst — Outline v0.2 + design-doc acceptance tests (post FAIL)
- Claim: After Verifier FAIL on T-001 and user lock (real tests required), outline bumped to **v0.2** with §0.4 HARD gate (no LLM-only PASS; executable pytest and/or CI required). Added `tests/test_design_doc_outline.py` (11 tests) checking B1–B4/R1 sections + enum alignment; refreshed `tests/evidence/T-001.yaml` + `logs/T-001-run_test.log` (**42 passed**). Coordinator: no waive — Critic re-red-team next.
- Evidence: artifacts/design-doc-outline.md v0.2; tests/test_design_doc_outline.py; tests/evidence/T-001.yaml; logs/T-001-run_test.log; logs/verdict-T-001-2026-10-07.md (prior FAIL).
- Confidence: high that B1–B4 text + runnable tests now exist; medium pending Critic re-pass and Verifier re-verify on v0.2 (a concurrent PASS artifact on v0.1 may race).
- Open questions: Critic second pass on v0.2; commit working tree so git_sha matches files under review.
- Safety: Sandbox stub unchanged; untrusted intake + forbidden git actions retained.
