"""Tests for file_diff."""

import subprocess
from pathlib import Path

from micro_entity.vcs import commit_paths, file_diff


def _init_repo(tmp_path: Path) -> None:
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)


def test_file_diff_two_commits_no_to(tmp_path: Path) -> None:
    """With a CLEAN working tree, diff(HEAD~1, None) shows the change between commits."""
    _init_repo(tmp_path)

    f = tmp_path / "file.txt"
    f.write_text("A")
    commit_paths(tmp_path, [f], "first commit")

    f.write_text("B")
    commit_paths(tmp_path, [f], "second commit")

    # WORKING TREE is clean (matches HEAD which has "B").
    # git diff HEAD~1 -- file.txt  compares HEAD~1 ({path}=content="A") vs
    # working tree (content="B"), yielding a patch with "-A" and "+B".
    result = file_diff(tmp_path, f, "HEAD~1", None)
    assert "B" in result
    assert "A" in result


def test_file_diff_two_commits_with_to(tmp_path: Path) -> None:
    """Diff between two explicit refs shows the change."""
    _init_repo(tmp_path)

    f = tmp_path / "file.txt"
    f.write_text("A")
    commit_paths(tmp_path, [f], "first commit")

    f.write_text("B")
    commit_paths(tmp_path, [f], "second commit")

    result = file_diff(tmp_path, f, "HEAD~1", "HEAD")
    assert "B" in result
    assert "-A" in result or "B" in result


def test_file_diff_identical_refs_returns_empty(tmp_path: Path) -> None:
    """Same ref twice → empty string."""
    _init_repo(tmp_path)

    f = tmp_path / "file.txt"
    f.write_text("A")
    commit_paths(tmp_path, [f], "first commit")

    result = file_diff(tmp_path, f, "HEAD", "HEAD")
    assert result == ""


def test_file_diff_scoped_to_one_file(tmp_path: Path) -> None:
    """Diff for file_a must not contain content unique to file_b."""
    _init_repo(tmp_path)

    f_a = tmp_path / "file_a.txt"
    f_b = tmp_path / "file_b.txt"

    f_a.write_text("alpha")
    f_b.write_text("beta")
    commit_paths(tmp_path, [f_a, f_b], "initial")

    f_a.write_text("ALPHA")
    f_b.write_text("BETA")
    commit_paths(tmp_path, [f_a, f_b], "update both")

    result_a = file_diff(tmp_path, f_a, "HEAD~1", "HEAD")
    # Should contain the file_a changes
    assert "ALPHA" in result_a
    # Must NOT contain the unique content of file_b
    assert "beta" not in result_a
    assert "BETA" not in result_a


def test_file_diff_direction_pinned(tmp_path: Path) -> None:
    """The diff *ref → to* shows old→new direction: `-old` and `+new` in output.

    When ``file_diff(root, file, ref, to)`` is called with ``ref="HEAD~1"`` and
    ``to="HEAD"``, the result should read like "git diff HEAD~1 HEAD -- file":
    it goes FROM the older state (old) TO the newer state (new), so the patch
    must remove old (line starting with ``-``) and add new (line starting with
    ``+``). This pins the ref→to direction; if the args are reversed the
    patch would show ``+old`` / ``-new`` instead.
    """
    _init_repo(tmp_path)

    f = tmp_path / "file.txt"
    f.write_text("old")
    commit_paths(tmp_path, [f], "first")

    f.write_text("new")
    commit_paths(tmp_path, [f], "second")

    old_ref = "HEAD~1"
    new_ref = "HEAD"
    result = file_diff(tmp_path, f, old_ref, new_ref)

    # Must have removed "old" (a line starting with -, containing "old")
    assert any(line.startswith("-") and "old" in line for line in result.splitlines()), (
        f"Expected a `-` line containing 'old', got:\\n{result}"
    )
    # Must have added "new" (a line starting with +, containing "new")
    assert any(line.startswith("+") and "new" in line for line in result.splitlines()), (
        f"Expected a `+` line containing 'new', got:\\n{result}"
    )
