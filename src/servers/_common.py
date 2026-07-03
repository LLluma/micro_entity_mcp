from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from fastmcp.exceptions import ToolError

from micro_entity import vcs
from micro_entity.codec import CommentedMap
from micro_entity.entity import Entity
from micro_entity.markdown_store import MarkdownStore
from micro_entity.partition import StoreProvider, UnresolvedSegmentError


@dataclass(frozen=True)
class ProfileConfig:
    name: str
    instructions: str
    status_values: set[str]
    normalize: Callable[[CommentedMap], CommentedMap] | None = None
    normalize_id: Callable[[str], str] | None = None
    reserved_keys: frozenset[str] = field(default=frozenset({"created", "updated", "id"}))


def _entity_to_dict(entity: Entity) -> dict:
    """Convert an Entity to a JSON-safe dict (timestamps as ISO strings)."""
    return entity.model_dump(mode="json")


def _resolve_store(
    provider: StoreProvider,
    project: str | None,
) -> MarkdownStore:
    """Resolve the store for a tool call; raise ToolError on failure."""
    try:
        return provider.get(project)
    except UnresolvedSegmentError as e:
        raise ToolError(str(e)) from e


def _require_repo(store: MarkdownStore) -> Path:
    """Resolve the enclosing git repo root for the store's partition dir.

    Raise ``ToolError("storage is not under git")`` if the dir is not under a
    git repository.
    """
    try:
        return vcs.find_repo_root(store.directory)
    except vcs.NotAGitRepoError as e:
        raise ToolError("storage is not under git") from e
