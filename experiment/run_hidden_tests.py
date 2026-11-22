"""Run one issue's hidden acceptance tests against a branch or commit, and record the result.

The hidden tests live OUTSIDE the repository (assignment rule). This script checks the chosen
ref out into a temporary folder, copies the hidden test file in there only, runs it, and removes
the folder again. Nothing is ever added to your working tree.

    python experiment/run_hidden_tests.py --issue 3 --ref origin/autose/issue-5-123456 --run-id 123456
    python experiment/run_hidden_tests.py --issue 3 --ref f7ec702 --run-id baseline

Each call appends one row to results/results_hidden.csv (issue, ref, run id, passed, failed).
Use --ref f7ec702 once per issue to record the baseline (before any change).
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import List, Tuple

REPO = Path(__file__).resolve().parents[1]
DEFAULT_HIDDEN = REPO.parent / "a3-private" / "hidden_tests"
OUT_CSV = REPO / "results" / "results_hidden.csv"


def run(argv: List[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(argv, cwd=cwd, capture_output=True, text=True, shell=False)


def find_test_file(hidden_dir: Path, issue: int) -> Path:
    matches = sorted(hidden_dir.glob(f"test_issue{issue}_*.py"))
    if not matches:
        raise SystemExit(f"no hidden test file test_issue{issue}_*.py in {hidden_dir}")
    return matches[0]


def count(output: str) -> Tuple[int, int]:
    passed = re.search(r"(\d+) passed", output)
    failed = re.search(r"(\d+) failed", output)
    errors = re.search(r"(\d+) error", output)
    return int(passed.group(1)) if passed else 0, (int(failed.group(1)) if failed else 0) + (
        int(errors.group(1)) if errors else 0
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--issue", type=int, required=True, help="1-5, the experiment issue number")
    ap.add_argument("--ref", required=True, help="branch, commit or origin/<branch> to test")
    ap.add_argument("--run-id", default="", help="Actions run id, or 'baseline'")
    ap.add_argument("--hidden-dir", default=os.environ.get("AUTOSE_HIDDEN_DIR", str(DEFAULT_HIDDEN)))
    args = ap.parse_args()

    test_file = find_test_file(Path(args.hidden_dir), args.issue)
    if REPO in test_file.resolve().parents:
        raise SystemExit("the hidden tests must stay outside the repository until the experiments are done")

    tmp = Path(tempfile.mkdtemp(prefix="autose-hidden-"))
    work = tmp / "checkout"
    try:
        added = run(["git", "worktree", "add", "--detach", str(work), args.ref], REPO)
        if added.returncode != 0:
            raise SystemExit(f"could not check out {args.ref}: {added.stderr.strip()}")
        shutil.copy(test_file, work / "tests" / test_file.name)
        result = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--tb=no", f"tests/{test_file.name}"], work)
        passed, failed = count(result.stdout + result.stderr)
        print(result.stdout.strip().splitlines()[-1] if result.stdout.strip() else result.stderr.strip()[-300:])
    finally:
        run(["git", "worktree", "remove", "--force", str(work)], REPO)
        shutil.rmtree(tmp, ignore_errors=True)

    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    new = not OUT_CSV.exists()
    with OUT_CSV.open("a", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if new:
            writer.writerow(["time_utc", "issue", "ref", "run_id", "passed", "failed", "total"])
        writer.writerow([time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), args.issue, args.ref, args.run_id, passed, failed, passed + failed])
    print(f"issue {args.issue} @ {args.ref}: {passed} passed, {failed} failed -> {OUT_CSV.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
