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
