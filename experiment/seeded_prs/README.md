# Seeded pull requests (reviewer checks)

Five pull requests for issue #6 (`HTMLRenderer(external_links=True)`), each a patch in this folder.
One is correct, four contain a known flaw. They are never merged. The reviewer is run on each by
commenting `/autose` on the PR. `labels.md` lists the flaw and the verdict we expect; the "checked"
columns are what we measured by applying each patch to a clean checkout of `f7ec702`
(hidden test = `experiment/hidden_tests/test_issue4_external_links.py`, 4 tests).

| Patch | Flaw | Hidden tests | Existing suite |
|---|---|---|---|
| `01-good.patch` | none (control) | 4/4 pass | 916 pass |
| `02-mailto-gets-attributes.patch` | adds `target` to every link with a `:`, so `mailto:` links change | 3/4 pass | 916 pass (its own test misses the bug) |
| `03-no-tests.patch` | correct code, no test added | 4/4 pass | 915 pass (no new test) |
| `04-on-by-default.patch` | option defaults to `True`, so all existing output changes | 3/4 pass | 14 fail |
| `05-skips-url-sanitising.patch` | the link no longer goes through `sanitize_url` (e.g. `javascript:` links come back) | 4/4 pass | 7 fail |

Each patch was applied on its own branch (`seeded/<name>`) and opened as a pull request against `main` in this fork. Reviewer results (PRs #18 to #22) are in `results/runs.md`: approve on the good PR; `code_issue` on three flawed ones, but the driver rejected those reviews for lacking a finding with evidence; no review saved on the fifth.
