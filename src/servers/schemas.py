from typing import TypedDict

"""MCP tool return envelope TypedDicts."""


class ItemResult(TypedDict):
    item: dict | None


class ItemCommitResult(TypedDict):
    item: dict
    commit: str | None


class ListResult(TypedDict):
    items: list[dict]
    errors: list[dict]


class ItemsResult(TypedDict):
    items: list[dict]


class OkIdCommitResult(TypedDict):
    ok: bool
    id: str
    commit: str | None


class CompleteResult(TypedDict):
    complete: bool


class CommitResult(TypedDict):
    ok: bool
    commit: str | None
    ids: list[str]


class SupersedeResult(TypedDict):
    superseded: dict
    superseding: dict
    commit: str | None


class DiffResult(TypedDict):
    diff: str


class CommitsResult(TypedDict):
    commits: list[dict]


class HealthResult(TypedDict):
    status: str
    status_values: list[str]
    base: str
    segment: str | None
    dir: str | None
