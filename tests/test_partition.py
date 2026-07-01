from micro_entity.partition import sanitize_segment


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
