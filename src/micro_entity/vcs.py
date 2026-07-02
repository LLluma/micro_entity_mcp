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
