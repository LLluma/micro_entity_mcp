"""Smoke tests for issue server entrypoint wiring."""

import subprocess
from pathlib import Path

from micro_entity.partition import StoreProvider


def _init_repo(p: Path) -> None:
    subprocess.run(["git", "init", str(p)], check=True, capture_output=True)
    subprocess.run(
        ["git", "-C", str(p), "config", "user.email", "test@localhost"],
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "-C", str(p), "config", "user.name", "test"],
        check=True,
        capture_output=True,
    )


def test_mcp_module_attributes():
    """Verify the module exposes expected names at import."""
    import servers.issue as m

    assert m.mcp is not None
    assert isinstance(m.ISSUE_DIR, str)
    assert len(m.ISSUE_DIR) > 0


def test_build_server_callable():
    """Calling build_server with a viable provider returns a FastMCP instance."""
    import servers.issue as m

    tmp_path = Path(__file__).parent / "_tmp_build"
    try:
        _init_repo(tmp_path)
        provider = StoreProvider(
            tmp_path,
            "seg",
            normalize_id=m._normalize_issue_id,
        )
        server = m.build_server(provider)
    finally:
        import shutil

        shutil.rmtree(tmp_path, ignore_errors=True)

    assert server is not None


def test_build_server_no_raise_on_valid_provider():
    """build_server should not raise given a git-initialized tmp_path provider."""
    import servers.issue as m

    tmp_path = Path(__file__).parent / "_tmp_build2"
    try:
        _init_repo(tmp_path)
        provider = StoreProvider(
            tmp_path,
            "seg",
            normalize_id=m._normalize_issue_id,
        )
        m.build_server(provider)  # should not raise
    finally:
        import shutil

        shutil.rmtree(tmp_path, ignore_errors=True)
