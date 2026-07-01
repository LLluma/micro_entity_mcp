from pathlib import Path

from fastmcp import Client

from micro_entity.partition import StoreProvider
from servers.todo import build_server


def _client(tmp_path: Path) -> Client:
    return Client(build_server(StoreProvider(tmp_path, "test")))
