# State

## Current goal
Produce a solid GitHub-native Cipher design doc (reference architecture + runnable prototype path), iterating via Research → Analyst → Critic → Verifier.

## Phase
`design-doc-pipeline` — Research brief complete; ready for Analyst

## Pipeline status
| Stage | Status |
|-------|--------|
| Coordinator | Kickoff issued for design-doc pipeline (Research assigned via Coordinator message; no formal task YAML id yet) |
| Research | **done** — prior-art brief appended to `memory/findings.md` (2026-10-07) |
| Builder | idle (T-000 scaffold done earlier) |
| Analyst | **next** — structure tradeoffs/recommendations into design-doc outline under `artifacts/` |
| Shared memory | findings + state updated |
| Critic | queued after Analyst outline |
| Verifier | queued after Critic — PASS/FAIL vs goal: solid GitHub-native Cipher design doc ready to iterate on |

## Last verdict
_none_ (design-doc not yet Critic/Verifier gated)

## Repo
- Live: https://github.com/pillowprynce/cipher
- Local worktree: `/workspace/cipher`

## Safety reminder
Aggressive only inside authorized sandbox. No security bypass, credential/data theft, safeguard evasion, or break-ins.

## Open questions
- [x] GitHub repo URL — https://github.com/pillowprynce/cipher
- [ ] Formal task id for Research kickoff / Analyst handoff (Coordinator has not written a tasks/*.yaml yet)
- [ ] LLM / teammate backend for `run_agents()`
- [ ] Permission model details for `create_agent()` (spawn depth, allowlist)
- [ ] ADR: memory write concurrency + task claiming locks
- [ ] ADR: operational definition of “authorized sandbox” (box vs Actions vs Docker)
- [ ] Concrete GitHub-native v0 triggers (issue label? PR comment? workflow_dispatch?)

## Next
1. Analyst (0bf8701b-7f85-4f70-b029-1a0ba662c65b): read `memory/findings.md` latest Research entry; write design-doc outline under `/workspace/cipher/artifacts/`.
2. Critic (eb60cfd4-89c5-4b2b-ab84-62a04f53190d): red-team outline + assumptions flagged in findings.
3. Verifier (50548c80-77ad-45d7-9e36-eb221f19ba7a): PASS/FAIL against design-doc goal with evidence.
4. Coordinator/Agent: optional formal task YAML for this pipeline; track GitHub push/auth separately if still needed for remote sync.
