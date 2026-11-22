# Decision-experiment variants

We planned to test two ADRs with one changed variant each. **We did not run these
experiments**: no real run got past stage 2 (see `results/runs.md`), so there was
nothing to compare. This file records what we intended, so the gap is clear.

| ADR tested | Default (what we built) | Variant (not run) | What we would have measured |
|---|---|---|---|
| ADR-008 reviewer isolation | reviewer sees issue + diff + repo only, own model | reviewer also sees the builder's `test_report.md` | how often it approves a seeded bad PR |
| ADR-009 planner budget | planner at most 8 calls / 60K tokens | 4 calls | spec and design pass rate |

What the real runs did test, by accident: ADR-009's token limit (the design stage
overflowed Groq's 8K tokens per minute, which led to `design_context`) and ADR-006's
model choice (which led to ADR-011).
