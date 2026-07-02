from src.servers.schemas import (
    CommitResult,
    CommitsResult,
    CompleteResult,
    DiffResult,
    HealthResult,
    ItemCommitResult,
    ItemResult,
    ItemsResult,
    ListResult,
    OkIdCommitResult,
    SupersedeResult,
)


def test_item_result_annotations():
    assert set(ItemResult.__annotations__) == {"item"}


def test_item_commit_result_annotations():
    assert set(ItemCommitResult.__annotations__) == {"item", "commit"}


def test_list_result_annotations():
    assert set(ListResult.__annotations__) == {"items", "errors"}


def test_items_result_annotations():
    assert set(ItemsResult.__annotations__) == {"items"}


def test_ok_id_commit_result_annotations():
    assert set(OkIdCommitResult.__annotations__) == {"ok", "id", "commit"}


def test_complete_result_annotations():
    assert set(CompleteResult.__annotations__) == {"complete"}


def test_commit_result_annotations():
    assert set(CommitResult.__annotations__) == {"ok", "commit", "ids"}


def test_supersede_result_annotations():
    assert set(SupersedeResult.__annotations__) == {"superseded", "superseding", "commit"}


def test_diff_result_annotations():
    assert set(DiffResult.__annotations__) == {"diff"}


def test_commits_result_annotations():
    assert set(CommitsResult.__annotations__) == {"commits"}


def test_health_result_annotations():
    assert set(HealthResult.__annotations__) == {
        "status",
        "status_values",
        "base",
        "segment",
        "dir",
    }
