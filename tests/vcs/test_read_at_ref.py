"""Tests for read_at_ref."""

import subprocess
from pathlib import Path

import pytest

from micro_entity.vcs import commit_paths, read_at_ref


def _git(*args: str, cwd: str) -> subprocess.CompletedProcess[str]:
    """Run ``git <args>`` inside *cwd*, returning CompletedProcess (unchecked)."""
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def test_read_at_ref_returns_content_at_refs(tmp_path: Path) -> None:
    """Two commits → read_at_ref(HEAD) = second content, read_at_ref(HEAD~1) = first."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    f = tmp_path / "file.txt"
    f.write_text("A")
    commit_paths(tmp_path, [f], "first commit")

    f.write_text("B")
    commit_paths(tmp_path, [f], "second commit")

    # Both commits exist — verify via git log.
    assert _git("log", "--oneline", "HEAD~1", cwd=str(tmp_path)).returncode == 0

    assert read_at_ref(tmp_path, f, "HEAD") == "B"
    assert read_at_ref(tmp_path, f, "HEAD~1") == "A"


def test_read_at_ref_unknown_ref_raises(tmp_path: Path) -> None:
    """Bogus ref → CalledProcessError."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    f = tmp_path / "x.txt"
    f.write_text("data")
    commit_paths(tmp_path, [f], "add")

    with pytest.raises(subprocess.CalledProcessError):
        read_at_ref(tmp_path, f, "does-not-exist-ref")


def test_read_at_ref_unknown_path_raises(tmp_path: Path) -> None:
    """Existing ref but non-existent path → CalledProcessError."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    f = tmp_path / "x.txt"
    f.write_text("data")
    commit_paths(tmp_path, [f], "add")

    phantom = tmp_path / "nope.txt"
    with pytest.raises(subprocess.CalledProcessError):
        read_at_ref(tmp_path, phantom, "HEAD")
