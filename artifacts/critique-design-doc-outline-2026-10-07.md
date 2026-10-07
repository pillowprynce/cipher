# Critic / Red Team — Design-doc outline critique

**Author:** Critic  
**Date:** 2026-10-07 (America/Chicago)  
**Target:** `artifacts/design-doc-outline.md` (Analyst v0)  
**Also reviewed:** `memory/findings.md` (Research + Swarm Watch + Analyst), `DESIGN.md`, `memory/state.md`, `tasks/README.md`, `tasks/T-001-design-doc.yaml`  
**Verdict for Verifier readiness:** **BLOCK — conditional**. Outline is strong enough to iterate, but several claims are under-specified or over-confident. Fix the blockers below before calling the design doc “ready to iterate on” as a *gated* PASS. Soft recommendations can ship as open ADRs.

**Safety posture while critiquing:** sandbox-only aggression. No bypass, credential theft, safeguard evasion, or break-ins.

---

## Executive summary

Analyst’s outline is the right shape: safety first, prior-art gaps, schema proposals, GitHub A+C, risk table, next tasks. The differentiator story (Critic → evidence-gated Verifier on GitHub primitives) is coherent.

What fails a hard red-team:

1. **Verifier theater is only named, not mechanized** — still easy for an LLM Verifier to rubber-stamp.
2. **GitHub A+C mapping assumes agent identity / auth that Cipher does not yet have.**
3. **Schema extras conflict with live `tasks/README.md` and T-001 status vocabulary.**
4. **“Authorized sandbox” is still a slogan** — listed as ADR but treated as if the boundary is already operational.
5. **Four Research assumptions are asserted, not stress-tested** against Copilot overlap and multi-writer reality.

Recommendation: Verifier should **FAIL** a “solid, ready-to-iterate design doc” claim until blockers B1–B4 are addressed in the outline (or explicitly demoted to tracked open risks with owners). Non-blockers can remain ADRs.

---

## Attack surface 1 — §1.2 assumptions (Research’s four)

### A1. “Reference + prototype, does not replace Copilot SaaS”

- **Attack:** Positioning is product-marketing, not architecture. Issue-label kickoff + branch claim + PR + Actions is *exactly* Copilot cloud-agent UX. Without a crisp “what Cipher adds that Copilot cannot” section (multi-role Critic→Verifier + shared markdown board + challenge-Coordinator), the GitHub-native claim collapses into “DIY Copilot with more prompts.”
- **Counterexample:** A reader comparing outline §4.2 to [Copilot coding agent](https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent) sees near-identical primitives.
- **Required fix:** Add a one-page “vs Copilot” table: multi-role debate, evidence schema under `tests/`, challenge-Coordinator rights, append-only findings with `verified`. If those are not enforceable in v0, drop “differentiator” language.

### A2. “Markdown memory primary through v0”

- **Attack:** Append-only markdown on a shared PR is not concurrency-safe. Parallel Claudes and Anthropic multiagent patterns show overwrite / same-bug collisions. Outline prefers claim locks (good) but still lets *many roles append findings* without a merge protocol for `findings.md` itself.
- **Missing:** Who serializes appends? Single memory PR? Bot rebase? File-level lock? Without that, `verified` flags race.
- **Required fix:** Specify single-writer for `memory/*.md` in v0 (Coordinator or dedicated memory branch), or claim-lock per findings section. Do not leave as vague ADR while calling markdown “keep.”

### A3. “Verifier evidence = tests/ paths and/or CI run_id, not LLM self-check”

- **Attack:** “And/or” is the theater hole. An agent can invent a path under `tests/` that never ran, or paste a stale `run_id`. Outline risk #5 names this and then mitigates with “Critic before Verifier” — which is *process*, not *enforcement*.
- **Required fix (BLOCKER B1):** Define a minimal evidence schema, e.g.:
  - `tests/evidence/<task_id>.yaml` with `paths[]`, `commands[]`, `exit_codes[]`, `ci_run_url` (must resolve), `checked_at`
  - Verifier PASS requires **machine-checkable** fields: file exists + CI API status `success` for that SHA, **or** local `run_test()` exit 0 logged under `logs/`
  - Explicit: LLM prose alone is never evidence
- Until B1 lands, do not claim evidence-gating as a hard loop exit.

### A4. “Multi-Builder parallelism desired eventually; not locked for v0”

