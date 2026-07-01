from datetime import UTC, datetime
from datetime import date as date_cls

from servers.adr import _normalize_frontmatter


def test_normalize_date_as_datetime_date() -> None:
    fm: dict = {"date": date_cls(2026, 6, 29)}
    result = _normalize_frontmatter(fm)
    expected = datetime(2026, 6, 29, tzinfo=UTC)
    assert result is fm
    assert fm["created"] == expected
    assert fm["updated"] == expected


def test_normalize_date_as_string() -> None:
    fm: dict = {"date": "2026-06-29"}
    result = _normalize_frontmatter(fm)
    expected = datetime(2026, 6, 29, tzinfo=UTC)
    assert result is fm
    assert fm["created"] == expected
    assert fm["updated"] == expected


def test_normalize_skip_existing_timestamps() -> None:
    existing_created = datetime(2025, 1, 1, tzinfo=UTC)
    existing_updated = datetime(2025, 6, 15, tzinfo=UTC)
    fm: dict = {
        "created": existing_created,
        "updated": existing_updated,
        "date": datetime(2026, 6, 29, tzinfo=UTC),
    }
    result = _normalize_frontmatter(fm)
    assert result is fm
    assert fm["created"] is existing_created
    assert fm["updated"] is existing_updated


def test_normalize_no_date_no_timestamps() -> None:
    fm: dict = {"title": "no date here"}
    result = _normalize_frontmatter(fm)
    assert result is fm
    assert "created" not in fm
    assert "updated" not in fm


def test_normalize_datetime_datetime_drops_time() -> None:
    fm: dict = {"date": datetime(2026, 6, 29, 13, 30, tzinfo=UTC)}
    result = _normalize_frontmatter(fm)
    expected = datetime(2026, 6, 29, tzinfo=UTC)
    assert result is fm
    assert fm["created"] == expected
    assert fm["updated"] == expected
