"""A local review UI.

Deliberately small: `http.server` from the standard library, one thread per
request, bound to the loopback interface. This database holds your address,
phone number, employment history, and drafts addressed to real employers, so the
server is built to be reachable from this machine and nowhere else.

Three protections, none of them optional:

- **Loopback bind.** The listening socket is 127.0.0.1. Passing a public address
  is refused rather than warned about.
- **CSRF token.** Any page on the internet can make your browser POST to
  localhost. Every mutating request must carry a token minted at startup, and
  GET never changes state, so a prefetch cannot fire an action.
- **Host header check.** Blocks DNS rebinding, where a hostile domain re-resolves
  to 127.0.0.1 and reads these pages from a tab you left open.
"""

from __future__ import annotations

import os
import secrets
import sqlite3
import threading
import time
import urllib.parse
import webbrowser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from .. import answers, db, pipeline
from ..config import Config
from . import assets, evoque, evoque_pages, pages
from .html import esc, layout

ALLOWED_HOSTS_SUFFIX = ("localhost", "127.0.0.1", "[::1]")


class WebError(RuntimeError):
    pass


def _page(title: str, message: str, status: int = 400) -> tuple[int, str]:
    body = f"<h1>{esc(title)}</h1><p class='sub'>{esc(message)}</p><p><a href='/'>Back</a></p>"
    return status, layout(title, body)


SESSION_COOKIE = "jobsearch_session"
SESSION_TTL_SECONDS = 60 * 60 * 24 * 30  # 30 days


