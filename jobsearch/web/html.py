"""Page chrome: escaping, layout, and the stylesheet.

No template engine and no CSS framework, for the same reason this project parses
.docx with the standard library -- a local single-user review UI does not earn a
dependency. Everything here is a function that returns a string.

The one rule that matters: `esc()` every value that came from a job board, a
document, or a model. Job descriptions are attacker-controlled text as far as
this server is concerned.
"""

from __future__ import annotations

import html
from typing import Any, Iterable, Sequence

NAV = (
    ("/", "Dashboard"),
    ("/jobs", "Jobs"),
    ("/queue", "Queue"),
    ("/profile", "Profile"),
    ("/answers", "Answers"),
    ("/review", "Review"),
    ("/runs", "Runs"),
)

STYLESHEET = """
:root {
  color-scheme: light dark;
  --bg: #f6f7f9;
  --surface: #ffffff;
  --surface-2: #f0f2f5;
  --text: #14171c;
  --muted: #666e7a;
  --border: #d9dde3;
  --accent: #2a6df4;
  --good: #1a7f45;
  --warn: #9a6400;
  --bad: #b3261e;
  --mono: ui-monospace, SFMono-Regular, "Cascadia Mono", Menlo, Consolas, monospace;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #14171c;
    --surface: #1c2027;
    --surface-2: #232830;
    --text: #e6e9ee;
    --muted: #98a1ad;
    --border: #2f3742;
    --accent: #6ea3ff;
    --good: #4ac97e;
    --warn: #e0aa3e;
    --bad: #ff6b60;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 15px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
header.bar {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 0 20px;
  display: flex; align-items: center; gap: 22px;
  position: sticky; top: 0; z-index: 5;
}
header.bar .brand { font-weight: 600; padding: 14px 0; margin-right: 6px; }
header.bar nav { display: flex; gap: 18px; flex-wrap: wrap; }
header.bar nav a {
  padding: 14px 0; color: var(--muted); border-bottom: 2px solid transparent;
}
header.bar nav a.on { color: var(--text); border-bottom-color: var(--accent); }
main { max-width: 1100px; margin: 0 auto; padding: 26px 20px 80px; }
h1 { font-size: 22px; margin: 0 0 4px; }
h2 { font-size: 16px; margin: 30px 0 10px; }
h3 { font-size: 14px; margin: 18px 0 6px; }
.sub { color: var(--muted); margin: 0 0 22px; }
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 16px 18px; margin-bottom: 14px;
}
.grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); }
.stat .n { font-size: 26px; font-weight: 600; }
.stat .k { color: var(--muted); font-size: 13px; }
table { width: 100%; border-collapse: collapse; font-size: 14px; }
th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--border); vertical-align: top; }
th { color: var(--muted); font-weight: 500; font-size: 12px; text-transform: uppercase; letter-spacing: .04em; }
tr:last-child td { border-bottom: none; }
.scroll { overflow-x: auto; }
.pill {
  display: inline-block; padding: 2px 8px; border-radius: 20px;
  font-size: 12px; border: 1px solid var(--border); color: var(--muted);
  white-space: nowrap;
}
.pill.good { color: var(--good); border-color: currentColor; }
.pill.warn { color: var(--warn); border-color: currentColor; }
.pill.bad  { color: var(--bad);  border-color: currentColor; }
.bar-track { background: var(--surface-2); border-radius: 3px; height: 6px; width: 90px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--accent); }
.mono { font-family: var(--mono); font-size: 13px; }
.muted { color: var(--muted); }
.doc {
  background: var(--surface-2); border: 1px solid var(--border); border-radius: 8px;
  padding: 14px 16px; white-space: pre-wrap; font-family: var(--mono);
  font-size: 13px; line-height: 1.6; overflow-x: auto;
}
button, .btn {
  font: inherit; cursor: pointer; border-radius: 7px; padding: 7px 14px;
  border: 1px solid var(--border); background: var(--surface-2); color: var(--text);
}
button:hover, .btn:hover { border-color: var(--accent); text-decoration: none; }
button.primary { background: var(--accent); border-color: var(--accent); color: #fff; }
button.danger { color: var(--bad); }
form.inline { display: inline; }
.actions { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 14px; }
.notice {
  border-left: 3px solid var(--accent); background: var(--surface);
  border-radius: 0 8px 8px 0; padding: 12px 16px; margin-bottom: 14px;
}
.notice.bad { border-left-color: var(--bad); }
.notice.warn { border-left-color: var(--warn); }
.notice ul { margin: 6px 0 0; padding-left: 18px; }
.empty { color: var(--muted); padding: 26px 0; text-align: center; }
ul.tight { margin: 6px 0; padding-left: 20px; }
ul.tight li { margin: 3px 0; }
.kv { display: grid; grid-template-columns: 150px 1fr; gap: 4px 14px; font-size: 14px; }
.kv dt { color: var(--muted); }
.kv dd { margin: 0; }

/* -- forms -------------------------------------------------------------- */
form.stack { display: flex; flex-direction: column; gap: 14px; }
label.field { display: flex; flex-direction: column; gap: 5px; }
label.field > span { font-size: 13px; font-weight: 600; color: var(--muted); }
input[type=text], input[type=email], input[type=url], input[type=tel],
textarea, select {
  width: 100%; padding: 9px 11px; font: inherit;
  background: var(--surface); color: var(--text);
  border: 1px solid var(--border); border-radius: 7px;
}
input:focus, textarea:focus, select:focus {
  outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(42,109,244,.16);
}
textarea { resize: vertical; min-height: 68px; font-family: inherit; }
.field .hint { font-size: 12px; color: var(--muted); }
.actions { display: flex; gap: 10px; align-items: center; }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; }
.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 10px; padding: 16px 18px; margin: 14px 0;
}
.card h2 { margin-top: 0; }
.answer-row {
  display: flex; justify-content: space-between; align-items: flex-start; gap: 14px;
  padding: 11px 0; border-bottom: 1px solid var(--border);
}
.answer-row:last-child { border-bottom: none; }
.answer-row .pattern { font-family: var(--mono); font-size: 13px; }
.answer-row .value { color: var(--muted); font-size: 14px; margin-top: 2px; }
.count { font-family: var(--mono); color: var(--warn); font-weight: 600; }
"""


