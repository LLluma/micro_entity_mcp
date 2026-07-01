"""ADR (Architecture Decision Record) server — exposes ADR management via FastMCP."""

import os
from datetime import UTC, datetime
from datetime import date as date_cls
from pathlib import Path
from typing import cast

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError

from micro_entity.codec import CommentedMap, entity_from_parts, parse_document, serialize_document
from micro_entity.entity import Entity
from micro_entity.markdown_store import UNSET, MarkdownStore, UnsetType
from micro_entity.query import query as query_entities
from micro_entity.store import LoadError, NotFoundError
from micro_entity.validation import FormError, validate_against_set, validate_attribute_value

# ---------------------------------------------------------------------------
# Module constants
# ---------------------------------------------------------------------------

STATUS_VALUES: set[str] = {"Proposed", "Accepted", "Superseded"}
STATUS_KEY: str = "status"
SUPERSEDES_KEY: str = "supersedes"
SUPERSEDED_BY_KEY: str = "superseded_by"
DEFAULT_STATUS: str = "Proposed"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_frontmatter(fm: dict) -> dict:
    """Derive created/updated timestamps from a legacy ``date`` field.

    If ``created`` and ``updated`` already exist, return *fm* unchanged.
    Otherwise derive a midnight-UTC datetime from ``date`` (the structurally
    parsed YAML value — may be ``datetime``, ``date``, or ``str``).
    Mutates *fm* in place and returns it.
    """
    got_created: bool = "created" in fm
    got_updated: bool = "updated" in fm

    if got_created and got_updated:
        return fm

    raw_date = fm.get("date")
    if raw_date is None:
        return fm

    # datetime is subclass of date — merged isinstance catches both
    if isinstance(raw_date, (datetime, date_cls)):
        ts = datetime(raw_date.year, raw_date.month, raw_date.day, tzinfo=UTC)
    elif isinstance(raw_date, str):
        parsed = date_cls.fromisoformat(raw_date[:10])
        ts = datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC)
    else:
        return fm

    if not got_created:
        fm["created"] = ts
    if not got_updated:
        fm["updated"] = ts

    return fm


def _get_migrated(store: MarkdownStore, id: str) -> Entity:
    """Read one record, migrating legacy timestamps, and return the Entity.

    Raises ``NotFoundError`` if the file does not exist.
    """
    path = store._path_for(id)
    if not path.is_file():
        raise NotFoundError(f"decision not found: {id}")
    fm, body = parse_document(path.read_text(encoding="utf-8"))
    fm = _normalize_frontmatter(fm)

    # Drop the legacy ``date`` key so it doesn't pollute entity attributes
    fm.pop("date", None)

    return entity_from_parts(id, fm, body)


def _update_migrated(
    store: MarkdownStore,
    id: str,
    *,
    attributes: dict | None = None,
    body: str | None | UnsetType = UNSET,
) -> Entity:
    # Deliberate copy of store.update flow; ADR profile injects legacy timestamp migration here.
    path = store._path_for(id)
    if not path.is_file():
        raise NotFoundError(f"entity not found: {id}")

    text = path.read_text(encoding="utf-8")
    fm, existing_body = parse_document(text)
    fm = _normalize_frontmatter(fm)
    fm.pop("date", None)

    if attributes is not None:
        for val in attributes.values():
            validate_attribute_value(val)
        for k, v in attributes.items():
            fm[k] = v

    fm["updated"] = store._clock().isoformat()

    new_body: str | None
    if body is UNSET:
        new_body = existing_body
    else:
        assert isinstance(body, (str, type(None)))
        new_body = body

    document = serialize_document(cast(CommentedMap, fm), new_body)
    store._atomic_write(path, document)
    return entity_from_parts(id, fm, new_body)


def _entity_to_dict(entity: Entity) -> dict:
    """Convert an Entity to a JSON-safe dict (timestamps as ISO strings)."""
    return entity.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------


def _load_all_migrated(
    store: MarkdownStore,
) -> tuple[list[Entity], list[LoadError]]:
    """Load every record in the partition, migrating legacy timestamps.

    Each ``.md`` file that parses/validates (after migration) becomes an Entity;
    each that fails becomes a ``LoadError(id=<stem>, reason=<message>)``.
    Entities are returned sorted by id. Never raises on a single bad record.
    Returns ``([], [])`` when the directory is absent.
    """
    if not store._directory.is_dir():
        return ([], [])

    entities: list[Entity] = []
    errors: list[LoadError] = []

    for path in sorted(store._directory.glob("*.md")):
        stem = path.stem
        try:
            entity = _get_migrated(store, stem)
            entities.append(entity)
        except Exception as exc:
            errors.append(LoadError(id=stem, reason=str(exc)))

    entities.sort(key=lambda e: e.id)
    return (entities, errors)


