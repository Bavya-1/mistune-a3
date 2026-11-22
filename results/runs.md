# Runs

Every link below is a real GitHub Actions run in https://github.com/Bavya-1/mistune-a3.
No run reached stage 3 (diff), so there is no pull request and no review yet. Each stop was caught and explained by the workflow itself.

## Final five runs (one per experiment issue, all on Groq)

| Issue | Run | Furthest stage | Result | Why it stopped |
|---|---|---|---|---|
| #3 | https://github.com/Bavya-1/mistune-a3/actions/runs/45002050172 | 1 spec | stopped | Groq HTTP 400 `output_parse_failed` (gpt-oss-20b produced output that could not be parsed) |
| #4 | https://github.com/Bavya-1/mistune-a3/actions/runs/45002183777 | 1 spec | stopped | Groq HTTP 400 `tool_use_failed` (tool-call arguments were not valid JSON) |
| #5 | https://github.com/Bavya-1/mistune-a3/actions/runs/44999496778 | 2 design (spec passed) | stopped | Groq HTTP 400 `tool_use_failed` (call to `search` missing the required `pattern`) |
| #6 | https://github.com/Bavya-1/mistune-a3/actions/runs/45000655278 | 2 design (spec passed) | stopped | Groq HTTP 400 `output_parse_failed` (empty generation) |
| #7 | https://github.com/Bavya-1/mistune-a3/actions/runs/44999306142 | 1 spec | stopped (check failed twice) | AC5 had no concrete example in backticks. This is the designed stop for a vague issue. |

## Earlier runs on issue #7 (while building the workflow)

| Run | Furthest stage | Why it stopped | What it taught us |
|---|---|---|---|
| https://github.com/Bavya-1/mistune-a3/actions/runs/44989946342 | 1 spec | spec stage failed (no reason recorded yet) | led to recording stop reasons |
| https://github.com/Bavya-1/mistune-a3/actions/runs/44990514386 | 1 spec | spec stage failed twice (no reason recorded yet) | spec stage used up its budget exploring, so it got a write-only tool set |
| https://github.com/Bavya-1/mistune-a3/actions/runs/44994852029 | 2 design | design failed (no reason recorded yet) | led to "Why it stopped" in the status comment |
| https://github.com/Bavya-1/mistune-a3/actions/runs/44997834658 | 1 spec | Vercel gateway HTTP 403: card required | gateway not usable without a card, so the planner moved to Groq |
| https://github.com/Bavya-1/mistune-a3/actions/runs/44998205351 | 1 spec | Groq HTTP 403 code 1010 | Cloudflare blocks Python's default User-Agent, so a header was added |
| https://github.com/Bavya-1/mistune-a3/actions/runs/44998644551 | 2 design | prompt 8118 tokens > 8000 per-minute limit | design context is now sized from the provider's limit |

## Pull requests and reviews

None. No run produced a diff, so no PR was opened and the reviewer never ran on a real change.

## Reviewer checks on seeded pull requests (issue #6, patches in `experiment/seeded_prs/`)

None of these was merged. Each review is the comment posted on the PR by the "Review a pull request" workflow run.

| PR | Seeded flaw | Expected | Reviewer verdict | Did it catch the flaw? | Run |
|---|---|---|---|---|---|
| [#18](https://github.com/Bavya-1/mistune-a3/pull/18) `01-good` | none (control) | approve | approve, 8 commands run, new test and suite pass | correct | https://github.com/Bavya-1/mistune-a3/actions/runs/45015757076 |
| [#19](https://github.com/Bavya-1/mistune-a3/pull/19) `02-mailto-gets-attributes` | `mailto:` links get `target` | code_issue | code_issue, 5 commands, all tests passed | no: it named no finding about `mailto:`; the driver stopped the review as invalid | https://github.com/Bavya-1/mistune-a3/actions/runs/45017333385 |
| [#20](https://github.com/Bavya-1/mistune-a3/pull/20) `03-no-tests` | no test added | code_issue | code_issue, 6 commands, checked the behaviour by hand | no: the visible text does not mention missing tests; stopped as invalid | https://github.com/Bavya-1/mistune-a3/actions/runs/45018829592 |
| [#21](https://github.com/Bavya-1/mistune-a3/pull/21) `04-on-by-default` | option on by default | code_issue | code_issue, 6 commands, full suite `20 failed, 1308 passed`, states output must stay unchanged by default | yes in substance; stopped as invalid (no finding with evidence recorded) | https://github.com/Bavya-1/mistune-a3/actions/runs/45021157375 |
| [#22](https://github.com/Bavya-1/mistune-a3/pull/22) `05-skips-url-sanitising` | URL sanitising skipped | code_issue | no review saved (the run stopped at stage 6; the reason is not visible on the PR page) | no | https://github.com/Bavya-1/mistune-a3/actions/runs/45022924870 |

## Mistake during the seeded PRs

The first `01-good` PR, [#16](https://github.com/Bavya-1/mistune-a3/pull/16), was merged into `main` by mistake. It was reverted in [#17](https://github.com/Bavya-1/mistune-a3/pull/17), and the control was redone as #18 from a fresh branch. So `main` has the feature commit and its revert in its history, and the same code as before.
