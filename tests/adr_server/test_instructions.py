"""Verify the server instructions constant is wired and contains key phrases."""

from pathlib import Path

from micro_entity.partition import StoreProvider
from servers.adr import build_server


def test_server_instructions_present(tmp_path: Path) -> None:
    """build_server should carry the module-level instructions."""
    server = build_server(StoreProvider(tmp_path, "test"))
    instructions: str | None = server.instructions
    assert instructions is not None, "server.instructions is None"

    text = instructions
    slices = [
        "not found: {id}",
        "storage is not under git",
        "ADR-NNNN",
        "Superseded",
        "supersede",
        '"item"',
        '"commit"',
        "project",
        "same parallel batch as a write may not observe",
    ]
    for slice in slices:
        assert slice in text, f"missing: {slice!r} in server.instructions"
