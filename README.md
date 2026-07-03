# micro_entity_mcp

A neutral core `micro_entity` package plus thin [FastMCP](https://github.com/jlowin/fastmcp)
profile servers. Entities are stored as plain Markdown files with YAML
frontmatter, one file per entity, so the data stays human-readable and
git-friendly.

## Layout

```
src/
  micro_entity/     Neutral core: entity model, store, codec, query, validation
  servers/          Thin FastMCP profile servers (todo, adr, issue)
  servers/_common.py Shared tool scaffold (ProfileConfig + register_common_tools)
tests/
```

Entity data is not stored in the repo. Each server writes its Markdown files to an
external, git-backed directory chosen at runtime via `$TODO_DIR` / `$ADR_DIR` /
`$ISSUE_DIR` (defaults `~/.micro_entity_todo` / `~/.micro_entity_adr` /
`~/.micro_entity_issue`), partitioned per project into a workspace segment.

## Core (`micro_entity`)

- **`entity.py`** — `Entity`, a frozen Pydantic v2 model: `id`, timezone-aware
  `created`/`updated`, optional `body`, and `attributes` (scalars or flat lists
  of scalars).
- **`markdown_store.py`** — `MarkdownStore`, maps entity ids to `.md` files under
  a directory. Atomic writes (temp file + `os.replace`), id-traversal protection,
  and CRUD (`get`, `create`, `update`, `delete`, `load_all`, `clear`). Timestamps
  come from an injectable clock. Reads hit disk fresh (no cache). Optional
  `normalize` hook for per-profile frontmatter migration, plus an injectable
  `normalize_id` hook applied at the lookup boundary so id-taking calls can accept
  lenient ids (e.g. `17` → `0017`).
- **`partition.py`** — `StoreProvider`, resolves a project/workspace to a
  per-segment `MarkdownStore` (per-project partitioning) and threads the
  `normalize_id` hook through to it.
- **`vcs.py`** — git helpers (repo discovery, per-file commit/log/diff, read-at-ref)
  backing the servers' per-mutation auto-commit and history/diff/revert tools.
- **`codec.py`** — Markdown ⇄ frontmatter/body serialization (ruamel.yaml,
  comment/key-order preserving).
- **`query.py`** — `query()` matches entities against attribute criteria (logical
  AND across keys, OR across values, type-strict equality); `entity_matches_text()`
  does case-insensitive full-text matching over body + attribute values (shared by
  all profiles' `search`, provided via the common scaffold).
- **`validation.py`** — attribute-shape, id, and allowed-set validation
  (`FormError`).

## Profile servers

Each server is built by a `build_server(provider)` factory (the testability seam,
taking a `StoreProvider`) and exposes tools over FastMCP stdio. All three
profiles share one common tool surface via the `_common.py` scaffold
(`ProfileConfig` + `register_common_tools`), so the common tools behave
identically across profiles (guaranteed by a parametrized conformance suite), and
each server adds only its profile-specific tools. Cross-cutting behavior across
all profiles: every mutation auto-commits to git and returns its commit sha;
`list` and `search` omit entity bodies by default (`include_body=True` to include
them); id-taking tools accept lenient ids and report the canonical id on
`not found`; storage must live inside a git repository.

### todo (`src/servers/todo.py`)

Task management. Status values: `todo`, `in-progress`, `done`, `blocked`.

Tools: `health`, `create`, `get`, `list`, `query`, `search`, `update`, `delete`,
`next`, `is_complete`, `patch_body`, `history`, `diff`, `revert`. `create`
auto-assigns a sequential zero-padded id and an `order` attribute; `next` returns
the lowest-`order` actionable item; `is_complete` reports whether any item is
still open.

Storage dir: `$TODO_DIR` (default `~/.micro_entity_todo`).

### adr (`src/servers/adr.py`)

Architecture Decision Records. Status values: `Proposed`, `Accepted`,
`Superseded`. The log is append-only (no delete): a changed decision is a new
record plus a `Superseded` status on the old one.

Tools: `health`, `create`, `get`, `list`, `query`, `search`, `update`,
`supersede`, `patch_body`, `history`, `diff`, `revert`. `create` assigns the
sequential `ADR-NNNN` id (caller-supplied ids are rejected); `supersede` links
old/new decisions and rolls back on failure. Legacy `date` frontmatter is
normalized into `created`/`updated`.

Storage dir: `$ADR_DIR` (default `~/.micro_entity_adr`).

### issue (`src/servers/issue.py`)

Durable "what happened" records — observations and bugs that are mutable and
closeable but never deleted. Status values: `open` (default, only non-terminal),
`closed`, `wontfix` (a wrong/duplicate report; never deleted).

Tools: `health`, `create`, `get`, `list`, `query`, `search`, `update`,
`patch_body`, `history`, `diff`, `revert`. There is no `delete`, `next`,
`is_complete`, or `supersede` — closing is done via
`update(status="closed"|"wontfix")`. `create` auto-assigns `ISSUE-NNNN` ids
(caller-supplied ids rejected; it injects `title`).
Meaningful free-form attributes: `title`, `external_refs` (list of `"tracker#id"`
strings), `relates_to` (list of ADR ids), `resolved_by` (list of durable
artifacts: commit shas and/or ADR ids), `duplicate_of` (an issue id).

Storage dir: `$ISSUE_DIR` (default `~/.micro_entity_issue`).

## Running a server

```sh
uv run python -m servers.todo
uv run python -m servers.adr
uv run python -m servers.issue
```

## Installing into an MCP client

All three servers speak MCP over stdio, so any MCP-capable agent can launch them as a
local (stdio) server. The launch command is the same one shown above; point it at
this checkout with `uv run --directory` and pass the storage dir via the
`TODO_DIR` / `ADR_DIR` / `ISSUE_DIR` environment variables. Adjust the paths to your clone —
OpenCode can expand `{env:HOME}` (used below); Claude Code needs a literal path.

### OpenCode

Add the servers under the `mcp` key of your `opencode.json` (project-level
`./opencode.json` or global `~/.config/opencode/opencode.json`). OpenCode expands
`{env:VAR}` in config, so you can anchor paths to `{env:HOME}` instead of typing an
absolute path:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "todo": {
      "type": "local",
      "command": ["uv", "run", "--directory", "{env:HOME}/code/micro_entity_mcp", "python", "-m", "servers.todo"],
      "environment": { "TODO_DIR": "{env:HOME}/.micro_entity_todo" },
      "enabled": true
    },
    "adr": {
      "type": "local",
      "command": ["uv", "run", "--directory", "{env:HOME}/code/micro_entity_mcp", "python", "-m", "servers.adr"],
      "environment": { "ADR_DIR": "{env:HOME}/.micro_entity_adr" },
      "enabled": true
    },
    "issue": {
      "type": "local",
      "command": ["uv", "run", "--directory", "{env:HOME}/code/micro_entity_mcp", "python", "-m", "servers.issue"],
      "environment": { "ISSUE_DIR": "{env:HOME}/.micro_entity_issue" },
      "enabled": true
    }
  }
}
```

### Claude Code

Register each server with the CLI (the flags before `--` configure Claude Code;
everything after `--` is the launch command):

```sh
claude mcp add todo --env TODO_DIR=/abs/path/to/data/todo \
  -- uv run --directory /abs/path/to/micro_entity_mcp python -m servers.todo