class App:
    """Routing and actions, kept apart from the HTTP plumbing so it can be tested."""

    def __init__(self, db_path: str | Path | None, config: Config, token: str) -> None:
        self.db_path = db_path
        self.config = config
        self.token = token
        self.password = ""
        self.public = False  # set by serve(); True adds Secure to the session cookie
        self._lock = threading.Lock()
        self._sessions: dict[str, float] = {}
        self._session_lock = threading.Lock()

    # ------------------------------------------------------------------ sessions

    def create_session(self) -> str:
        token = secrets.token_urlsafe(32)
        with self._session_lock:
            self._sessions[token] = time.time() + SESSION_TTL_SECONDS
        return token

    def session_valid(self, token: str) -> bool:
        if not token:
            return False
        with self._session_lock:
            expiry = self._sessions.get(token)
            if expiry is None:
                return False
            if expiry < time.time():
                del self._sessions[token]
                return False
            return True

    def destroy_session(self, token: str) -> None:
        with self._session_lock:
            self._sessions.pop(token, None)

    def try_login(self, fields: dict[str, str]) -> str | None:
        """Check a login form post. Returns a fresh session token on success."""
        supplied = fields.get("password") or ""
        if not self.password or not secrets.compare_digest(supplied, self.password):
            return None
        return self.create_session()

    def login_page(self, *, error: str = "") -> str:
        return evoque.login_document(error=error)

    # ------------------------------------------------------------------ helpers

    def _connect(self) -> sqlite3.Connection:
        return db.connect(self.db_path)

    def _fresh_config(self) -> Config:
        """Re-read config.toml per request so edits show up without a restart.

        Only ever re-reads the file this App was opened with. A config that came
        from somewhere other than a path is used as-is -- reloading it from the
        default location would quietly answer with a different config than the
        caller supplied.
        """
        if not self.config.path:
            return self.config
        try:
            return Config.load(self.config.path)
        except Exception:
            return self.config

    # ------------------------------------------------------------------ GET

    def get(self, path: str, query: dict[str, list[str]]) -> tuple[int, str]:
        parts = [p for p in path.strip("/").split("/") if p]
        conn = self._connect()
        try:
            # Every page is the Evoque shell (evoque_pages). The React
            # bundle's pages are gone from routing; `pages.py` is still the
            # single source of the aggregation queries both used.
            one = lambda k: (query.get(k) or [""])[0]  # noqa: E731
            if not parts:
                return 200, evoque_pages.dashboard(conn, self._fresh_config())
            if parts == ["jobs"]:
                return 200, evoque_pages.jobs(
                    conn,
                    q=one("q"),
                    where=one("where"),
                    status=(query.get("status") or [None])[0],
                    scope=one("scope") or "remote",
                )
            if len(parts) == 2 and parts[0] == "jobs" and parts[1].isdigit():
                html = evoque_pages.job_detail(
                    conn, int(parts[1]), self._fresh_config(), self.token
                )
                return (200, html) if html else _page(
                    "No such job", f"Job {parts[1]} is not in the database.", 404
                )
            if parts == ["competitions"]:
                return 200, evoque_pages.competitions(conn, q=one("q"))
            if parts == ["queue"]:
                return 200, evoque_pages.queue(conn)
            if parts == ["resume"]:
                return 200, evoque_pages.resume(conn)
            if len(parts) == 2 and parts[0] == "applications" and parts[1].isdigit():
                html = evoque_pages.application_detail(conn, int(parts[1]), self.token)
                return (200, html) if html else _page(
                    "No such application", f"Application {parts[1]} does not exist.", 404
                )
            if parts == ["profile"]:
                return 200, evoque_pages.profile(conn)
            if parts == ["profile", "edit"]:
                return 200, evoque_pages.profile_edit(conn, self.token)
            if parts == ["profile", "build"]:
                return 200, evoque_pages.profile_build(conn, self.token)
            if parts == ["analytics"]:
                return 200, evoque_pages.analytics(conn)
            if parts == ["runs"]:
                return 200, evoque_pages.runs(conn)
            if parts == ["answers"]:
                return 200, evoque_pages.answers(conn, self.token)
            if parts == ["review"]:
                return 200, evoque_pages.review(conn, self.token)
            # `/reach`, `/funnel` and `/terminal` were three views of the same
            # figures. They serve the one Analytics page now rather than
            # redirecting, so every URL that worked before still returns a page.
            if parts in (["reach"], ["funnel"], ["terminal"]):
                return 200, evoque_pages.analytics(conn)
            return _page("Not found", f"No page at {path}", 404)
        finally:
            conn.close()

    # ------------------------------------------------------------------ POST

    def post(self, path: str, fields: dict[str, str]) -> tuple[int, str]:
        if not secrets.compare_digest(fields.get("token", ""), self.token):
            return _page(
                "Rejected",
                "That form did not carry this session's token. Reload the page and try "
                "again. If you did not click anything, another site tried to act on your "
                "behalf and was stopped.",
                403,
            )
        parts = [p for p in path.strip("/").split("/") if p]
        conn = self._connect()
        try:
            if len(parts) == 3 and parts[0] == "jobs" and parts[1].isdigit() and parts[2] == "tailor":
                return self._tailor(conn, int(parts[1]))
            if len(parts) == 3 and parts[0] == "applications" and parts[1].isdigit():
                return self._decide(conn, int(parts[1]), parts[2])
            if len(parts) == 4 and parts[0] == "review" and parts[3] == "verify":
                return self._verify_row(conn, parts[1], parts[2])
            if parts == ["answers", "add"]:
                return self._add_answer(conn, fields)
            if len(parts) == 3 and parts[0] == "answers" and parts[1].isdigit() and parts[2] == "delete":
                answers.remove(conn, int(parts[1]))
                conn.commit()
                return 303, "/answers"
            if parts == ["competitions", "add"]:
                return self._add_competition(conn, fields)
            if len(parts) == 3 and parts[0] == "competitions" and parts[1].isdigit() and parts[2] == "delete":
                db.delete_row(conn, "competitions", int(parts[1]))
                conn.commit()
                return 303, "/competitions"
            if parts == ["profile", "save"]:
                return self._save_profile(conn, fields)
            if len(parts) == 3 and parts[0] == "profile" and parts[2] == "add":
                return self._add_entity(conn, parts[1], fields)
            if (
                len(parts) == 4
                and parts[0] == "profile"
                and parts[2].isdigit()
                and parts[3] == "delete"
            ):
                return self._delete_entity(conn, parts[1], int(parts[2]))
            if len(parts) == 4 and parts[0] == "profile" and parts[1] == "attr" and parts[3] == "delete":
                db.delete_profile_field(conn, parts[2])
                conn.commit()
                return 303, "/profile/edit"
            return _page("Not found", f"No action at {path}", 404)
        finally:
            conn.close()

    # ------------------------------------------------------------------ actions

    def _add_answer(self, conn: sqlite3.Connection, fields: dict[str, str]) -> tuple[int, str]:
        """Store one standing answer.

        A blank answer is a no-op rather than an error: the page renders a dozen
        suggested questions at once, and submitting the one you filled in should
        not complain about the eleven you skipped.
        """
        answer = (fields.get("answer") or "").strip()
        pattern = (fields.get("pattern") or "").strip()
        if not answer or not pattern:
            return 303, "/answers"
        try:
            answers.add(
                conn, pattern, answer,
                company=(fields.get("company") or "").strip() or None,
            )
            answers.prune_answered(conn)
            conn.commit()
        except ValueError as exc:
            return _page("Not stored", str(exc), 400)
        return 303, "/answers"

    def _add_competition(self, conn: sqlite3.Connection, fields: dict[str, str]) -> tuple[int, str]:
        name = (fields.get("name") or "").strip()
        category = (fields.get("category") or "").strip()
        valid_categories = {v for v, _label in pages.COMPETITION_CATEGORIES}
        if not name:
            return _page("Not added", "A competition needs a name.", 400)
        if category not in valid_categories:
            return _page("Not added", f"Unknown category '{category}'.", 400)
        db.insert_row(conn, "competitions", {
            "name": name,
            "category": category,
            "result": (fields.get("result") or "").strip() or None,
            "period": (fields.get("period") or "").strip() or None,
            "description": (fields.get("description") or "").strip() or None,
            "tech": (fields.get("tech") or "").strip() or None,
            "url": (fields.get("url") or "").strip() or None,
            "deadline": (fields.get("deadline") or "").strip() or None,
            "team_size": (fields.get("team_size") or "").strip() or None,
            "tracks": (fields.get("tracks") or "").strip() or None,
            "apply_url": (fields.get("apply_url") or "").strip() or None,
        })
        conn.commit()
        return 303, "/competitions"

    # Which tables the builder page may write, and the delete confirmation each
    # needs. An allow-list, not a passthrough: the entity name arrives in the
    # URL, and without this a crafted path could reach any table in the schema.
    BUILDER_TABLES = {
        "experience": "experiences",
        "achievement": "achievements",
        "education": "education",
        "project": "projects",
        "certification": "certifications",
        "skill": "skills",
    }

    def _add_entity(
        self, conn: sqlite3.Connection, entity: str, fields: dict[str, str]
    ) -> tuple[int, str]:
        """Add one row to the profile graph from the builder page.

        Rows entered here are marked verified, because a person typed them. That
        is the same standing a LinkedIn export gets and a stronger one than
        anything a model extracted from a document.
        """
        def value(name: str) -> str:
            return (fields.get(name) or "").strip()

        title = value("title")
        skills = [s.strip() for s in value("skills").split(",") if s.strip()]

        try:
            if entity == "experience":
                if not title:
                    return _page("Not added", "A position needs a title.", 400)
                row_id = db.insert_row(conn, "experiences", {
                    "organization_id": db.upsert_organization(conn, value("org"), kind="company"),
                    "title": title,
                    "employment_type": value("type"),
                    "location": value("location"),
                    "start_date": value("start"),
                    "end_date": value("end"),
                    "is_current": 0 if value("end") else 1,
                    "verified": 1,
                })
                db.link_skills_to(conn, skills, "experience", row_id, verified=1)

            elif entity == "achievement":
                # Exactly one parent, which the schema enforces with a CHECK.
                # The form only ever posts a position, so a missing one is a bug
                # rather than something to guess a parent for.
                parent = (fields.get("experience_id") or "").strip()
                if not parent.isdigit():
                    return _page(
                        "Not added",
                        "An accomplishment has to belong to a position, project, or degree.",
                        400,
                    )
                if not title:
                    return _page("Not added", "An accomplishment needs a title.", 400)
                row_id = db.insert_row(conn, "achievements", {
                    "experience_id": int(parent),
                    "title": title,
                    "description": value("description") or title,
                    "quantified_impact": value("impact") or None,
                    "verified": 1,
                })
                db.link_skills_to(conn, skills, "achievement", row_id, verified=1)

            elif entity == "education":
                if not title:
                    return _page("Not added", "A degree needs a name.", 400)
                db.insert_row(conn, "education", {
                    "organization_id": db.upsert_organization(conn, value("org"), kind="school"),
                    "degree": title,
                    "field_of_study": value("field"),
                    "start_date": value("start"),
                    "end_date": value("end"),
                    "verified": 1,
                })

            elif entity == "project":
                if not title:
                    return _page("Not added", "A project needs a name.", 400)
                row_id = db.insert_row(conn, "projects", {
                    "name": title,
                    "description": value("description"),
                    "role": value("role"),
                    "url": value("url"),
                    "verified": 1,
                })
                db.link_skills_to(conn, skills, "project", row_id, verified=1)

            elif entity == "certification":
                if not title:
                    return _page("Not added", "A certification needs a name.", 400)
                db.insert_row(conn, "certifications", {
                    "name": title,
                    "issuer": value("org"),
                    "issue_date": value("start"),
                    "url": value("url"),
                    "verified": 1,
                })

            elif entity == "skill":
                name = value("name")
                if not name:
                    return _page("Not added", "A skill needs a name.", 400)
                db.upsert_skill(conn, name, proficiency=value("proficiency") or None, verified=1)

            else:
                return _page("Not found", f"Cannot add '{entity}'.", 404)
        except sqlite3.IntegrityError as exc:
            return _page("Not added", f"The database refused that row: {exc}", 400)

        conn.commit()
        return 303, "/profile/build"

    def _delete_entity(
        self, conn: sqlite3.Connection, entity: str, row_id: int
    ) -> tuple[int, str]:
        table = self.BUILDER_TABLES.get(entity)
        if not table:
            return _page("Not found", f"Cannot delete '{entity}'.", 404)
        if not db.delete_row(conn, table, row_id):
            return _page("Not found", f"No {entity} {row_id}.", 404)
        conn.commit()
        return 303, "/profile/build"

    def _save_profile(self, conn: sqlite3.Connection, fields: dict[str, str]) -> tuple[int, str]:
        """Write the profile form back.

        Two shapes post here: the main editor, which sends one key per column,
        and the "add anything else" box, which sends a key/value pair. Blank
        values are skipped rather than written, so submitting the editor with
        empty optional boxes does not wipe fields set elsewhere.
        """
        custom_key = (fields.get("key") or "").strip()
        if custom_key:
            value = (fields.get("value") or "").strip()
            if value:
                db.set_profile_field(conn, custom_key, value)
                conn.commit()
            return 303, "/profile/edit"

        for name, value in fields.items():
            if name in ("token", "key", "value"):
                continue
            if not str(value).strip():
                continue
            db.set_profile_field(conn, name, str(value))
        conn.commit()
        return 303, "/profile/edit"

    def _decide(self, conn: sqlite3.Connection, app_id: int, action: str) -> tuple[int, str]:
        app = db.get_application(conn, app_id)
        if not app:
            return _page("No such application", f"Application {app_id} does not exist.", 404)
        if action == "approve":
            db.update_application(conn, app_id, {"status": "approved", "approved_at": db.now()})
        elif action == "reject":
            db.update_application(conn, app_id, {"status": "rejected"})
        else:
            return _page("Unknown action", action, 404)
        conn.commit()
        return 303, f"/applications/{app_id}"

    def _verify_row(self, conn: sqlite3.Connection, table: str, row_id: str) -> tuple[int, str]:
        if table not in pages.REVIEWABLE or not row_id.isdigit():
            return _page("Not reviewable", f"{table} is not a table this page can confirm.", 400)
        conn.execute(f"UPDATE {table} SET verified = 1 WHERE id = ?", (int(row_id),))  # noqa: S608
        conn.commit()
        return 303, "/review"

    def _tailor(self, conn: sqlite3.Connection, job_id: int) -> tuple[int, str]:
        """Generate documents for one posting. Costs one model call, so it is
        serialised -- a double-clicked button must not become two calls.
        The actual work is pipeline.tailor_one(), shared with the MCP
        server's tailor_job tool so there is exactly one place this logic
        lives."""
        with self._lock:
            config = self._fresh_config()
            try:
                app_id = pipeline.tailor_one(conn, config, job_id)
            except pipeline.TailorError as exc:
                return _page("Tailoring failed", str(exc), 404 if "not in the database" in str(exc) else 500)
        return 303, f"/applications/{app_id}"


