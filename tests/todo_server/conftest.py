import subprocess
from pathlib import Path

from fastmcp import Client

from micro_entity.partition import StoreProvider
from servers.todo import build_server


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


def _client(tmp_path: Path) -> Client:
    _init_repo(tmp_path)
    return Client(build_server(StoreProvider(tmp_path, "test")))
