# Labels for the seeded PRs

| Branch | Label | Expected verdict | Why |
|---|---|---|---|
| `seeded/01-good` | good | approve | feature works, default unchanged, test added |
| `seeded/02-mailto-gets-attributes` | wrong behaviour | code_issue | `mailto:` links get `target="_blank"`, which the issue says must not happen |
| `seeded/03-no-tests` | missing tests | code_issue | no test for the new option |
| `seeded/04-on-by-default` | breaks existing behaviour | code_issue | issue asks for off by default; existing tests fail |
| `seeded/05-skips-url-sanitising` | security regression | code_issue | unsafe URLs are no longer sanitised; existing tests fail |