def _handler_class(app: App) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "jobsearch"
        sys_version = ""

        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip().lower()
            if host in ALLOWED_HOSTS_SUFFIX or host == "":
                return True
            # A deployment answers on its own domain, so the rebinding check
            # cannot be "loopback only" there. It becomes "the host I was told
            # to expect" instead -- still a fixed allow-list, never a wildcard.
            expected = os.environ.get("JOBSEARCH_HOST", "").strip().lower()
            return bool(expected) and host == expected

        def _send(self, status: int, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            # This page never belongs in a frame.
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            # Still `default-src 'none'`. The one script on these pages is
            # static, so it is allowed by hash rather than by 'unsafe-inline' --
            # every other inline script stays refused, including anything a job
            # description manages to smuggle through. `data:` is for the grain
            # texture, which is an inline SVG.
            script_src = f"'{assets.SITE_JS_HASH}' '{evoque.SCRIPT_HASH}'"
            if assets.REACT_BUNDLE_JS_HASH:
                # Only the Reach/Funnel pages emit a second inline script (the
                # built React bundle); every other page still carries just
                # SITE_JS_HASH, so allow-listing this hash too is a no-op
                # everywhere else.
                script_src += f" '{assets.REACT_BUNDLE_JS_HASH}'"
            # Google Fonts is the one external origin this policy allows, and
            # only for a stylesheet and the font files it pulls -- the Evoque
            # pages' typography (Sora/Inter) is part of the design and several
            # rules name Sora with no fallback. The tradeoff is real and worth
            # stating plainly: it means Google sees a request each time one of
            # these pages loads, from a site that displays a full career
            # history. Nothing else may be fetched cross-origin; to close even
            # this, self-host the two woff2 files and drop these two sources.
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; "
                "style-src 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src https://fonts.gstatic.com; "
                f"script-src {script_src}; "
                "img-src 'self' data:; "
                "form-action 'self'",
            )
            self.end_headers()
            self.wfile.write(payload)

        def _redirect(self, location: str) -> None:
            self.send_response(303)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _session_token(self) -> str:
            jar: SimpleCookie = SimpleCookie()
            jar.load(self.headers.get("Cookie", ""))
            morsel = jar.get(SESSION_COOKIE)
            return morsel.value if morsel else ""

        def _authorised(self) -> bool:
            """A no-op once no password is configured (safe: `serve` refuses a
            public bind without one, so loopback-only and no-password can never
            both be true). Otherwise requires a valid session cookie, set by a
            successful POST to /login.
            """
            if not getattr(app, "password", ""):
                return True
            return app.session_valid(self._session_token())

        def _set_session_cookie(self, token: str, *, clear: bool = False) -> str:
            jar: SimpleCookie = SimpleCookie()
            jar[SESSION_COOKIE] = "" if clear else token
            morsel = jar[SESSION_COOKIE]
            morsel["httponly"] = True
            morsel["path"] = "/"
            morsel["samesite"] = "Lax"
            if app.public:
                morsel["secure"] = True
            if clear:
                morsel["max-age"] = 0
            else:
                morsel["max-age"] = SESSION_TTL_SECONDS
            return morsel.OutputString()

        def _guard(self) -> bool:
            if not self._host_ok():
                self._send(*_page("Blocked", "Unexpected Host header.", 403))
                return False
            if not self._authorised():
                self._redirect("/login")
                return False
            return True

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's naming
            if not self._host_ok():
                self._send(*_page("Blocked", "Unexpected Host header.", 403))
                return
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/login":
                self._send(200, app.login_page())
                return
            if not self._guard():
                return
            query = urllib.parse.parse_qs(parsed.query)
            status, body = app.get(parsed.path, query)
            if status == 303:
                self._redirect(body)
            else:
                self._send(status, body)

        def do_POST(self) -> None:  # noqa: N802
            if not self._host_ok():
                self._send(*_page("Blocked", "Unexpected Host header.", 403))
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length > 1_000_000:
                self._send(*_page("Too large", "Refusing an oversized form post.", 413))
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            fields = {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path == "/login":
                token = app.try_login(fields)
                if token is None:
                    self._send(200, app.login_page(error="Wrong password."))
                    return
                self.send_response(303)
                self.send_header("Location", "/")
                self.send_header("Set-Cookie", self._set_session_cookie(token))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if parsed.path == "/logout":
                app.destroy_session(self._session_token())
                self.send_response(303)
                self.send_header("Location", "/login")
                self.send_header("Set-Cookie", self._set_session_cookie("", clear=True))
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            if not self._guard():
                return
            status, body = app.post(parsed.path, fields)
            if status == 303:
                self._redirect(body)
            else:
                self._send(status, body)

        def log_message(self, fmt: str, *args: Any) -> None:
            return  # the CLI prints its own line; access logs add nothing here

    return Handler


def serve(
    *,
    db_path: str | Path | None = None,
    config: Config | None = None,
    host: str = "127.0.0.1",
    port: int = 8765,
    open_browser: bool = True,
    ready: Callable[[str], None] | None = None,
) -> None:
    """Run until interrupted.

    Loopback by default. A public bind is possible -- Render and friends need
    0.0.0.0 -- but only with a password set, because the alternative is putting
    someone's address, phone number, employment history, and the ability to send
    applications on the open internet behind no door at all.
    """
    password = os.environ.get("JOBSEARCH_PASSWORD", "")
    if host not in ("127.0.0.1", "localhost", "::1") and not password:
        raise WebError(
            f"Refusing to bind {host} with no password.\n"
            "This server exposes your full career history and drafts addressed to "
            "employers, and it can send applications.\n"
            "Set JOBSEARCH_PASSWORD to a long random string to bind publicly, or "
            "leave the host as 127.0.0.1."
        )
    app = App(db_path, config or Config.load(), secrets.token_urlsafe(32))
    app.password = password
    app.public = host not in ("127.0.0.1", "localhost", "::1")
    server = ThreadingHTTPServer((host, port), _handler_class(app))
    url = f"http://{host}:{server.server_address[1]}/"
    if ready:
        ready(url)
    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
