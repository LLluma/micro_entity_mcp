"""Tests for path_in_history."""

import subprocess
from pathlib import Path

from micro_entity.vcs import commit_paths, path_in_history


def _git(*args: str, cwd: str) -> subprocess.CompletedProcess[str]:
    """Run ``git <args>`` inside *cwd*, returning CompletedProcess (unchecked)."""
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_path_in_history_committed_file(tmp_path: Path) -> None:
    """After creating and committing a file, path_in_history returns True."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    f = tmp_path / "hello.txt"
    f.write_text("world")
    commit_paths(tmp_path, [f], "add hello.txt")

    assert path_in_history(tmp_path, f) is True


def test_path_in_history_uncommitted_path(tmp_path: Path) -> None:
    """A path that was never committed returns False."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    # Never create or commit this file.
    never_file = tmp_path / "never-existed.txt"

    assert path_in_history(tmp_path, never_file) is False


def test_path_in_history_deleted_but_committed(tmp_path: Path) -> None:
    """A file that was committed then deleted-and-the-deletion-committed
    still returns True (it remains in history)."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    f = tmp_path / "removed.txt"
    f.write_text("bye")
    commit_paths(tmp_path, [f], "add removed.txt")

    # Delete and commit the deletion.
    f.unlink()
    _git("add", "removed.txt", cwd=str(tmp_path))
    _git("commit", "-m", "delete removed.txt", cwd=str(tmp_path))

    # File is gone from filesystem but was in history.
    assert path_in_history(tmp_path, f) is True
