"""Tools the agents may call (ADR-005).

Design rules:
  * Every tool is our own small function. A tool that is not in an agent's
    allow-list does not exist for that agent.
  * Output is always capped, so one call can never flood a small context
    window (free-tier limits, ADR-006).
  * File access is confined to the workspace; writes are confined to explicit
    directories and never touch `.github/`.
  * `run_command` uses no shell, only allowed programs, a scrubbed
    environment (no keys, no tokens) and a time limit.
"""

from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

MAX_READ_LINES = 120
MAX_SEARCH_MATCHES = 20
MAX_LIST_ENTRIES = 80
MAX_OUTPUT_CHARS = 3000
COMMAND_TIMEOUT = 180
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules", ".mypy_cache", ".ruff_cache"}
SEARCH_SUFFIXES = {".py", ".md", ".rst", ".txt", ".toml", ".cfg", ".yml", ".yaml"}
ALLOWED_PROGRAMS = {"python", "python3", "pytest", "git"}
ALLOWED_GIT = {"diff", "status", "log", "show"}  # read-only git for reviewing
SAFE_ENV_NAMES = {"PATH", "SYSTEMROOT", "HOME", "USERPROFILE", "TEMP", "TMP", "TMPDIR", "LANG", "VIRTUAL_ENV", "PYTHONPATH"}
SECRET_WORDS = ("KEY", "TOKEN", "SECRET", "PASSWORD")


class ToolError(Exception):
    """A tool refused or failed; the message goes back to the model."""


