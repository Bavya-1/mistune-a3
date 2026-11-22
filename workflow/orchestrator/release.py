"""Stage 5 (release) and the run status comment. Plain code, no model (ADR-001, ADR-005).

    python release.py pr      --artifacts DIR --issue-number N --run-id ID
    python release.py comment --artifacts DIR --issue-number N   (reads RESULTS env)

Only this code writes to GitHub; the agents never hold a token (ADR-005).
Everything goes through the `gh` CLI with an argument list (no shell), and every
call names the repository explicitly, so a pull request can never land in the
upstream project by accident (assignment rule: your fork only).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

UPSTREAM = "lepture/mistune"   # never touch this repository
CI_WORKFLOW = "tests.yml"      # the project's own CI (it has workflow_dispatch)
CI_TIMEOUT_S = 25 * 60
POLL_S = 20


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.is_file() else ""


def sh(argv: List[str], check: bool = True) -> subprocess.CompletedProcess:
    res = subprocess.run(argv, capture_output=True, text=True, shell=False)
    if check and res.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(argv[:4])}...\n{res.stderr.strip()[-800:]}")
    return res


def target_repo() -> str:
    """The repository we may write to. Refuses the upstream project."""
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not re.fullmatch(r"[\w.-]+/[\w.-]+", repo):
        raise SystemExit("GITHUB_REPOSITORY is not set to owner/name")
    if repo.lower() == UPSTREAM:
        raise SystemExit("refusing to write to the upstream project")
    origin = sh(["git", "remote", "get-url", "origin"]).stdout.strip().lower()
    if repo.lower() not in origin:
        raise SystemExit(f"origin ({origin}) is not {repo}; refusing to push")
    return repo


def section(text: str, heading: str) -> str:
    m = re.search(r"^##\s+" + re.escape(heading) + r"\s*$", text, re.I | re.M)
    if not m:
        return ""
    rest = text[m.end():]
    nxt = re.search(r"^##\s+", rest, re.M)
    return (rest[: nxt.start()] if nxt else rest).strip()


def issue_title(artifacts: Path) -> str:
    try:
        return json.loads(read(artifacts / "issue.json")).get("title", "")
    except ValueError:
        return ""


def write_pr_md(artifacts: Path, number: str, branch: str, run_url: str) -> Path:
    spec, design = read(artifacts / "spec.md"), read(artifacts / "design.md")
    diff = read(artifacts / "diff.patch")
    files = sorted(set(re.findall(r"^diff --git a/(\S+) b/", diff, re.M)))
    first_line = (read(artifacts / "test_report.md").splitlines() or ["", "", ""])
    result_line = next((ln for ln in first_line if ln.startswith("Result:")), "Result: see test_report.md")
    lines = [
        f"## AutoSE: {issue_title(artifacts)} (issue #{number})",
        "",
        f"Opened by the AutoSE workflow for issue #{number}. **A person must review and merge or close this pull request.**",
        "",
        "### Acceptance criteria (from spec.md)",
        section(spec, "Acceptance criteria") or "(none found)",
        "",
        "### Files changed",
        *[f"- `{f}`" for f in files],
        "",
        "### Tests",
        result_line,
        "",
        "### Plan summary (from design.md)",
        section(design, "Files and functions to change") or "(none found)",
        "",
        f"Run: {run_url}",
        f"Branch: `{branch}`",
    ]
    path = artifacts / "pr.md"
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def wait_for_ci(repo: str, branch: str, started: float) -> dict:
    """Dispatch the project's CI on the branch and wait for it (a PR opened with
    GITHUB_TOKEN does not start CI by itself)."""
    sh(["gh", "workflow", "run", CI_WORKFLOW, "--repo", repo, "--ref", branch])
    deadline = time.time() + CI_TIMEOUT_S
    run_id: Optional[int] = None
    while time.time() < deadline:
        time.sleep(POLL_S)
        res = sh(
            ["gh", "run", "list", "--repo", repo, "--workflow", CI_WORKFLOW, "--branch", branch,
             "--event", "workflow_dispatch", "--limit", "5", "--json", "databaseId,status,conclusion,url,createdAt"],
            check=False,
        )
        try:
            runs = json.loads(res.stdout or "[]")
        except ValueError:
            runs = []
        runs = [r for r in runs if _ts(r["createdAt"]) >= started - 5]
        if not runs:
            continue
        r = max(runs, key=lambda x: x["createdAt"])
        run_id = r["databaseId"]
        if r["status"] == "completed":
            return {"run_id": run_id, "conclusion": r["conclusion"], "url": r["url"]}
    return {"run_id": run_id, "conclusion": "timed_out", "url": ""}


def _ts(iso: str) -> float:
    return time.mktime(time.strptime(iso, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone


def cmd_pr(args: argparse.Namespace) -> int:
    repo = target_repo()
    artifacts = Path(args.artifacts)
    number, run_id = args.issue_number, args.run_id
    branch = f"autose/issue-{number}-{run_id}"
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    run_url = f"{server}/{repo}/actions/runs/{run_id}"

    diff = artifacts / "diff.patch"
    if not read(diff).strip():
        print("no diff to release")
        return 2
    sh(["git", "config", "user.name", "autose-bot"])
    sh(["git", "config", "user.email", "autose-bot@users.noreply.github.com"])
    sh(["git", "switch", "-c", branch])
    sh(["git", "apply", "--index", str(diff.resolve())])
    sh(["git", "commit", "-m", f"AutoSE: changes for issue #{number}\n\nRun: {run_url}"])
    sh(["git", "push", "origin", branch])

    pr_md = write_pr_md(artifacts, number, branch, run_url)
    title = f"AutoSE: {issue_title(artifacts)} (#{number})"[:200]
    res = sh(["gh", "pr", "create", "--repo", repo, "--base", "main", "--head", branch,
              "--title", title, "--body-file", str(pr_md)])
    pr_url = res.stdout.strip().splitlines()[-1]
    (artifacts / "pr_link.txt").write_text(pr_url + "\n", encoding="utf-8")
    print("opened", pr_url)

    started = time.time()
    ci = wait_for_ci(repo, branch, started)
    (artifacts / "ci.json").write_text(json.dumps(ci, indent=2), encoding="utf-8")
    ok = ci["conclusion"] == "success"
    note = f"CI on `{branch}`: **{ci['conclusion']}** {ci['url']}"
    with pr_md.open("a", encoding="utf-8") as f:
        f.write("\n" + note + "\n")
    sh(["gh", "pr", "comment", pr_url, "--repo", repo, "--body", note], check=False)
    if not ok:
        print("CI did not pass:", ci)
        return 2
    return 0


def cmd_comment(args: argparse.Namespace) -> int:
    """One status comment on the issue so anyone can follow the run."""
    repo = target_repo()
    artifacts = Path(args.artifacts)
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    run_url = f"{server}/{repo}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"
    results = os.environ.get("RESULTS", "")
    pr_link = read(artifacts / "pr_link.txt").strip()
    state = read(artifacts / "run_state.json")
    last = ""
    try:
        events = json.loads(state).get("events", [])
        last = "; ".join(f"{e['stage']}: {e['status']}" for e in events[-4:])
    except (ValueError, KeyError):
        pass
    body = ["### AutoSE run finished", "", f"- Results: {results}", f"- Run and artifacts: {run_url}"]
    if pr_link:
        body.append(f"- Pull request (a person decides): {pr_link}")
    if last:
        body.append(f"- Last events: {last}")
    sh(["gh", "issue", "comment", args.issue_number, "--repo", repo, "--body", "\n".join(body)])
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("pr", "comment"):
        p = sub.add_parser(name)
        p.add_argument("--artifacts", required=True)
        p.add_argument("--issue-number", required=True)
        if name == "pr":
            p.add_argument("--run-id", required=True)
    args = ap.parse_args()
    return cmd_pr(args) if args.cmd == "pr" else cmd_comment(args)


if __name__ == "__main__":
    sys.exit(main())
