import dataclasses
import subprocess
from pathlib import Path

import pytest
from fastmcp import Client

from micro_entity.partition import StoreProvider
from servers.adr import _normalize_adr_id
from servers.adr import build_server as build_adr
from servers.todo import _normalize_todo_id
from servers.todo import build_server as build_todo


def _init_repo(p: Path) -> None:
    subprocess.run(["git", "init", str(p)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(p), "config", "user.email", "test@localhost"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(p), "config", "user.name", "test"],
        check=True,
        capture_output=True,
    )


@dataclasses.dataclass
class ConformanceCase:
    """One profile server under test, plus the metadata a conformance test needs."""

    name: str
    client: Client
    status_values: list[str]
    create_payload: dict
    expected_id: str
    denormalized_id: str
    missing_id: str


@pytest.fixture(params=["todo", "adr"])
def conformance_case(request: pytest.FixtureRequest, tmp_path: Path) -> ConformanceCase:
    """Yield a built client + metadata for each profile server (todo, adr)."""
    _init_repo(tmp_path)
    if request.param == "todo":
        provider = StoreProvider(tmp_path, "seg", normalize_id=_normalize_todo_id)
        return ConformanceCase(
            name="todo",
            client=Client(build_todo(provider)),
            status_values=["blocked", "done", "in-progress", "todo"],
            create_payload={"body": "hello world"},
            expected_id="0001",
            denormalized_id="1",
            missing_id="9999",
        )
    provider = StoreProvider(tmp_path, "seg", normalize_id=_normalize_adr_id)
    return ConformanceCase(
        name="adr",
        client=Client(build_adr(provider)),
        status_values=["Accepted", "Proposed", "Superseded"],
        create_payload={"title": "T", "body": "hello world"},
        expected_id="ADR-0001",
        denormalized_id="adr-1",
        missing_id="ADR-9999",
    )
