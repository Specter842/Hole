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

import secrets
import sqlite3
import threading
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from .. import answers, db, generate, graph as graph_module, pipeline, retrieval, verify
from ..config import Config
from . import pages
from .html import esc, layout

ALLOWED_HOSTS_SUFFIX = ("localhost", "127.0.0.1", "[::1]")


class WebError(RuntimeError):
    pass


def _page(title: str, message: str, status: int = 400) -> tuple[int, str]:
    body = f"<h1>{esc(title)}</h1><p class='sub'>{esc(message)}</p><p><a href='/'>Back</a></p>"
    return status, layout(title, body)


class App:
    """Routing and actions, kept apart from the HTTP plumbing so it can be tested."""

    def __init__(self, db_path: str | Path | None, config: Config, token: str) -> None:
        self.db_path = db_path
        self.config = config
        self.token = token
        self._lock = threading.Lock()

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
            if not parts:
                return 200, pages.dashboard(conn, self._fresh_config())
            if parts == ["jobs"]:
                status = (query.get("status") or [None])[0]
                return 200, pages.jobs_list(conn, status=status)
            if len(parts) == 2 and parts[0] == "jobs" and parts[1].isdigit():
                html = pages.job_detail(conn, int(parts[1]), self._fresh_config(), self.token)
                return (200, html) if html else _page("No such job", f"Job {parts[1]} is not in the database.", 404)
            if parts == ["queue"]:
                return 200, pages.queue(conn)
            if len(parts) == 2 and parts[0] == "applications" and parts[1].isdigit():
                html = pages.application_detail(conn, int(parts[1]), self.token)
                return (200, html) if html else _page("No such application", f"Application {parts[1]} does not exist.", 404)
            if parts == ["profile"]:
                return 200, pages.profile(conn)
            if parts == ["profile", "edit"]:
                return 200, pages.profile_edit(conn, self.token)
            if parts == ["answers"]:
                return 200, pages.answers_page(conn, self.token)
            if parts == ["review"]:
                return 200, pages.review(conn, self.token)
            if parts == ["runs"]:
                return 200, pages.runs(conn)
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
            if parts == ["profile", "save"]:
                return self._save_profile(conn, fields)
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
        serialised -- a double-clicked button must not become two calls."""
        job = db.get_row(conn, "jobs", job_id)
        if not job:
            return _page("No such job", f"Job {job_id} is not in the database.", 404)

        with self._lock:
            existing = conn.execute(
                "SELECT id FROM applications WHERE job_id = ?", (job_id,)
            ).fetchone()
            if existing:
                return 303, f"/applications/{existing['id']}"

            config = self._fresh_config()
            try:
                g = graph_module.ProfileGraph.load(conn)
                description = pipeline._job_description(job)
                plan = retrieval.build_plan(
                    g,
                    description,
                    company=job.get("company"),
                    role=job.get("title"),
                    verified_only=config.dispatch.require_verified_records,
                )
                result = generate.generate(
                    description, plan, model=config.llm.model or None,
                    max_tokens=config.llm.max_tokens,
                )
            except Exception as exc:
                return _page("Tailoring failed", f"{type(exc).__name__}: {exc}", 500)

            findings = verify.verify_plan(
                {"resume": result.resume, "cover_letter": result.cover_letter},
                plan.to_facts(),
                target_company=job.get("company"),
            )
            out_dir = db.PROJECT_ROOT / "output" / pipeline._slug(
                job.get("company"), job.get("title"), job_id
            )
            pipeline.write_bundle(
                out_dir,
                result=result,
                job_description=description,
                plan=plan,
                meta={
                    "job_id": job_id,
                    "source": job.get("source"),
                    "url": job.get("url"),
                    "fit_score": job.get("fit_score"),
                    "created_via": "web",
                },
            )
            app_id = db.insert_application(
                conn,
                {
                    "job_id": job_id,
                    "company": job.get("company"),
                    "role": job.get("title"),
                    "source": job.get("source"),
                    "job_url": job.get("url"),
                    "resume_version": str(out_dir),
                    "status": "drafted",
                    "fit_score": job.get("fit_score"),
                    "grounding_status": "flagged" if findings else "clean",
                },
            )
            db.update_row(conn, "jobs", job_id, {"status": "tailored"})
            conn.commit()
        return 303, f"/applications/{app_id}"


def _handler_class(app: App) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "jobsearch"
        sys_version = ""

        def _host_ok(self) -> bool:
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0].strip().lower()
            return host in ALLOWED_HOSTS_SUFFIX or host == ""

        def _send(self, status: int, body: str) -> None:
            payload = body.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            # This page never belongs in a frame, and never needs to load
            # anything from another origin.
            self.send_header("X-Frame-Options", "DENY")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header(
                "Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'",
            )
            self.end_headers()
            self.wfile.write(payload)

        def _redirect(self, location: str) -> None:
            self.send_response(303)
            self.send_header("Location", location)
            self.send_header("Content-Length", "0")
            self.end_headers()

        def _guard(self) -> bool:
            if self._host_ok():
                return True
            self._send(*_page("Blocked", "Unexpected Host header.", 403))
            return False

        def do_GET(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's naming
            if not self._guard():
                return
            parsed = urllib.parse.urlparse(self.path)
            query = urllib.parse.parse_qs(parsed.query)
            status, body = app.get(parsed.path, query)
            if status == 303:
                self._redirect(body)
            else:
                self._send(status, body)

        def do_POST(self) -> None:  # noqa: N802
            if not self._guard():
                return
            length = int(self.headers.get("Content-Length") or 0)
            if length > 1_000_000:
                self._send(*_page("Too large", "Refusing an oversized form post.", 413))
                return
            raw = self.rfile.read(length).decode("utf-8", errors="replace")
            fields = {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}
            parsed = urllib.parse.urlparse(self.path)
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
    """Run until interrupted. Refuses to listen anywhere but loopback."""
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise WebError(
            f"Refusing to bind {host}. This server exposes your full career history and "
            "drafts addressed to employers, with no login. It is loopback-only by design."
        )
    app = App(db_path, config or Config.load(), secrets.token_urlsafe(32))
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