claude mcp add adr --env ADR_DIR=/abs/path/to/data/adr \
  -- uv run --directory /abs/path/to/micro_entity_mcp python -m servers.adr
claude mcp add issue --env ISSUE_DIR=/abs/path/to/data/issue \
  -- uv run --directory /abs/path/to/micro_entity_mcp python -m servers.issue
```

Equivalently, add them by hand to a `.mcp.json` (project scope) or
`~/.claude.json` (user scope):

```json
{
  "mcpServers": {
    "todo": {
      "command": "uv",
      "args": ["run", "--directory", "/abs/path/to/micro_entity_mcp", "python", "-m", "servers.todo"],
      "env": { "TODO_DIR": "/abs/path/to/data/todo" }
    },
    "adr": {
      "command": "uv",
      "args": ["run", "--directory", "/abs/path/to/micro_entity_mcp", "python", "-m", "servers.adr"],
      "env": { "ADR_DIR": "/abs/path/to/data/adr" }
    },
    "issue": {
      "command": "uv",
      "args": ["run", "--directory", "/abs/path/to/micro_entity_mcp", "python", "-m", "servers.issue"],
      "env": { "ISSUE_DIR": "/abs/path/to/data/issue" }
    }
  }
}
```

The storage dir must live inside a git repository — the servers commit every
mutation — so point `TODO_DIR` / `ADR_DIR` / `ISSUE_DIR` at a path under a git
repo (or run `git init` in it once).

## Development

Requires Python >= 3.11. Uses `uv`.

```sh
make test    # uv run pytest
make lint    # ruff check + pyright
make fix     # ruff check --fix + ruff format
```