def esc(value: Any) -> str:
    """HTML-escape anything. `None` becomes an empty string, not "None"."""
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def layout(title: str, body: str, *, active: str = "") -> str:
    links = "".join(
        f'<a href="{esc(href)}" class="{"on" if href == active else ""}">{esc(label)}</a>'
        for href, label in NAV
    )
    return (
        "<!doctype html>\n"
        '<html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>{esc(title)} - jobsearch</title>"
        f"<style>{STYLESHEET}</style></head><body>"
        f'<header class="bar"><span class="brand">jobsearch</span><nav>{links}</nav></header>'
        f"<main>{body}</main></body></html>"
    )


def stat(number: Any, label: str) -> str:
    return f'<div class="card stat"><div class="n">{esc(number)}</div><div class="k">{esc(label)}</div></div>'


def pill(text: str, tone: str = "") -> str:
    return f'<span class="pill {esc(tone)}">{esc(text)}</span>'


def score_bar(score: float | None) -> str:
    """Fit score as a number plus a proportional bar."""
    if score is None:
        return '<span class="muted">--</span>'
    pct = max(0.0, min(100.0, float(score)))
    return (
        f'<div style="display:flex;align-items:center;gap:8px">'
        f'<span class="mono">{pct:.1f}</span>'
        f'<span class="bar-track"><span class="bar-fill" style="width:{pct:.0f}%"></span></span>'
        f"</div>"
    )


def table(headers: Sequence[str], rows: Iterable[Sequence[str]], *, empty: str = "Nothing here yet.") -> str:
    """Rows carry pre-rendered HTML cells -- callers escape their own values."""
    body = "".join(
        "<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows
    )
    if not body:
        return f'<div class="empty">{esc(empty)}</div>'
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    return f'<div class="scroll"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def notice(text: str, items: Sequence[str] = (), tone: str = "") -> str:
    inner = f"<strong>{esc(text)}</strong>"
    if items:
        inner += "<ul>" + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul>"
    return f'<div class="notice {esc(tone)}">{inner}</div>'


def form_button(
    action: str, label: str, token: str, *, style: str = "", confirm: str = ""
) -> str:
    """A POST button. Every mutating action goes through one of these.

    Links cannot mutate state here: a GET must never change anything, or a
    prefetch would fire it.
    """
    onclick = f' onclick="return confirm({html.escape(repr(confirm), quote=True)})"' if confirm else ""
    return (
        f'<form method="post" action="{esc(action)}" class="inline">'
        f'<input type="hidden" name="token" value="{esc(token)}">'
        f'<button class="{esc(style)}"{onclick}>{esc(label)}</button></form>'
    )


def field(
    name: str,
    label: str,
    value: Any = "",
    *,
    kind: str = "text",
    hint: str = "",
    placeholder: str = "",
    rows: int = 3,
    options: Sequence[str] = (),
) -> str:
    """One labelled input. `value` is escaped -- it may be text a board supplied."""
    ident = f"f_{esc(name)}"
    note = f'<span class="hint">{esc(hint)}</span>' if hint else ""
    if kind == "textarea":
        control = (
            f'<textarea id="{ident}" name="{esc(name)}" rows="{int(rows)}" '
            f'placeholder="{esc(placeholder)}">{esc(value)}</textarea>'
        )
    elif kind == "select":
        picked = str(value or "")
        choices = "".join(
            f'<option value="{esc(o)}"{" selected" if str(o) == picked else ""}>{esc(o)}</option>'
            for o in options
        )
        control = f'<select id="{ident}" name="{esc(name)}">{choices}</select>'
    else:
        control = (
            f'<input id="{ident}" name="{esc(name)}" type="{esc(kind)}" '
            f'value="{esc(value)}" placeholder="{esc(placeholder)}">'
        )
    return f'<label class="field" for="{ident}"><span>{esc(label)}</span>{control}{note}</label>'


def form(action: str, token: str, body: str, submit: str = "Save", *, cls: str = "") -> str:
    """A POST form carrying the session token. Mutations only ever arrive this way."""
    return (
        f'<form method="post" action="{esc(action)}" class="stack {esc(cls)}">'
        f'<input type="hidden" name="token" value="{esc(token)}">'
        f"{body}"
        f'<div class="actions"><button class="primary">{esc(submit)}</button></div>'
        f"</form>"
    )


def kv(pairs: Sequence[tuple[str, str]]) -> str:
    """Definition list. Values are pre-rendered HTML."""
    items = "".join(f"<dt>{esc(k)}</dt><dd>{v}</dd>" for k, v in pairs if v)
    return f'<dl class="kv">{items}</dl>'
