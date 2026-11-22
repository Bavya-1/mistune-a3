"""Unit tests for the stage checks. Run from the repo root:

    python -m pytest workflow/orchestrator -q
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from checks import check_design, check_review, check_spec  # noqa: E402

REPO = str(Path(__file__).resolve().parents[2])

GOOD_SPEC = """# Spec: x
## Problem
p
## Acceptance criteria
- AC1: Given `| a |\\n|---|\\n| 1 |`, the output contains `<table>`.
- AC2: Existing behaviour for `| a |\\n|---|\\n| 1 |` is unchanged.
## Edge cases
- none
"""


def test_good_spec_passes():
    r = check_spec(GOOD_SPEC)
    assert r.ok and r.data["ac_ids"] == ["AC1", "AC2"]


def test_spec_without_example_fails():
    r = check_spec("## Acceptance criteria\n- AC1: It works well for users.\n")
    assert not r.ok


def test_spec_with_vague_word_fails():
    r = check_spec("## Acceptance criteria\n- AC1: Given `a`, it works `properly`.\n")
    assert not r.ok and any("properly" in x for x in r.reasons)


def test_blocked_spec_is_flagged():
    r = check_spec("## Acceptance criteria\nBLOCKED: not about this project\n")
    assert not r.ok and r.blocked


def test_design_names_real_function():
    design = (
        "## Files and functions to change\n"
        "- `src/mistune/list_parser.py`: `parse_list`: fix\n"
        "- `tests/test_new.py`: `test_ac1_x`\n"
        "## Acceptance criteria coverage\n- AC1: covered\n"
    )
    assert check_design(design, REPO, ["AC1"]).ok


def test_design_with_invented_function_fails():
    design = (
        "## Files and functions to change\n"
        "- `src/mistune/list_parser.py`: `no_such_function`: fix\n"
        "## Acceptance criteria coverage\n- AC1: covered\n"
    )
    r = check_design(design, REPO, ["AC1"])
    assert not r.ok and any("no_such_function" in x for x in r.reasons)


def test_design_with_missing_file_or_coverage_fails():
    design = "## Files and functions to change\n- `src/mistune/nope.py`: `x`\n## Acceptance criteria coverage\n"
    r = check_design(design, REPO, ["AC1"])
    assert not r.ok and len(r.reasons) >= 2


def review(verdict, commands, findings="- a bug: block_parser.py:10, output showed X"):
    return f"---\nverdict: {verdict}\ncommands_run: {commands}\n---\n# Review\n## Findings\n{findings}\n"


def test_approve_with_evidence_passes():
    r = check_review(review("approve", 3, "none"), ci_green=True)
    assert r.ok and r.data["verdict"] == "approve"


def test_approve_without_commands_fails():
    assert not check_review(review("approve", 1, "none")).ok


def test_approve_is_overridden_when_ci_red():
    r = check_review(review("approve", 3, "none"), ci_green=False)
    assert r.ok and r.data["verdict"] == "code_issue"


def test_code_issue_needs_a_finding():
    assert not check_review(review("code_issue", 2, "none")).ok
    assert check_review(review("code_issue", 2)).ok


def test_malformed_review_fails():
    assert not check_review("looks good to me").ok
    assert not check_review(review("maybe", 2)).ok
