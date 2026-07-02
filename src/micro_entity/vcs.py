"""Git repo-root discovery for micro_entity."""

from __future__ import annotations

import subprocess
from pathlib import Path


class NotAGitRepoError(Exception):
    """Raised when *path* is not inside a git repository."""


def find_repo_root(path: Path) -> Path:
    """Return the enclosing git repository root for *path*.

    Walks up from the directory containing *path* by delegating to
    ``git rev-parse --show-toplevel``.

    Raises:
        NotAGitRepoError: if no git repository contains *path*.
    """
    query_dir = path if path.is_dir() else path.parent

    try:
        result = subprocess.run(
            ["git", "-C", str(query_dir), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise NotAGitRepoError(
            f"Not a git repo (query dir: {query_dir}): {exc.stderr.strip()}"
        ) from exc

    return Path(result.stdout.strip()).resolve()


def commit_paths(repo_root: Path, paths: list[Path], message: str) -> str | None:
    """Stage and commit *paths* inside *repo_root*, returning the new commit SHA or ``None``.

    Returns ``None`` when none of the given paths have staged changes (i.e.
    there is nothing to commit for those paths — no exception is raised).
    """
    # Stage exactly the given paths.
    for p in paths:
        subprocess.run(
            ["git", "-C", str(repo_root), "add", "--", str(p)],
            capture_output=True,
            text=True,
            check=True,
        )

    # Attempt the commit with identity flags so it works without user config.
    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "-c",
            "user.name=micro_entity",
            "-c",
            "user.email=micro_entity@localhost",
            "commit",
            "-m",
            message,
            "--",
            *[str(p) for p in paths],
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        output = result.stdout + result.stderr
        if "nothing to commit" in output or "no changes added" in output:
            return None
        raise subprocess.CalledProcessError(
            result.returncode, result.args, result.stdout, result.stderr
        )

    # Return full SHA of HEAD.
    sha_result = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=True,
    )
    return sha_result.stdout.strip()


def file_log(repo_root: Path, path: Path, limit: int) -> list[dict]:
    """Return the git log entries for *path* up to *limit* commits.

    Each entry is ``{"sha": str, "date": str, "message": str}`` ordered
    newest-first (git log default).
    """
    rel = str(path.relative_to(repo_root)).replace("\\", "/")

    result = subprocess.run(
        [
            "git",
            "-C",
            str(repo_root),
            "log",
            f"--max-count={limit}",
            "--format=%H%x1f%cI%x1f%s",
            "--",
            rel,
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    entries: list[dict] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        sha, date, message = line.split("\x1f", 2)
        entries.append({"sha": sha, "date": date, "message": message})

    return entries


def file_diff(repo_root: Path, path: Path, ref: str, to: str | None) -> str:
    """Return the unified diff for *path* between git *ref* and *to*.

    When *to* is ``None``, the diff is between *ref* and the working tree.
    When *to* is given, the diff is between the two refs.

    Returns the diff text (stdout). An empty string when there is no
    difference is a valid result, not an error.
    """
    rel = str(path.relative_to(repo_root)).replace("\\", "/")

    cmd = ["git", "-C", str(repo_root), "diff", "--", rel]
    if to is not None:
        cmd.insert(4, ref)
        cmd.insert(5, to)
    else:
        cmd.insert(4, ref)

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def read_at_ref(repo_root: Path, path: Path, ref: str) -> str:
    """Return file *path* content as text at git *ref*.

    Uses ``git show <ref>:<relpath>`` and returns the stdout content.

    Raises:
        subprocess.CalledProcessError: if the ref or path is unknown.
    """
    rel = str(path.relative_to(repo_root)).replace("\\", "/")

    result = subprocess.run(
        ["git", "-C", str(repo_root), "show", f"{ref}:{rel}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout
