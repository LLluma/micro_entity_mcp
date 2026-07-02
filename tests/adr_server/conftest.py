import subprocess
from pathlib import Path

import pytest
from fastmcp import Client

from micro_entity.partition import StoreProvider
from servers.adr import _normalize_adr_id, build_server


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
    return Client(build_server(StoreProvider(tmp_path, "seg", normalize_id=_normalize_adr_id)))


# Synthetic legacy ADR records (carry `date:` but no created/updated, rich frontmatter)
# used by tests that previously copied the repo's docs/adr directory.
_legacy_adrs: dict = {
    "ADR-0001": {"title": "First decision", "date": "2026-06-29", "tags": ["alpha", "beta"]},
    "ADR-0002": {"title": "Second decision", "date": "2026-06-29", "tags": ["gamma"]},
    "ADR-0003": {"title": "Third decision", "date": "2026-06-30", "tags": ["alpha"]},
    "ADR-0004": {"title": "Fourth decision", "date": "2026-06-30", "tags": ["delta"]},
    "ADR-0005": {"title": "Fifth decision", "date": "2026-06-30", "tags": ["omega"]},
}


def _legacy_adr_text(adr_id: str, title: str, date: str, tags: list[str]) -> str:
    tagline = "[" + ", ".join(tags) + "]"
    return (
        f"---\nid: {adr_id}\ntitle: {title}\nstatus: Accepted\ndate: {date}\n"
        f'tags: {tagline}\nsupersedes: ""\nsuperseded_by: ""\nrelates_to: []\n---\n\n'
        f"# {adr_id}: {title}\n\n## Context\nSynthetic fixture body for {adr_id}.\n"
    )


def write_legacy_adrs(seg_dir, ids=None):
    """Write synthetic legacy ADR .md files into seg_dir. Returns the ids written."""
    seg_dir = Path(seg_dir)
    seg_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for adr_id, meta in _legacy_adrs.items():
        if ids is None or adr_id in ids:
            (seg_dir / f"{adr_id}.md").write_text(
                _legacy_adr_text(adr_id, **meta), encoding="utf-8"
            )
            written.append(adr_id)
    return written