def truncate(text: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    """Keep the head and the tail; failing output usually matters at the end."""
    if len(text) <= limit:
        return text
    half = limit // 2
    return text[:half] + f"\n... [{len(text) - limit} characters cut] ...\n" + text[-half:]


def scrubbed_env() -> Dict[str, str]:
    env = {}
    for name, value in os.environ.items():
        if name.upper() in SAFE_ENV_NAMES and not any(w in name.upper() for w in SECRET_WORDS):
            env[name] = value
    return env


class Workspace:
    def __init__(self, root: str, writable: Optional[List[str]] = None, artifact_dir: Optional[str] = None):
        self.root = Path(root).resolve()
        # directories (relative to root) where edit_file / write_file may write
        self.writable = [(self.root / w).resolve() for w in (writable or [])]
        self.artifact_dir = Path(artifact_dir).resolve() if artifact_dir else None

    def resolve(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if p != self.root and self.root not in p.parents:
            raise ToolError("path is outside the workspace")
        if any(part in SKIP_DIRS for part in p.relative_to(self.root).parts):
            raise ToolError("path is in an ignored directory")
        return p

    def resolve_writable(self, rel: str) -> Path:
        p = self.resolve(rel)
        rel_parts = p.relative_to(self.root).parts
        if rel_parts and rel_parts[0] == ".github":
            raise ToolError("editing .github/ is not allowed")
        if not any(d == p or d in p.parents for d in self.writable):
            allowed = ", ".join(str(d.relative_to(self.root)) for d in self.writable) or "nothing"
            raise ToolError(f"writing is not allowed here; writable: {allowed}")
        return p

    # ---------------- reading tools ----------------
    def read_file(self, path: str, start_line: int = 1, end_line: Optional[int] = None) -> str:
        p = self.resolve(path)
        if not p.is_file():
            raise ToolError("not a file")
        lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        start = max(1, int(start_line))
        end = int(end_line) if end_line else start + MAX_READ_LINES - 1
        end = min(end, start + MAX_READ_LINES - 1, len(lines))
        if start > len(lines):
            raise ToolError(f"file has only {len(lines)} lines")
        body = "\n".join(f"{i}: {lines[i - 1]}" for i in range(start, end + 1))
        note = f"\n[showing lines {start}-{end} of {len(lines)}]"
        return truncate(body + note)

    def list_files(self, path: str = ".") -> str:
        p = self.resolve(path)
        if not p.is_dir():
            raise ToolError("not a directory")
        entries = []
        for child in sorted(p.iterdir()):
            if child.name in SKIP_DIRS:
                continue
            entries.append(child.name + ("/" if child.is_dir() else ""))
        more = len(entries) - MAX_LIST_ENTRIES
        shown = entries[:MAX_LIST_ENTRIES]
        return "\n".join(shown) + (f"\n[{more} more entries]" if more > 0 else "")

    def search(self, pattern: str, path: str = ".") -> str:
        try:
            rx = re.compile(pattern)
        except re.error as exc:
            raise ToolError(f"bad regular expression: {exc}")
        base = self.resolve(path)
        files = [base] if base.is_file() else sorted(base.rglob("*"))
        hits: List[str] = []
        for f in files:
            if not f.is_file() or f.suffix not in SEARCH_SUFFIXES:
                continue
            if any(part in SKIP_DIRS for part in f.relative_to(self.root).parts):
                continue
            try:
                text = f.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for n, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{f.relative_to(self.root).as_posix()}:{n}: {line.strip()[:160]}")
                    if len(hits) >= MAX_SEARCH_MATCHES:
                        return truncate("\n".join(hits) + f"\n[stopped at {MAX_SEARCH_MATCHES} matches]")
        return truncate("\n".join(hits)) if hits else "no matches"

    # ---------------- writing tools ----------------
    def edit_file(self, path: str, old_string: str, new_string: str) -> str:
        p = self.resolve_writable(path)
        if not p.is_file():
            raise ToolError("file does not exist (use write_file to create a new file)")
        text = p.read_text(encoding="utf-8")
        count = text.count(old_string)
        if count == 0:
            raise ToolError("old_string was not found; read the file again and copy it exactly")
        if count > 1:
            raise ToolError(f"old_string appears {count} times; include more surrounding lines to make it unique")
        p.write_text(text.replace(old_string, new_string, 1), encoding="utf-8")
        return "edited"

    def write_file(self, path: str, content: str) -> str:
        p = self.resolve_writable(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"wrote {len(content)} characters"

    def write_artifact(self, name: str, content: str) -> str:
        if self.artifact_dir is None:
            raise ToolError("no artifact directory is configured")
        if name not in ALLOWED_ARTIFACTS:
            raise ToolError(f"artifact name must be one of {sorted(ALLOWED_ARTIFACTS)}")
        self.artifact_dir.mkdir(parents=True, exist_ok=True)
        (self.artifact_dir / name).write_text(content, encoding="utf-8")
        return f"saved {name}"

    # ---------------- command tool ----------------
    def run_command(self, command: str) -> str:
        try:
            argv = shlex.split(command)
        except ValueError as exc:
            raise ToolError(f"cannot parse command: {exc}")
        if not argv:
            raise ToolError("empty command")
        program = Path(argv[0]).name
        if program not in ALLOWED_PROGRAMS:
            raise ToolError(f"program not allowed; allowed: {sorted(ALLOWED_PROGRAMS)}")
        if program == "git" and (len(argv) < 2 or argv[1] not in ALLOWED_GIT):
            raise ToolError(f"only these git subcommands are allowed: {sorted(ALLOWED_GIT)}")
        if program in ("python", "python3"):
            argv[0] = sys.executable
        try:
            done = subprocess.run(
                argv,
                cwd=self.root,
                env=scrubbed_env(),
                capture_output=True,
                text=True,
                timeout=COMMAND_TIMEOUT,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            raise ToolError(f"command timed out after {COMMAND_TIMEOUT} seconds")
        except OSError as exc:
            raise ToolError(f"could not run command: {type(exc).__name__}")
        out = (done.stdout or "") + (done.stderr or "")
        lines = out.splitlines()
        tail = "\n".join(lines[-60:])
        return truncate(f"exit code {done.returncode}\n{tail}")


ALLOWED_ARTIFACTS = {"spec.md", "design.md", "review.md"}


# ---------------- tool registry (what each agent gets) ----------------
def _schema(name: str, description: str, props: Dict[str, Any], required: List[str]) -> Dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


S = {"type": "string"}
I = {"type": "integer"}
SCHEMAS: Dict[str, Dict[str, Any]] = {
    "read_file": _schema(
        "read_file",
        f"Read lines of a file (at most {MAX_READ_LINES} lines per call). Use start_line and end_line.",
        {"path": S, "start_line": I, "end_line": I},
        ["path"],
    ),
    "list_files": _schema("list_files", "List a directory.", {"path": S}, []),
    "search": _schema(
        "search",
        f"Regex search in text files; at most {MAX_SEARCH_MATCHES} matching lines are returned.",
        {"pattern": S, "path": S},
        ["pattern"],
    ),
    "edit_file": _schema(
        "edit_file",
        "Replace one exact, unique piece of text in an existing file.",
        {"path": S, "old_string": S, "new_string": S},
        ["path", "old_string", "new_string"],
    ),
    "write_file": _schema(
        "write_file", "Create or overwrite a file in a writable directory.", {"path": S, "content": S}, ["path", "content"]
    ),
    "write_artifact": _schema(
        "write_artifact",
        "Save your final document. name is one of spec.md, design.md, review.md.",
        {"name": S, "content": S},
        ["name", "content"],
    ),
    "run_command": _schema(
        "run_command",
        "Run python, pytest or read-only git (diff, status, log, show). No shell. Output is shortened.",
        {"command": S},
        ["command"],
    ),
}

# allow-lists per agent (ADR-005 table)
AGENT_TOOLS = {
    "planner": ["read_file", "list_files", "search", "write_artifact"],        # stage 2 (design)
    "planner_spec": ["write_artifact"],                                        # stage 1: no exploring, just write
    "builder": ["read_file", "list_files", "search", "edit_file", "write_file", "run_command"],
    "reviewer": ["read_file", "list_files", "search", "run_command", "write_artifact"],
}


class ToolSet:
    def __init__(self, agent: str, workspace: Workspace):
        if agent not in AGENT_TOOLS:
            raise ValueError(f"unknown agent {agent!r}")
        self.agent = agent
        self.names = AGENT_TOOLS[agent]
        self._impl: Dict[str, Callable[..., str]] = {n: getattr(workspace, n) for n in self.names}

    def schemas(self) -> List[Dict[str, Any]]:
        return [SCHEMAS[n] for n in self.names]

    def call(self, name: str, arguments: Any) -> str:
        """Run a tool for the model. Never raises: errors become text for the model."""
        if name not in self._impl:
            return f"error: tool {name!r} is not available to the {self.agent} agent"
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments or "{}")
            except json.JSONDecodeError:
                return "error: arguments were not valid JSON"
        if not isinstance(arguments, dict):
            return "error: arguments must be an object"
        try:
            return self._impl[name](**arguments)
        except ToolError as exc:
            return f"error: {exc}"
        except TypeError as exc:
            return f"error: wrong arguments for {name}: {exc}"
        except Exception as exc:  # a tool bug must not kill the run
            return f"error: {type(exc).__name__} while running {name}"
