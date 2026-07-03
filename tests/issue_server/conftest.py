import subprocess
from pathlib import Path

import pytest
from fastmcp import Client

from micro_entity.partition import StoreProvider
from servers.issue import _normalize_issue_id, build_server


def _init_repo(p: Path) -> None:
    subprocess.run(["git", "init", str(p)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(p), "config", "user.email", "test@localhost"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(p), "config", "user.name", "test"], check=True, capture_output=True
    )


@pytest.fixture(autouse=True)
def _ensure_repo(tmp_path: Path) -> None:
    """Auto-git-init any tmp_path that isn't already inside a repo."""
    try:
        subprocess.run(
            ["git", "-C", str(tmp_path), "rev-parse", "--show-toplevel"],
            capture_output=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        _init_repo(tmp_path)


def _client(tmp_path: Path) -> Client:
    _init_repo(tmp_path)
    return Client(build_server(StoreProvider(tmp_path, "seg", normalize_id=_normalize_issue_id)))
