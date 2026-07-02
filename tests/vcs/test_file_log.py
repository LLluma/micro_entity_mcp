"""Tests for file_log."""

import subprocess
from datetime import datetime
from pathlib import Path

from micro_entity.vcs import commit_paths, file_log


def _build_history(
    root: Path, file: Path, messages: list[str]
) -> None:
    """Write *file* (or append) and commit with each *message*."""
    for i, msg in enumerate(messages):
        if i == 0:
            file.parent.mkdir(parents=True, exist_ok=True)
            file.write_text(f"content v{i}")
        else:
            file.write_text(f"content v{i} – {msg}")
        commit_paths(root, [file], msg)


# --- Tests ----------------------------------------------------------------


def test_file_log_returns_n_records(tmp_path: Path) -> None:
    """After N commits touching the file, file_log returns N records,
    newest-first, with correct sha/date/message."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    f = tmp_path / "changes.txt"
    messages = ["alpha", "bravo", "charlie", "delta"]
    _build_history(tmp_path, f, messages)

    result = file_log(tmp_path, f, limit=4)

    assert len(result) == 4

    # Newest-first: first record = last commit message
    assert result[0]["message"] == messages[-1]
    assert result[1]["message"] == messages[-2]
    assert result[2]["message"] == messages[-3]
    assert result[3]["message"] == messages[0]

    for rec in result:
        sha = rec["sha"]
        assert isinstance(sha, str)
        assert len(sha) == 40  # full hash

        dt = datetime.fromisoformat(rec["date"])
        assert dt is not None

        assert isinstance(rec["message"], str)
        assert len(rec["message"]) > 0


def test_file_log_limit_caps_count(tmp_path: Path) -> None:
    """With N commits, limit=1 returns exactly 1 record (the newest)."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    f = tmp_path / "limited.txt"
    messages = ["once", "twice", "thrice"]
    _build_history(tmp_path, f, messages)

    result = file_log(tmp_path, f, limit=1)

    assert len(result) == 1
    assert result[0]["message"] == messages[-1]


def test_file_log_single_commit(tmp_path: Path) -> None:
    """A file with exactly one commit returns exactly one record."""
    subprocess.run(["git", "init", str(tmp_path)], check=True, capture_output=True)

    f = tmp_path / "single.txt"
    f.write_text("only one")
    commit_paths(tmp_path, [f], "only commit")

    result = file_log(tmp_path, f, limit=10)

    assert len(result) == 1
    assert result[0]["message"] == "only commit"
    assert len(result[0]["sha"]) == 40
    datetime.fromisoformat(result[0]["date"])
