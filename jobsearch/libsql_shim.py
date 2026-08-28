"""A sqlite3.Connection-shaped adapter over libsql_client, for a remote Turso DB.

The rest of the codebase talks to `db.connect()`'s return value using a small,
fixed slice of the sqlite3 API: `.execute()`, `.executescript()`, `.commit()`,
`.close()`, `.row_factory`, and on the object `.execute()` returns:
iteration, `["column"]` / `.keys()` on each row, and `.rowcount` / `.lastrowid`
on the cursor itself. This module implements exactly that slice on top of
libsql_client's ClientSync (HTTP transport -- no native/Rust build required),
so db.py can hand back one of these in place of a real sqlite3.Connection
without every caller needing to change.

Not a general sqlite3 shim: no cursor(), no explicit transactions.
`executemany()` exists specifically for the hot loops (score every sourced
posting, then skip most of them) that used to run one HTTP round-trip per
row -- thousands of them, sequentially, over a real network. That was not
just slow: read-your-writes got unreliable at that volume (a `SELECT ...
GROUP BY status` right after a few thousand individual UPDATEs would
disagree with itself between successive calls). Batching the same writes
into ~200-row HTTP requests via libsql_client's batch() made both problems
go away in testing. Every statement still runs and commits on its own
(server-side, per statement) -- nothing in this app relies on multi-
statement atomicity within one call.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Iterable, Iterator, TypeVar

try:
    import libsql_client
except ImportError:  # pragma: no cover - exercised only when the extra isn't installed
    libsql_client = None  # type: ignore[assignment]

T = TypeVar("T")

# Chunk size for executemany(). Turso's HTTP API has its own cap on request/
# response size; this is comfortably under it while still cutting a
# thousand-row loop down to single-digit round-trips.
_BATCH_CHUNK = 200

# A sourcing run does one HTTP round-trip per row -- thousands of them, over a
# real network, with nothing else retrying in between. A single DNS hiccup or
# dropped connection would otherwise abort the whole run partway through, with
# whatever was already committed staying committed and everything after it
# lost. Retried errors are ones a network blip plausibly causes; a real query
# error (bad SQL, a constraint violation) isn't in this list and still raises
# immediately, on the first try, same as before this existed.
_RETRIABLE = (OSError, TimeoutError)
_MAX_ATTEMPTS = 4
_BACKOFF_SECONDS = (0.5, 1.5, 3.0)


def _with_retry(call: Callable[[], T]) -> T:
    for attempt in range(_MAX_ATTEMPTS):
        try:
            return call()
        except _RETRIABLE:
            if attempt == _MAX_ATTEMPTS - 1:
                raise
            time.sleep(_BACKOFF_SECONDS[attempt])
        except Exception as exc:  # libsql_client wraps transport errors, incl. DNS
            # ClientConnectorDNSError, ServerDisconnectedError, etc. all subclass
            # OSError *except* when aiohttp re-wraps them -- checking the message
            # is unfortunately the reliable signal across aiohttp versions.
            transient = ("getaddrinfo", "Connection", "Timeout", "disconnected", "reset")
            if attempt == _MAX_ATTEMPTS - 1 or not any(t in str(exc) for t in transient):
                raise
            time.sleep(_BACKOFF_SECONDS[attempt])
    raise AssertionError("unreachable")  # loop always returns or raises above


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
        return LibsqlCursor(_with_retry(lambda: self._client.execute(sql, args)))

    def executemany(self, sql: str, seq_of_params: Iterable[Any]) -> None:
        """Same SQL, many param sets, batched into chunked HTTP requests.

        sqlite3.Connection.executemany() takes the same shape (one sql, an
        iterable of positional sequences or dicts), so callers that already
        build a list of updates can switch to this without restructuring.
        """
        statements = []
        for params in seq_of_params:
            args = params if isinstance(params, dict) else tuple(params)
            statements.append((sql, args))
        for i in range(0, len(statements), _BATCH_CHUNK):
            chunk = statements[i : i + _BATCH_CHUNK]
            _with_retry(lambda chunk=chunk: self._client.batch(chunk))

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
            _with_retry(lambda: self._client.batch(statements))

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
