"""Smoke tests for server entrypoint wiring — default segment from cwd."""

import os

from micro_entity.partition import StoreProvider, resolve_segment


def test_provider_default_segment_from_cwd(tmp_path, monkeypatch):
    """Verify that a provider built with resolve_segment(cwd) resolves its
    store directory to <base>/<slugified_cwd_basename>.
    """
    workspace = tmp_path / "MyWorkspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    base = tmp_path / "store"
    provider = StoreProvider(base, resolve_segment(explicit=None, workspace=os.getcwd()))
    store = provider.get()  # no explicit project -> default segment
    expected = (base / "myworkspace").resolve()
    assert store._directory == expected


def test_resolve_segment_uses_cwd_basename():
    """resolve_segment(explicit=None, workspace=/foo/MyProj) -> 'myproj'."""
    result = resolve_segment(explicit=None, workspace="/foo/MyProj")
    assert result == "myproj"


def test_resolve_segment_explicit_overrides_workspace():
    """explicit segment takes priority over workspace."""
    result = resolve_segment(explicit="myproject", workspace="/foo/SomeDir")
    assert result == "myproject"


def test_both_server_modules_import_and_build(monkeypatch, tmp_path):
    """Importing each server module builds a provider + FastMCP without error."""
    monkeypatch.setenv("TODO_DIR", str(tmp_path / "t"))
    monkeypatch.setenv("ADR_DIR", str(tmp_path / "a"))
    monkeypatch.chdir(tmp_path)
    import importlib

    import servers.adr as adr_mod
    import servers.todo as todo_mod

    importlib.reload(todo_mod)
    importlib.reload(adr_mod)
    assert todo_mod.mcp is not None
    assert adr_mod.mcp is not None


def test_todo_provider_resolves_store_from_cwd(monkeypatch, tmp_path):
    """The todo server's provider.get() resolves the store into <TODO_DIR>/<cwd_slug>."""
    workspace = tmp_path / "MyWorkspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.setenv("TODO_DIR", str(tmp_path / "todos"))
    import importlib

    import servers.todo

    importlib.reload(servers.todo)
    store = servers.todo._provider.get()
    assert store._directory == (tmp_path / "todos" / "myworkspace").resolve()


def test_adr_provider_resolves_store_from_cwd(monkeypatch, tmp_path):
    """The adr server's provider.get() resolves the store into <ADR_DIR>/<cwd_slug>."""
    workspace = tmp_path / "MyWorkspace"
    workspace.mkdir()
    monkeypatch.chdir(workspace)
    monkeypatch.setenv("ADR_DIR", str(tmp_path / "adrs"))
    import importlib

    import servers.adr

    importlib.reload(servers.adr)
    store = servers.adr._provider.get()
    assert store._directory == (tmp_path / "adrs" / "myworkspace").resolve()
