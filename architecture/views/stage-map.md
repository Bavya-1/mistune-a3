# Stage map

One row per stage: which agent handles it, which artifact it saves, and the
check that must pass before the next stage starts. Checks are deterministic
code (ADR-007); the agent split is ADR-001.

| # | Stage | Agent (model) | Artifact | Check before moving on | If the check fails |
| --- | --- | --- | --- | --- | --- |
| 1 | Requirements | Planner (Groq `gpt-oss-20b`, was Gemini: ADR-011) | `spec.md` | Has acceptance criteria `AC1..ACn`; each has a concrete input and expected result; no vague words; no `BLOCKED:` marker | Retry once; if still failing, stop the run and explain in `spec.md` |
| 2 | Design | Planner (Groq `gpt-oss-20b`, was Gemini: ADR-011) | `design.md` | Names files that exist and functions found in them; every AC is covered by the plan | Retry once; if still failing, stop the run |
| 3 | Implementation | Builder (Groq `gpt-oss-120b`) | `diff.patch` | Package installs and imports; diff is non-empty; only allowed paths changed | Retry within the build budget; then stop the run |
| 4 | Testing | Builder (Groq `gpt-oss-120b`) | `test_report.md` | Each AC has a new test; the full suite passes; new tests fail without the change | Back to stage 3 within budget; then back to stage 2 once; then stop |
| 5 | Release | Workflow code (no model) | `pr.md` and the PR link | Branch pushed, PR open, CI on the PR head is green | Stop the run and comment on the issue |
| 6 | Review | Reviewer (Groq `qwen3.8-27b`) | `review.md` | Valid structured verdict with evidence; `approve` only if CI is green | `code_issue` back to stage 3, `approach_issue` back to stage 2, at most 2 rounds; then a human decides |

Final decision: a human merges or closes the pull request; nothing in the
workflow merges.
