from pathlib import Path

from fastmcp import Client

from micro_entity.markdown_store import MarkdownStore
from servers.adr import build_server


def _client(tmp_path: Path) -> Client:
    return Client(build_server(MarkdownStore(tmp_path)))
