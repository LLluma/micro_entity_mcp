"""Tests for last_change_diff."""

from pathlib import Path

from micro_entity.vcs import commit_paths, last_change_diff


def _init_repo(tmp_path: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)


def test_last_change_diff_two_commits(tmp_path: Path) -> None:
    """Two commits: file goes A→B. Diff must show the B change (not empty)."""
    _init_repo(tmp_path)

    f = tmp_path / "file.txt"
    f.write_text("A")
    commit_paths(tmp_path, [f], "first commit")

    f.write_text("B")
    commit_paths(tmp_path, [f], "second commit")

    result = last_change_diff(tmp_path, f)
    assert result != "", "expected non-empty diff for second commit"
    assert "B" in result


def test_last_change_diff_first_commit(tmp_path: Path) -> None:
    """Single-commit file: diff against empty tree must show additions."""
    _init_repo(tmp_path)

    f = tmp_path / "file.txt"
    f.write_text("v1")
    sha = commit_paths(tmp_path, [f], "initial commit")

    assert sha is not None

    result = last_change_diff(tmp_path, f)
    assert result != "", "expected non-empty diff for first commit"
    # Against empty tree: all lines are additions (start with +)
    lines = [ln for ln in result.splitlines() if ln.startswith("+") and not ln.startswith("+++")]
    assert len(lines) >= 1, "expected at least one addition line"


def test_last_change_diff_scoped_to_one_file(tmp_path: Path) -> None:
    """When two files are committed together, diff for one must not mention the
    other file's content or path."""
    _init_repo(tmp_path)

    f_a = tmp_path / "file_a.txt"
    f_b = tmp_path / "file_b.txt"

    f_a.write_text("alpha")
    f_b.write_text("beta")
    commit_paths(tmp_path, [f_a, f_b], "initial both")

    # Second commit modifies only f_a
    f_a.write_text("ALPHA")
    commit_paths(tmp_path, [f_a], "update a")

    result = last_change_diff(tmp_path, f_a)
    # Must contain f_a's new content
    assert "ALPHA" in result
    # Must NOT contain f_b's unique content
    assert "beta" not in result
    assert "BETA" not in result
    # Path must be scoped: diff header should reference file_a
    # The --file-mode header or filename in diff header
    assert "file_a.txt" in result
