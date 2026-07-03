from typing import NotRequired, TypedDict

"""MCP tool return envelope TypedDicts."""


class ItemResult(TypedDict):
    item: dict | None


class ItemCommitResult(TypedDict):
    item: dict
    commit: str | None
    progress: NotRequired[dict]


class ListResult(TypedDict):
    items: list[dict]
    errors: list[dict]


class ItemsResult(TypedDict):
    items: list[dict]


class OkIdCommitResult(TypedDict):
    ok: bool
    id: str
    commit: str | None
    progress: NotRequired[dict]


class CompleteResult(TypedDict):
    complete: bool


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
