# Sequence view: one real run

This is the furthest real run we have: issue #5 (experiment issue 3, "www autolink"),
run https://github.com/Bavya-1/mistune-a3/actions/runs/44999496778.
It reached stage 2 and stopped there. The review stage has not run on a real change
yet, so the last part is the designed flow and is marked as not yet run.
The first part is taken from the run's own log and status comment.

```
Maintainer   GitHub        gate job     agents job (Planner)                      Groq
   |  label     |             |               |                                      |
   |  `autose` ->|             |               |                                      |
   |            | labeled --> |               |                                      |
   |            |             | label ok, trusted user, one run per issue (ADR-010)  |
   |            |             |-- needs ----->|                                      |
   |            |             |               | Stage 1: spec                        |
   |            |             |               |-- chat (issue as untrusted data) --->|
   |            |             |               |<-- write_artifact spec.md -----------|
   |            |             |               | check: acceptance criteria, each with|
   |            |             |               | a backticked example -> PASSED       |
   |            |             |               | Stage 2: design                      |
   |            |             |               |-- chat (spec, ARCHITECTURE.md, files)>|
   |            |             |               |<-- HTTP 400 tool_use_failed ---------|
   |            |             |               |    (bad `search` call, no `pattern`) |
   |            |             |               | STOPPED: "no design saved"           |
   |            |             |               | upload autose-artifacts              |
   |            |<-- finish job: comment "AutoSE run finished" + reason on issue #5 |

 -- below: designed flow, NOT yet reached by any real run --
   Builder   : stage 3 diff, stage 4 tests (ruff, mypy, pytest, new tests fail without the change)
   release   : push branch, open PR in the fork, dispatch tests.yml and wait for CI (stage 5)
   review    : separate job, read-only, Qwen; sees issue + diff + repo only -> review.md (stage 6)
   verdict   : code_issue -> fix -> review round 2; then a human decides. The workflow never merges.
```
