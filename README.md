# micro_entity_mcp

A neutral core `micro_entity` package plus thin [FastMCP](https://github.com/jlowin/fastmcp)
profile servers. Entities are stored as plain Markdown files with YAML
frontmatter, one file per entity, so the data stays human-readable and
git-friendly.

## Layout

```
src/
  micro_entity/     Neutral core: entity model, store, codec, query, validation
  servers/          Thin FastMCP profile servers (todo, adr)
tests/
docs/
  adr/              Architecture decision records
  todo/             Todo entities
```

## Core (`micro_entity`)

- **`entity.py`** — `Entity`, a frozen Pydantic v2 model: `id`, timezone-aware
  `created`/`updated`, optional `body`, and `attributes` (scalars or flat lists
  of scalars).
- **`markdown_store.py`** — `MarkdownStore`, maps entity ids to `.md` files under
  a directory. Atomic writes (temp file + `os.replace`), id-traversal protection,
  and CRUD (`get`, `create`, `update`, `delete`, `load_all`, `clear`). Timestamps
  come from an injectable clock. Optional `normalize` hook for per-profile
  frontmatter migration.
- **`codec.py`** — Markdown ⇄ frontmatter/body serialization (ruamel.yaml,
  comment/key-order preserving).
- **`query.py`** — `query()` matches entities against criteria: logical AND across
  keys, OR across values, type-strict equality.
- **`validation.py`** — attribute-shape, id, and allowed-set validation
  (`FormError`).

## Profile servers

Each server is built by a `build_server(store)` factory (the testability seam)
and exposes tools over FastMCP stdio.

### todo (`src/servers/todo.py`)

Task management. Status values: `todo`, `in-progress`, `done`, `blocked`.

Tools: `health`, `create`, `get`, `list`, `query`, `update`, `delete`, `next`,
`clear`, `is_complete`. `create` auto-assigns a sequential zero-padded id and an
`order` attribute; `next` returns the lowest-`order` actionable item.

Storage dir: `$TODO_DIR` (default `~/.micro_entity_todo`).

### adr (`src/servers/adr.py`)

Architecture Decision Records. Status values: `Proposed`, `Accepted`,
`Superseded`.

Tools: `health`, `add`, `get`, `list`, `update`, `supersede`, `query`, `search`.
`supersede` links old/new decisions and rolls back on failure. Legacy `date`
frontmatter is normalized into `created`/`updated`.

Storage dir: `$ADR_DIR` (default `~/.micro_entity_adr`).

## Running a server

```sh
uv run python -m servers.todo
uv run python -m servers.adr
```

## Development

Requires Python >= 3.11. Uses `uv`.

```sh
make test    # uv run pytest
make lint    # ruff check + pyright
make fix     # ruff check --fix + ruff format
```