- **Attack:** Harmless if true — but §3.4 Option A (single-writer + claim locks) and §4.2 “one writer branch per task” quietly **forbid** multi-Builder while §1.2 keeps the door open. Swarm Watch implications push conflict-at-write / claim locks *because* parallelism is expected.
- **Required fix:** Lock v0 as **single active Builder writer per repo path**. Move multi-Builder to a dated ADR milestone. Stop mixing “defer parallelism” with schema fields (`parent`/`spawned_by`) that invite spawn fan-out now.

---

## Attack surface 2 — GitHub mapping (§4 A+C)

### G1. Option A+C recommended without identity model

- **Attack:** Who is the GitHub actor? Human PAT? Bot app? Each teammate’s own auth? Outline says “least-privilege bot PAT” and “no agent merge to main” but Cipher today is a swarm of Grok Bot teammates writing under `/workspace/cipher` — not yet a GitHub App with issue webhooks.
- **Failure mode:** Design doc promises issue-label triggers and Actions status checks while `run_agents()` and webhook ingress are open questions in `state.md`. That is aspirational architecture labeled as v0 mapping.
- **Required fix (BLOCKER B2):** Split mapping into:
  - **v0 manual:** human opens issue / labels; humans or local agents open PR; Actions runs on PR; human merges
  - **v0.5 automated:** GitHub App / `workflow_dispatch` that assigns tasks
  - Do not present A+C as if automation is implied for “prototype path” without naming the actor

### G2. Shared memory “commits to memory/ on that PR”

- **Attack:** Multiple roles on one goal → multiple PRs or conflicted memory commits. Outline allows “or dedicated memory PR” as a parenthetical — that is the hard problem, waved away.
- **Required fix:** Pick one for v0: **dedicated memory branch/PR with single serial writer**, specialist PRs link claims by path. Document merge order.

### G3. Reject D (autonomous merge) — good — but silent on force-push / `--no-verify`

- **Attack:** Branch protection stops merge to main; it does not stop agents force-pushing claimed branches or skipping hooks on feature branches, wiping Critic notes.
- **Required fix:** Add explicit forbidden git actions for agents: no `--force` to shared branches, no `--no-verify`, no amending pushed commits. Put in safety §0 or risks table.

### G4. Secrets line is incomplete

- “No org secrets in agent jobs by default” is good. Missing: MCP credentials on the box, browser sessions, and `gh` auth on the shared workspace machine — the actual blast radius for *this* swarm today.
- **Required fix:** ADR or risk row: **box credential boundary** (what agents may use ListCredentials / connectors for) vs Actions secrets.

---

## Attack surface 3 — Schema extras (§3)

### S1. Status vocabulary drift (BLOCKER B3)

- Live `tasks/README.md`: `pending | running | blocked | done | abandoned`
- Outline: adds `claimed`; T-001 uses `in_progress` (not in README enum)
- **Attack:** Three dialects before first E2E. Claiming protocol cannot work if status strings disagree.
- **Required fix:** One enum in README + outline + T-001. Recommend: `pending | claimed | running | blocked | done | abandoned` and migrate T-001 off `in_progress`.

### S2. Who flips `verified`?

- Outline: “only Verifier (or Critic+tests) flips to `yes`”
- **Attack:** “Or Critic+tests” recreates Verifier theater — Critic can self-certify. Research said Verifier or Critic+tests; that ambiguity is the bug.
- **Required fix:** **Only Verifier** sets `verified: yes`. Critic may set `challenged` / leave `no` / request evidence. Partial stays Verifier-owned.

### S3. Field explosion vs v0

- New: `claim_file`, `parent`/`spawned_by`, `github{}`, `evidence[]`, `permissions`, `budget`
- **Attack:** Speculating a full runtime ORM before `loop.py` is wired. Increases doc surface without enforcement.
- **Required fix:** Mark **v0 required:** `evidence[]` + claim mechanism (`claimed` status **or** lock file — pick one, not both). Mark spawn lineage + rich `github{}` as v0.5. Prefer one claim mechanism: status=`claimed` *with* assignee+timestamp is enough; lock files if multi-host.

### S4. Promote-to-state.md convention

- “After Critic pass or Verifier evidence” — two gates again. Coordinator might promote on Critic soft-pass without tests.
- **Required fix:** `state.md` Last verdict and goal completion require Verifier evidence list. Critic can update “Critic summary link” only.

---

## Attack surface 4 — Safety gaps

