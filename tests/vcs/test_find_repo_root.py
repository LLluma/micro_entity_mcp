"""Tests for find_repo_root."""

import subprocess
from pathlib import Path

import pytest

from micro_entity.vcs import NotAGitRepoError, find_repo_root


def test_git_repo_root_inside_repo(tmp_path: Path) -> None:
    """find_repo_root resolves to the git root for a file in a repo."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    repo = tmp_path.resolve()
    foo = tmp_path / "foo" / "bar"
    foo.mkdir(parents=True)

    result = find_repo_root(foo)
    assert result == repo


def test_git_repo_root_for_file_not_dir(tmp_path: Path) -> None:
    """find_repo_root resolves when *path* is a file, not a directory."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    repo = tmp_path.resolve()
    nested = tmp_path / "a" / "b"
    nested.mkdir(parents=True)
    file_in_repo = nested / "thing.txt"
    file_in_repo.write_text("x")

    result = find_repo_root(file_in_repo)
    assert result == repo


def test_plain_dir_raises(tmp_path: Path) -> None:
    """find_repo_root raises NotAGitRepoError for a non-git directory."""
    with pytest.raises(NotAGitRepoError):
        find_repo_root(tmp_path)