def _entity_matches_text(entity: Entity, needle: str) -> bool:
    """True if ``needle`` (case-insensitive) is a substring of the body or any
    attribute value (stringified)."""
    low = needle.lower()
    # body
    if entity.body is not None and low in entity.body.lower():
        return True
    # attributes
    for value in entity.attributes.values():
        if isinstance(value, list):
            for v in value:
                if low in str(v).lower():
                    return True
        else:
            if low in str(value).lower():
                return True
    return False


# ---------------------------------------------------------------------------
# Factory — the testability seam
# ---------------------------------------------------------------------------


def build_server(store: MarkdownStore) -> FastMCP:
    """Build the FastMCP server for the ADR profile.

    All tools are registered inside this function so tests can inject a
    mock / temporary store.
    """
    mcp = FastMCP("adr")

    @mcp.tool
    def health() -> dict:
        return {"status": "ok", "status_values": sorted(STATUS_VALUES)}

    @mcp.tool
    def add(
        id: str,
        title: str,
        body: str,
        attributes: dict | None = None,
    ) -> dict:
        attrs = dict(attributes) if attributes else {}
        attrs["title"] = title

        status = attrs.get(STATUS_KEY, DEFAULT_STATUS)
        try:
            validate_against_set(status, STATUS_VALUES)
        except FormError as e:
            raise ToolError(str(e)) from e
        attrs[STATUS_KEY] = status

        try:
            entity = store.create(id, attributes=attrs, body=body)
        except FileExistsError:
            raise ToolError(f"decision already exists: {id}") from None
        except FormError as e:
            raise ToolError(str(e)) from e

        return _entity_to_dict(entity)

    @mcp.tool
    def get(id: str) -> dict:
        try:
            entity = _get_migrated(store, id)
        except NotFoundError as e:
            raise ToolError(str(e)) from None
        except FormError as e:
            raise ToolError(str(e)) from e

        return _entity_to_dict(entity)

    @mcp.tool(name="list")
    def list_decisions() -> dict:
        entities, errors = _load_all_migrated(store)
        return {
            "items": [_entity_to_dict(e) for e in entities],
            "errors": [{"id": err.id, "reason": err.reason} for err in errors],
        }

    @mcp.tool
    def update(
        id: str,
        status: str | None = None,
        body: str | None = None,
        attributes: dict | None = None,
    ) -> dict:
        patch: dict = dict(attributes) if attributes else {}
        if status is not None:
            try:
                validate_against_set(status, STATUS_VALUES)
            except FormError as e:
                raise ToolError(str(e)) from e
            patch[STATUS_KEY] = status

        body_arg = body if body is not None else UNSET

        try:
            updated = _update_migrated(store, id, attributes=(patch or None), body=body_arg)
        except NotFoundError as e:
            raise ToolError(str(e)) from e
        except FormError as e:
            raise ToolError(str(e)) from e

        return _entity_to_dict(updated)

    @mcp.tool
    def supersede(old_id: str, new_id: str) -> dict:
        for ident in (old_id, new_id):
            try:
                path = store._path_for(ident)
            except FormError as e:
                raise ToolError(str(e)) from None
            if not path.is_file():
                raise ToolError(f"decision not found: {ident}")

        old = _update_migrated(
            store,
            old_id,
            attributes={STATUS_KEY: "Superseded", SUPERSEDED_BY_KEY: new_id},
        )
        new = _update_migrated(
            store,
            new_id,
            attributes={SUPERSEDES_KEY: old_id},
        )

        return {"superseded": _entity_to_dict(old), "superseding": _entity_to_dict(new)}

    @mcp.tool
    def query(criteria: dict[str, list] | None = None) -> dict:
        entities, _ = _load_all_migrated(store)
        matched = query_entities(entities, criteria or {})
        return {"items": [_entity_to_dict(e) for e in matched]}

    @mcp.tool
    def search(text: str) -> dict:
        entities, _ = _load_all_migrated(store)
        matched = [e for e in entities if _entity_matches_text(e, text)]
        return {"items": [_entity_to_dict(e) for e in matched]}

    return mcp


# ---------------------------------------------------------------------------
# Stdio entrypoint
# ---------------------------------------------------------------------------

ADR_DIR = os.environ.get("ADR_DIR", str(Path.home() / ".micro_entity_adr"))
mcp = build_server(MarkdownStore(Path(ADR_DIR)))

if __name__ == "__main__":
    mcp.run()
