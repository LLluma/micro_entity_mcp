"""Tests for commit_paths."""

import subprocess
from pathlib import Path

from micro_entity.vcs import commit_paths


def _git(*args: str, cwd: str) -> subprocess.CompletedProcess[str]:
    """Run ``git <args>`` inside *cwd*, returning CompletedProcess (unchecked)."""
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _commit_count(repo_root: str) -> int:
    """Return the number of commits (on the current branch) in *repo_root*."""
    r = _git("log", "--oneline", cwd=repo_root)
    if r.returncode != 0:
        return 0
    lines = [item for item in r.stdout.strip().splitlines() if item.strip()]
    return len(lines)


def _commit_files(repo_root: str, sha: str) -> list[str]:
    """Return the list of file paths touched by *sha*."""
    r = _git("show", "--name-only", "--format=", sha, cwd=repo_root)
    return [f for f in r.stdout.strip().splitlines() if f.strip()]


def _last_commit_files(repo_root: str) -> list[str]:
    """Return the list of file paths touched by the HEAD commit."""
    r = _git("show", "--name-only", "--format=", "HEAD", cwd=repo_root)
    return [f for f in r.stdout.strip().splitlines() if f.strip()]


# --- Tests ----------------------------------------------------------------


def test_commit_new_file(tmp_path: Path) -> None:
    """Create and commit_paths a new file → returns a sha; git log shows one
    commit; that commit touches only that file."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    new_file = tmp_path / "new.txt"
    new_file.write_text("hello")

    sha = commit_paths(tmp_path, [new_file], "add new file")

    assert isinstance(sha, str)
    assert len(sha) == 40  # full sha

    assert _commit_count(str(tmp_path)) == 1
    files = _last_commit_files(str(tmp_path))
    assert files == ["new.txt"]


def test_commit_modified_tracked_file(tmp_path: Path) -> None:
    """Modify a tracked file, commit_paths → returns a sha, one new commit
    touching only that file."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    tracked = tmp_path / "tracked.txt"
    tracked.write_text("v1")
    _git("add", "tracked.txt", cwd=str(tmp_path))
    _git("commit", "-m", "initial", cwd=str(tmp_path))

    # Modify
    tracked.write_text("v2")

    sha = commit_paths(tmp_path, [tracked], "update tracked")

    assert isinstance(sha, str)
    assert len(sha) == 40
    assert _commit_count(str(tmp_path)) == 2
    files = _last_commit_files(str(tmp_path))
    assert files == ["tracked.txt"]


def test_no_changes_returns_none(tmp_path: Path) -> None:
    """commit_paths again with no change to those paths → returns None, no
    new commit added."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    f = tmp_path / "a.txt"
    f.write_text("data")
    _git("add", "a.txt", cwd=str(tmp_path))
    _git("commit", "-m", "initial", cwd=str(tmp_path))

    # Nothing touched since last commit.
    result = commit_paths(tmp_path, [f], "no change")
    assert result is None
    assert _commit_count(str(tmp_path)) == 1


def test_delete_tracked_file(tmp_path: Path) -> None:
    """Delete a tracked file then commit_paths → records the deletion."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    tracked = tmp_path / "removed.txt"
    tracked.write_text("bye")
    _git("add", "removed.txt", cwd=str(tmp_path))
    _git("commit", "-m", "add removed.txt", cwd=str(tmp_path))

    # Delete from filesystem
    tracked.unlink()

    sha = commit_paths(tmp_path, [tracked], "delete removed.txt")

    assert isinstance(sha, str)
    assert len(sha) == 40
    assert _commit_count(str(tmp_path)) == 2
    files = _last_commit_files(str(tmp_path))
    assert files == ["removed.txt"]

    # Confirm deletion is recorded in the commit.
    show = _git("show", "--name-status", "--format=", sha, cwd=str(tmp_path))
    assert "D\tremoved.txt" in show.stdout or "D removed.txt" in show.stdout


def test_unrelated_dirty_files_ignored(tmp_path: Path) -> None:
    """Create a second dirty file, commit only the first path. Assert the
    second file is still uncommitted and not in that commit."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    first = tmp_path / "first.txt"
    first.write_text("aa")
    _git("add", "first.txt", cwd=str(tmp_path))
    _git("commit", "-m", "initial", cwd=str(tmp_path))

    # Modify first (our target)
    first.write_text("bb")

    # Create a second dirty file (NOT our target)
    second = tmp_path / "second.txt"
    second.write_text("secret")

    sha = commit_paths(tmp_path, [first], "update first")

    assert isinstance(sha, str)
    assert len(sha) == 40
    files = _last_commit_files(str(tmp_path))
    assert files == ["first.txt"]
    assert "second.txt" not in files

    # Confirm the dirty second file is still uncommitted.
    status = _git("status", "--porcelain", cwd=str(tmp_path))
    assert "second.txt" in status.stdout
