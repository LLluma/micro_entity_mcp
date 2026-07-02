import os
import re
from pathlib import Path

from micro_entity.markdown_store import MarkdownStore


class UnresolvedSegmentError(Exception):
    """Raised when no segment can be resolved for an operation."""


def sanitize_segment(name: str) -> str:
    text = name.lower()
    text = re.sub(r"[^a-z0-9._-]+", "-", text)
    text = text.strip("-._")
    text = text.replace("..", "-")
    if text in (".", "..") or text == "":
        return ""
    return text


def resolve_segment(*, explicit: str | None, workspace: str | None) -> str | None:
    if explicit is not None:
        slug = sanitize_segment(explicit)
        if slug:
            return slug
    if workspace is not None:
        slug = sanitize_segment(os.path.basename(workspace.rstrip("/")))
        if slug:
            return slug
    return None


class StoreProvider:
    """Resolve project/workspace to a cached ``MarkdownStore`` per segment."""

    def __init__(self, base: Path, default_segment: str | None) -> None:
        self._base = Path(base).resolve()
        self._default_segment = default_segment
        self._stores: dict[str, MarkdownStore] = {}

    @property
    def base(self) -> Path:
        return self._base

    @property
    def default_segment(self) -> str | None:
        return self._default_segment

    def get(self, project: str | None = None) -> MarkdownStore:
        seg = resolve_segment(explicit=project, workspace=None)
        if not seg:
            seg = self._default_segment
        if not seg:
            raise UnresolvedSegmentError("no project segment could be resolved")
        if seg not in self._stores:
            self._stores[seg] = MarkdownStore(self._base, segment=seg)
        return self._stores[seg]
