from micro_entity.partition import resolve_segment, sanitize_segment


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
