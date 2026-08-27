"""A sqlite3.Connection-shaped adapter over libsql_client, for a remote Turso DB.

The rest of the codebase talks to `db.connect()`'s return value using a small,
fixed slice of the sqlite3 API: `.execute()`, `.executescript()`, `.commit()`,
`.close()`, `.row_factory`, and on the object `.execute()` returns:
iteration, `["column"]` / `.keys()` on each row, and `.rowcount` / `.lastrowid`
on the cursor itself. This module implements exactly that slice on top of
libsql_client's ClientSync (HTTP transport -- no native/Rust build required),
so db.py can hand back one of these in place of a real sqlite3.Connection
without every caller needing to change.

Not a general sqlite3 shim: no executemany, no cursor(), no explicit
transactions. Every statement here runs and commits on its own, which is
fine for this app -- nothing in it relies on multi-statement atomicity.
"""

from __future__ import annotations

from typing import Any, Iterable, Iterator

try:
    import libsql_client
except ImportError:  # pragma: no cover - exercised only when the extra isn't installed
    libsql_client = None  # type: ignore[assignment]


class LibsqlRow:
    """Wraps a libsql_client.Row so it behaves like a sqlite3.Row: index, key, .keys()."""

    __slots__ = ("_row",)

    def __init__(self, row: Any) -> None:
        self._row = row

    def __getitem__(self, key: Any) -> Any:
        return self._row[key]

    def keys(self) -> list[str]:
        return list(self._row._fields)

    def __iter__(self) -> Iterator[Any]:
        return iter(self._row.astuple())

    def __len__(self) -> int:
        return len(self._row)

    def __repr__(self) -> str:
        return f"LibsqlRow({self._row.asdict()!r})"


class LibsqlCursor:
    """The object conn.execute() returns: iterable rows, plus rowcount/lastrowid."""

    def __init__(self, result_set: Any) -> None:
        self._rows = [LibsqlRow(r) for r in result_set]
        self._pos = 0
        self.rowcount = result_set.rows_affected
        self.lastrowid = result_set.last_insert_rowid

    def fetchone(self) -> LibsqlRow | None:
        if self._pos >= len(self._rows):
            return None
        row = self._rows[self._pos]
        self._pos += 1
        return row

    def fetchall(self) -> list[LibsqlRow]:
        rows = self._rows[self._pos :]
        self._pos = len(self._rows)
        return rows

    def __iter__(self) -> Iterator[LibsqlRow]:
        return iter(self._rows)


class LibsqlConnection:
    """sqlite3.Connection-shaped wrapper around a libsql_client.ClientSync."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self.row_factory: Any = None  # accepted for API parity; rows are already dict-like

    def execute(self, sql: str, params: Any = None) -> LibsqlCursor:
        # sqlite3.execute() takes either a positional sequence (for "?" markers)
        # or a mapping (for ":name" markers) -- insert_row/update_row use the
        # latter. Pass a dict through as-is; only sequences get tupled.
        if params is None or isinstance(params, dict):
            args = params
        else:
            args = tuple(params)
        return LibsqlCursor(self._client.execute(sql, args))

    def executescript(self, script: str) -> None:
        # Strip '--' line comments first -- schema.DDL's comments contain semicolons
        # of their own ("...achievement; ..."), which a naive split would cut on.
        # DDL only, never user input, so this doesn't need to understand string
        # literals containing '--'.
        uncommented = "\n".join(
            line.split("--", 1)[0] if "--" in line else line
            for line in script.splitlines()
        )
        statements = [s.strip() for s in uncommented.split(";") if s.strip()]
        if statements:
            self._client.batch(statements)

    def commit(self) -> None:
        pass  # each statement above already committed server-side; no open transaction here

    def close(self) -> None:
        self._client.close()


def connect(url: str, auth_token: str) -> LibsqlConnection:
    if libsql_client is None:
        raise RuntimeError(
            "TURSO_DATABASE_URL is set but the 'libsql-client' package is not "
            "installed. Add it to requirements.txt / `pip install libsql-client`."
        )
    client = libsql_client.create_client_sync(url, auth_token=auth_token or None)
    return LibsqlConnection(client)