### X1. Sandbox still undefined (BLOCKER B4)

- §0 restates the slogan. Risk #6 and ADR #2 admit operational definition is open. Outline still says this section “must appear” everywhere as if presence of text = control.
- **Attack:** Without named venues (box desktop / Docker / GH Actions runner) and forbidden host paths, “authorized sandbox” cannot be audited. Agents on this shared box already have broad Shell + browser.
- **Required fix:** Even a stub ADR in-outline:
  - Allowed: `/workspace/cipher` writes; Actions runner for CI; read-only web for Research
  - Forbidden: reading host credential stores to widen access; production deploy; bypassing connector auth
  - Human gate for any permission expansion

### X2. Prompt injection risk listed; no intake rule

- Issues/PRs are untrusted — good. Missing: **Critic must treat Research citations and issue text as untrusted data** (no “tool said so → do it”). Add to debate triggers: security-sensitive instructions in untrusted content → Critic mandatory.

### X3. “Cheat” list includes “spawn specialized sub-agents”

- Unbounded spawn + missing depth limit (open ADR #4) conflicts with budget risk #3.
- **Required fix:** v0 spawn depth = 0 or 1; Coordinator-only `create_agent()`; specialists may not recurse.

### X4. Safety not in T-001 goal text

- T-001 goal omits sandbox constraint. Outline says put reminder in state (done) — also require safety line in every task `goal` or `notes` for GitHub-facing work.

---

## Attack surface 5 — Verifier-theater risk (deep dive)

| Failure mode | How outline allows it | Hardening |
|--------------|----------------------|-----------|
| LLM PASS with no files | Evidence “and/or” CI optional | Require structured evidence object |
| Fake `tests/foo_passed.md` written by Builder | Paths exist ≠ tests ran | Evidence must include command + exit code from `run_test` or CI |
| Stale green CI from old SHA | run_id without SHA pin | Bind evidence to git SHA of the PR head |
| Critic “PASS-to-Verifier” softens bar | Handoff §9 invites readiness signal | Critic emits **BLOCK / CONDITIONAL / CLEAR**; never “PASS” (Verifier owns PASS/FAIL) |
| Analyst confidence “high on gap table” | Sourced ≠ applicable | Verifier should sample 2–3 prior-art citations for existence, not re-litigate all |

**Critic readiness signal:** **CONDITIONAL** — clear to Verifier only after B1–B4 addressed or explicitly accepted as FAIL reasons.

---

## What is solid (do not thrash)

- §0 safety boundary text and placement — keep.
- Prior-art gap table structure and “defer vector memory / crash-resume / auto-commit undo” — keep.
- Rejecting fully autonomous merge (Option D) — keep.
- Risk table rows 1–4, 7–10 — mostly good; harden 5–6 as above.
- Suggested T-001–T-005 sequencing — sensible once blockers clear.
- Debate triggers for safety/permission changes — keep; extend for untrusted-content instructions.

---

## Required fixes checklist (for Analyst / Coordinator / Builder)

| ID | Severity | Action |
|----|----------|--------|
| B1 | **Blocker** | Evidence schema: machine-checkable `tests/evidence/…` + SHA-bound CI or logged `run_test`; ban LLM-only PASS |
| B2 | **Blocker** | Split GitHub A+C into manual v0 vs automated v0.5; name the GitHub actor |
| B3 | **Blocker** | Unify task status enum across README, outline, T-001 |
| B4 | **Blocker** | Stub operational sandbox venues + forbidden actions in the outline |
| R1 | Required | Only Verifier sets `verified: yes` |
| R2 | Required | Single-writer rule for `memory/` in v0 |
| R3 | Required | vs-Copilot differentiator table |
| R4 | Required | Forbid agent force-push / hook skip on shared branches |
| R5 | Required | v0 spawn depth cap (0 or 1) |
| R6 | Nice | Prefer one claim mechanism; defer `parent`/`spawned_by` richness |

---

## Critic → Verifier handoff

- **Artifact:** this file  
- **Signal:** **CONDITIONAL / BLOCK** — do **not** PASS “solid GitHub-native design doc ready to iterate on” until B1–B4 are fixed in the outline or waived in writing by Coordinator with residual risk accepted.  
- **Evidence Critic used:** files listed in header (read 2026-10-07). No CI run for this critique (doc-only).  
- **Not claimed:** empirical validation of A+C in-repo; paper claims re-fetched (trusted Research citations at medium applicability).

