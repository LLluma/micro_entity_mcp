from pathlib import Path

import pytest

from micro_entity.partition import (
    StoreProvider,
    UnresolvedSegmentError,
    resolve_segment,
    sanitize_segment,
)

# --- UnresolvedSegmentError tests ---


def test_unresolved_segment_error_is_exception():
    """UnresolvedSegmentError is a real Exception subclass."""
    assert issubclass(UnresolvedSegmentError, Exception)


# --- StoreProvider tests ---


def test_provider_default_segment(tmp_path: Path) -> None:
    """Default segment resolves to base/default, identity cached."""
    provider = StoreProvider(tmp_path, "def")
    store = provider.get()
    assert store._directory == tmp_path / "def"
    assert provider.base == tmp_path
    assert provider.default_segment == "def"


def test_provider_default_identity_cached(tmp_path: Path) -> None:
    """Two .get() calls with same args return the SAME instance."""
    provider = StoreProvider(tmp_path, "def")
    a = provider.get()
    b = provider.get()
    assert a is b


def test_provider_different_segments_different_instances(tmp_path: Path) -> None:
    """Different project → different store instances."""
    provider = StoreProvider(tmp_path, "def")
    default_store = provider.get()
    other_store = provider.get("Other")
    assert default_store is not other_store
    assert default_store._directory == tmp_path / "def"
    assert other_store._directory == tmp_path / "other"


def test_provider_other_identity_cached(tmp_path: Path) -> None:
    """Two .get('Other') calls return the SAME instance."""
    provider = StoreProvider(tmp_path, "def")
    a = provider.get("Other")
    b = provider.get("Other")
    assert a is b


def test_provider_empty_explicit_fallback(tmp_path: Path) -> None:
    """.get("  ") slugifies to empty → falls back to default."""
    provider = StoreProvider(tmp_path, "fallback")
    store = provider.get("  ")
    assert store._directory == tmp_path / "fallback"


def test_unresolved_segment_error_message():
    """Exception carries a useful message."""
    try:
        raise UnresolvedSegmentError("no project segment could be resolved")
    except UnresolvedSegmentError as exc:
        assert "no project segment could be resolved" in str(exc)


def test_sanitize_segment_lowercases():
    assert sanitize_segment("MyProject") == "myproject"


def test_sanitize_segment_already_lower():
    assert sanitize_segment("micro_entity_mcp") == "micro_entity_mcp"


def test_sanitize_segment_path_traversal_chars():
    assert sanitize_segment("a/b\\c") == "a-b-c"


def test_sanitize_segment_whitespace():
    assert sanitize_segment("a   b") == "a-b"


def test_sanitize_segment_parent_dir():
    result = sanitize_segment("../etc")
    assert result not in (".", "..")
    assert ".." not in result


def test_sanitize_segment_double_dot_only():
    assert sanitize_segment("..") == ""


def test_sanitize_segment_single_dot():
    assert sanitize_segment(".") == ""


def test_sanitize_segment_underscores_stripped():
    assert sanitize_segment("__x__") == "x"


def test_sanitize_segment_empty():
    assert sanitize_segment("") == ""


def test_sanitize_segment_separators_only():
    assert sanitize_segment("/// ---") == ""


def test_sanitize_segment_hash_bang():
    assert sanitize_segment("Feature #1!") == "feature-1"


# --- resolve_segment tests ---


def test_resolve_segment_explicit_wins():
    """explicit slugifies and is returned, workspace ignored."""
    assert resolve_segment(explicit="Shared", workspace="/home/u/proj") == "shared"


def test_resolve_segment_workspace_basename():
    """No explicit — workspace last component basename is slugified."""
    assert (
        resolve_segment(explicit=None, workspace="/home/u/Micro_Entity_MCP") == "micro_entity_mcp"
    )


def test_resolve_segment_trailing_slash():
    """Trailing slash must be stripped before taking basename."""
    assert resolve_segment(explicit=None, workspace="/home/u/proj/") == "proj"


def test_resolve_segment_empty_explicit_falls_through():
    """explicit that slugifies to empty falls through to workspace."""
    assert resolve_segment(explicit="  ", workspace="/x/proj") == "proj"


def test_resolve_segment_both_none_returns_none():
    """Both None → None."""
    assert resolve_segment(explicit=None, workspace=None) is None


def test_resolve_segment_root_workspace_returns_none():
    """Workspace of '/' → basename empty → sanitize returns '' → None."""
    assert resolve_segment(explicit=None, workspace="/") is None


def test_provider_no_default_no_override_raises(tmp_path: Path) -> None:
    """No default, no project → UnresolvedSegmentError."""
    provider = StoreProvider(tmp_path, None)
    provider = StoreProvider(tmp_path, None)
    with pytest.raises(UnresolvedSegmentError) as exc_info:
        provider.get()
    assert "no project segment could be resolved" in str(exc_info.value)


def test_provider_explicit_project_would_work(tmp_path: Path) -> None:
    """No default but explicit project → store bound to project."""
    provider = StoreProvider(tmp_path, None)
    store = provider.get("proj")
    assert store._directory == tmp_path / "proj"


def test_provider_no_default_is_none(tmp_path: Path) -> None:
    """default_segment=None stays None."""
    provider = StoreProvider(tmp_path, None)
    assert provider.default_segment is None


def test_provider_base_resolves(tmp_path: Path) -> None:
    """base returns the resolved Path."""
    provider = StoreProvider(tmp_path, "seg")
    assert provider.base == tmp_path
