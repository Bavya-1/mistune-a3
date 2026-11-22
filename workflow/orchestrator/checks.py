"""Stage checks (ADR-007). Plain code decides pass or fail, never a model.

Each check returns a CheckResult. Reasons are short and are written into the
stage artifact so a failed run explains itself.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

VAGUE_WORDS = [
    "properly", "correctly", "better", "fast", "faster", "quickly", "nicely", "appropriate",
    "appropriately", "as expected", "user-friendly", "robust", "good", "reasonable", "intuitive",
]
VERDICTS = {"approve", "code_issue", "approach_issue"}


@dataclass
class CheckResult:
    ok: bool
    reasons: List[str] = field(default_factory=list)
    blocked: bool = False  # the agent said it cannot do this task at all
    data: Dict[str, Any] = field(default_factory=dict)

    def fail(self, reason: str) -> None:
        self.ok = False
        self.reasons.append(reason)


def _section(text: str, heading: str) -> Optional[str]:
    """Return the body of a '## heading' section (case-insensitive), or None."""
    pattern = re.compile(r"^##\s+" + re.escape(heading) + r"\s*$", re.I | re.M)
    m = pattern.search(text)
    if not m:
        return None
    rest = text[m.end():]
    nxt = re.search(r"^##\s+", rest, re.M)
    return rest[: nxt.start()] if nxt else rest


# ---------------------------------------------------------------- stage 1
def check_spec(text: str) -> CheckResult:
    """spec.md: acceptance criteria exist and each one is testable."""
    res = CheckResult(ok=True)
    if re.search(r"^\s*BLOCKED:", text, re.M) or "BLOCKED:" in (_section(text, "Acceptance criteria") or ""):
        res.fail("spec is marked BLOCKED")
        res.blocked = True
        return res
    body = _section(text, "Acceptance criteria")
    if body is None:
        res.fail("no 'Acceptance criteria' section")
        return res
    criteria = re.findall(r"^\s*[-*]\s*(AC(\d+))\s*:\s*(.+)$", body, re.M)
    if not criteria:
        res.fail("no criteria written as '- AC1: ...'")
        return res
    ids = []
    for label, num, line in criteria:
        ids.append(label)
        if "`" not in line or line.count("`") < 2:
            res.fail(f"{label} has no concrete example in backticks (an input and an expected result)")
        low = line.lower()
        for word in VAGUE_WORDS:
            if re.search(r"\b" + re.escape(word) + r"\b", low):
                res.fail(f"{label} uses the vague word '{word}'")
                break
    if len(set(ids)) != len(ids):
        res.fail("duplicate criterion ids")
    res.data["ac_ids"] = ids
    return res


# ---------------------------------------------------------------- stage 2
def _backticks(line: str) -> List[str]:
    return re.findall(r"`([^`]+)`", line)


def _defines(source: str, name: str) -> bool:
    last = name.replace("()", "").split(".")[-1]
    if not last:
        return False
    return bool(re.search(r"(def|class)\s+" + re.escape(last) + r"\b", source) or re.search(r"^\s*" + re.escape(last) + r"\s*[:=]", source, re.M))


def check_design(text: str, repo_root: str, ac_ids: List[str]) -> CheckResult:
    """design.md: names real files and functions, and covers every criterion."""
    res = CheckResult(ok=True)
    if re.search(r"^\s*BLOCKED:", text, re.M):
        res.fail("design is marked BLOCKED")
        res.blocked = True
        return res
    body = _section(text, "Files and functions to change")
    if body is None:
        res.fail("no 'Files and functions to change' section")
        return res
    root = Path(repo_root)
    source_files = 0
    for line in body.splitlines():
        if not re.match(r"^\s*[-*]\s", line):
            continue
        ticks = _backticks(line)
        if not ticks:
            continue
        path = ticks[0]
        if "/" not in path and not path.endswith(".py"):
            continue
        is_test = path.startswith("tests/")
        f = root / path
        if not f.is_file():
            if is_test:
                continue  # a new test file does not exist yet
            res.fail(f"file does not exist: {path}")
            continue
        if not is_test:
            source_files += 1
            src = f.read_text(encoding="utf-8", errors="replace")
            for name in ticks[1:]:
                if not _defines(src, name):
                    res.fail(f"{name} not found in {path}")
    if source_files == 0:
        res.fail("the plan names no existing source file to change")
    coverage = _section(text, "Acceptance criteria coverage") or ""
    for ac in ac_ids:
        if not re.search(r"\b" + re.escape(ac) + r"\b", coverage):
            res.fail(f"{ac} is not covered in the coverage section")
    return res


# ---------------------------------------------------------------- stage 6
def check_review(text: str, ci_green: Optional[bool] = None) -> CheckResult:
    """review.md: valid structured verdict; code can override an unsafe approve."""
    res = CheckResult(ok=True)
    m = re.match(r"\s*---\s*\n(.*?)\n---\s*\n", text, re.S)
    if not m:
        res.fail("review.md has no header between --- lines")
        return res
    header = dict(
        (k.strip().lower(), v.strip())
        for k, _, v in (ln.partition(":") for ln in m.group(1).splitlines() if ":" in ln)
    )
    verdict = header.get("verdict", "").strip("` ").lower()
    if verdict not in VERDICTS:
        res.fail(f"verdict must be one of {sorted(VERDICTS)}, got {verdict!r}")
        return res
    try:
        commands = int(header.get("commands_run", ""))
    except ValueError:
        res.fail("commands_run is missing or not a number")
        return res
    findings = _section(text, "Findings") or ""
    has_findings = bool(findings.strip()) and findings.strip().lower().rstrip(".") not in ("none", "- none")
    if verdict != "approve" and not has_findings:
        res.fail("a verdict other than approve needs at least one finding with evidence")
        return res
    if verdict == "approve":
        if commands < 2:
            res.fail("approve needs commands_run of at least 2")
            return res
        if ci_green is False:
            res.reasons.append("approve overridden to code_issue: CI is not green")
            verdict = "code_issue"
    res.data.update({"verdict": verdict, "commands_run": commands})
    return res
