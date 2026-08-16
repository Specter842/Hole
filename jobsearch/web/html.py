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

from .assets import SITE_JS

NAV = (
    ("/", "Dashboard"),
    ("/terminal", "Terminal"),
    ("/reach", "Reach"),
    ("/funnel", "Funnel"),
    ("/jobs", "Jobs"),
    ("/queue", "Queue"),
    ("/profile/build", "History"),
    ("/profile/edit", "Details"),
    ("/answers", "Answers"),
    ("/review", "Review"),
    ("/runs", "Runs"),
)

STYLESHEET = r"""
/* Editorial dark: a near-black canvas, oversized tight display type, and small
   uppercase tracked labels sitting in a left gutter beside their content.
   Structure is carried by hairline rules and whitespace rather than by boxes,
   so the only boxes on the page are the ones you type into.

   Four colours and nothing else: black, white, royal blue, royal red. Greys are
   white at low alpha, so no fifth hue enters through a border or a placeholder.
   Blue marks what is affirmative or in focus; red marks what warns or removes. */
:root {
  color-scheme: dark;
  --black: #000000;
  --white: #ffffff;
  --royal-blue: #4169e1;
  --royal-red: #c8102e;

  --bg: var(--black);
  --text: var(--white);
  --muted: rgba(255, 255, 255, .52);
  --faint: rgba(255, 255, 255, .34);
  --line: rgba(255, 255, 255, .14);
  --line-strong: rgba(255, 255, 255, .28);
  --field: rgba(255, 255, 255, .04);
  --accent: var(--royal-blue);
  --good: var(--royal-blue);
  --warn: var(--royal-red);
  --bad: var(--royal-red);
  --on-accent: var(--white);
  --sans: "Inter", system-ui, -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
  --mono: ui-monospace, SFMono-Regular, "Cascadia Mono", Menlo, Consolas, monospace;
  --gutter: 132px;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 16px/1.6 var(--sans);
  -webkit-font-smoothing: antialiased;
  letter-spacing: -0.005em;
}

a { color: inherit; text-decoration: none; border-bottom: 1px solid var(--line-strong); }
a:hover { border-bottom-color: var(--royal-blue); color: var(--royal-blue); }

/* -- chrome -------------------------------------------------------------- */
header.bar {
  position: sticky; top: 0; z-index: 20;
  display: flex; align-items: center; justify-content: space-between;
  gap: 30px; padding: 22px 44px;
  background: rgba(0, 0, 0, .82);
  backdrop-filter: blur(14px);
  border-bottom: 1px solid var(--line);
}
header.bar .brand {
  font-weight: 700; font-size: 15px; letter-spacing: -0.01em;
}
header.bar nav { display: flex; gap: 26px; flex-wrap: wrap; }
header.bar nav a {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .14em; color: var(--faint); border: 0; padding: 4px 0;
}
header.bar nav a:hover { color: var(--text); }
header.bar nav a.on { color: var(--text); border-bottom: 1px solid var(--royal-blue); }

main { max-width: 1220px; margin: 0 auto; padding: 68px 44px 140px; }

/* -- type ---------------------------------------------------------------- */
h1 {
  font-size: clamp(40px, 6vw, 68px); line-height: 1.02; font-weight: 700;
  letter-spacing: -0.035em; margin: 0 0 20px; max-width: 16ch;
}
h2 {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .16em; color: var(--faint);
  margin: 78px 0 22px; padding-top: 22px; border-top: 1px solid var(--line);
}
h3 { font-size: 20px; font-weight: 600; letter-spacing: -0.02em; margin: 0 0 14px; }
p { margin: 0 0 16px; }
.sub, .muted { color: var(--muted); }
.sub { font-size: 18px; max-width: 62ch; margin: 0 0 40px; }
.lead { font-size: clamp(20px, 2.4vw, 27px); line-height: 1.42; letter-spacing: -0.02em; max-width: 30ch; }
.mono { font-family: var(--mono); font-size: 13px; }
.label {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .14em; color: var(--faint);
}

/* -- gutter rows: small label left, content right ------------------------ */
.row {
  display: grid; grid-template-columns: var(--gutter) 1fr; gap: 34px;
  padding: 30px 0; border-top: 1px solid var(--line); align-items: start;
}
.row > .idx {
  font-size: 11px; letter-spacing: .14em; color: var(--faint);
  text-transform: uppercase; padding-top: 6px;
}
.row .title { font-size: clamp(22px, 3vw, 33px); font-weight: 700; letter-spacing: -0.03em; line-height: 1.1; }
.row .meta { font-size: 11px; letter-spacing: .14em; text-transform: uppercase; color: var(--faint); margin-top: 8px; }
.row-head { display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; }

/* -- stats --------------------------------------------------------------- */
.grid { display: grid; gap: 0; grid-template-columns: repeat(auto-fit, minmax(168px, 1fr)); border-top: 1px solid var(--line); }
.stat { padding: 26px 26px 26px 0; border-right: 1px solid var(--line); }
.stat:last-child { border-right: 0; }
.stat .n { font-size: 42px; font-weight: 700; letter-spacing: -0.04em; line-height: 1; }
.stat .k { font-size: 11px; text-transform: uppercase; letter-spacing: .14em; color: var(--faint); margin-top: 10px; }

/* -- form fields: the only boxes on the page ----------------------------- */
form.stack { display: flex; flex-direction: column; gap: 22px; }
label.field { display: flex; flex-direction: column; gap: 9px; }
/* Scoped to the caption, not to every span: the hint is also a direct child
   here, and uppercasing a sentence of guidance makes it unreadable. */
label.field > span.caption {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .14em; color: var(--muted);
}
input[type=text], input[type=email], input[type=url], input[type=tel],
input[type=password], input[type=number], textarea, select {
  width: 100%; padding: 15px 17px; font: inherit; font-size: 16px;
  background: var(--field); color: var(--text);
  border: 1px solid var(--line-strong); border-radius: 2px;
  transition: border-color .12s ease, background .12s ease;
}
input::placeholder, textarea::placeholder { color: rgba(255, 255, 255, .26); }
input:hover, textarea:hover, select:hover { border-color: rgba(255, 255, 255, .42); }
input:focus, textarea:focus, select:focus {
  outline: none; border-color: var(--royal-blue);
  background: rgba(65, 105, 225, .07);
  box-shadow: inset 0 0 0 1px var(--royal-blue);
}
textarea { resize: vertical; min-height: 108px; line-height: 1.55; }
select {
  appearance: none; cursor: pointer;
  background-image: linear-gradient(45deg, transparent 50%, rgba(255,255,255,.5) 50%),
                    linear-gradient(135deg, rgba(255,255,255,.5) 50%, transparent 50%);
  background-position: calc(100% - 20px) 24px, calc(100% - 14px) 24px;
  background-size: 6px 6px, 6px 6px;
  background-repeat: no-repeat;
}
.field .hint { font-size: 12px; color: var(--faint); line-height: 1.5; }
.grid2 { display: grid; grid-template-columns: repeat(auto-fit, minmax(258px, 1fr)); gap: 22px; }

/* -- buttons ------------------------------------------------------------- */
button, .btn {
  font: inherit; font-size: 11px; font-weight: 600; cursor: pointer;
  text-transform: uppercase; letter-spacing: .14em;
  padding: 13px 26px; border-radius: 2px;
  border: 1px solid var(--line-strong); background: transparent; color: var(--text);
  transition: border-color .12s ease, background .12s ease, color .12s ease;
}
button:hover, .btn:hover { border-color: var(--white); background: rgba(255,255,255,.06); }
button.primary { background: var(--royal-blue); border-color: var(--royal-blue); color: var(--on-accent); }
button.primary:hover { background: #3557c4; border-color: #3557c4; }
/* Quiet until wanted: a destructive control repeated down every row should not
   be the loudest thing on the page. */
button.danger {
  color: rgba(255, 255, 255, .38); border-color: transparent;
  padding: 9px 14px; background: transparent;
}
button.danger:hover {
  color: var(--royal-red); border-color: rgba(200, 16, 46, .55);
  background: rgba(200, 16, 46, .1);
}
li:hover > .ach > form button.danger,
.answer-row:hover button.danger,
.row-head:hover button.danger { color: rgba(255, 255, 255, .62); }
form.inline { display: inline; }
.actions { display: flex; gap: 12px; flex-wrap: wrap; align-items: center; margin-top: 8px; }

/* -- cards, tables, notices ---------------------------------------------- */
.card { border-top: 1px solid var(--line); padding: 28px 0; }
.card h2 { margin-top: 0; border-top: 0; padding-top: 0; }
.card h3 { margin-top: 0; }

table { width: 100%; border-collapse: collapse; font-size: 15px; }
th, td { text-align: left; padding: 17px 20px 17px 0; border-bottom: 1px solid var(--line); vertical-align: top; }
th {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .14em; color: var(--faint); border-bottom-color: var(--line-strong);
}
tbody tr:hover td { background: rgba(255,255,255,.025); }
.scroll { overflow-x: auto; }

.pill {
  display: inline-block; padding: 5px 11px; border-radius: 2px;
  font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: .12em;
  border: 1px solid var(--line-strong); color: var(--muted); white-space: nowrap;
}
.pill.good { color: var(--royal-blue); border-color: rgba(65,105,225,.55); }
.pill.warn, .pill.bad { color: var(--royal-red); border-color: rgba(200,16,46,.55); }

.bar-track { background: rgba(255,255,255,.1); border-radius: 1px; height: 3px; width: 104px; overflow: hidden; }
.bar-fill { height: 100%; background: var(--royal-blue); }

.notice {
  border-left: 2px solid var(--royal-blue); padding: 16px 0 16px 22px; margin: 0 0 22px;
  font-size: 15px;
}
.notice.bad, .notice.warn { border-left-color: var(--royal-red); }
.notice ul { margin: 10px 0 0; padding-left: 18px; color: var(--muted); }
.notice li { margin: 4px 0; }

.doc {
  border: 1px solid var(--line); border-radius: 2px; padding: 22px 24px;
  white-space: pre-wrap; font-family: var(--mono); font-size: 13px;
  line-height: 1.7; overflow-x: auto; background: var(--field);
}
.empty { color: var(--faint); padding: 60px 0; text-align: center; font-size: 15px; }
ul.tight { margin: 14px 0 0; padding-left: 0; list-style: none; }
ul.tight li { margin: 0; padding: 15px 0; border-top: 1px solid var(--line); }
.kv { display: grid; grid-template-columns: var(--gutter) 1fr; gap: 14px 34px; font-size: 15px; }
.kv dt { font-size: 11px; text-transform: uppercase; letter-spacing: .14em; color: var(--faint); padding-top: 3px; }
.kv dd { margin: 0; }

/* -- charts --------------------------------------------------------------- */
figure.chart { margin: 0 0 46px; }
.chart-title {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .14em; color: var(--faint); margin-bottom: 18px;
}
.chart-host { min-height: 60px; }
/* Until the engine runs, the table is the chart. Once it has drawn, the table
   folds away into its disclosure rather than disappearing. */
.chart-host.ready > .chart-table { margin-top: 18px; }
svg.plot { width: 100%; height: auto; display: block; overflow: visible; }
svg.plot .tick {
  font: 10px/1 var(--mono); fill: var(--faint);
  font-variant-numeric: tabular-nums; letter-spacing: .06em;
}
svg.plot .cat { font: 13px/1 var(--sans); fill: var(--muted); }
svg.plot .val {
  font: 12px/1 var(--mono); fill: var(--text);
  font-variant-numeric: tabular-nums;
}
svg.plot .hit { cursor: crosshair; }
svg.plot .mark { will-change: transform; }

.tip {
  position: fixed; z-index: 60; pointer-events: none;
  background: rgba(10,10,10,.96); border: 1px solid var(--line-strong);
  border-radius: 4px; padding: 9px 12px; min-width: 96px;
  opacity: 0; transform: translateY(3px);
  transition: opacity .12s ease, transform .12s ease;
  backdrop-filter: blur(8px);
}
.tip.on { opacity: 1; transform: translateY(0); }
.tip b {
  display: block; font: 600 17px/1.1 var(--sans); letter-spacing: -.02em;
  font-variant-numeric: tabular-nums;
}
.tip span {
  display: block; margin-top: 5px; font-size: 11px; letter-spacing: .1em;
  text-transform: uppercase; color: var(--faint);
}

.chart-table { margin-top: 16px; }
.chart-table > summary {
  font-size: 10px; letter-spacing: .14em; text-transform: uppercase;
  color: var(--faint); cursor: pointer; list-style: none;
}
.chart-table > summary:hover { color: var(--royal-blue); }
.chart-table > summary::-webkit-details-marker { display: none; }
.chart-table > summary::before { content: "+  "; }
.chart-table[open] > summary::before { content: "\2212  "; }
.chart-table table { margin-top: 14px; max-width: 440px; font-size: 13px; }
.chart-table td, .chart-table th { padding: 8px 20px 8px 0; }
.chart-table td:last-child { font-family: var(--mono); font-variant-numeric: tabular-nums; }

/* The one number a view leads with. Proportional figures on purpose --
   tabular would make it look loose at this size. */
.hero { padding: 12px 0 40px; }
.hero-n {
  font-size: clamp(64px, 11vw, 132px); font-weight: 700;
  letter-spacing: -.05em; line-height: .92;
  background: linear-gradient(170deg, #fff 30%, rgba(255,255,255,.62));
  -webkit-background-clip: text; background-clip: text;
  -webkit-text-fill-color: transparent;
}
.hero-k {
  font-size: 11px; text-transform: uppercase; letter-spacing: .16em;
  color: var(--faint); margin-top: 16px;
}

/* -- motion --------------------------------------------------------------- */
/* `.rise` alone is always fully visible -- it only marks an element as a
   candidate for the reveal animation. The hidden state lives on `.pending`,
   which the script adds at runtime right before it starts observing. That
   ordering matters: content must default to visible and JS may only ever make
   it *nicer*, never make it appear. Without this split, any page where the
   inline script does not run -- JavaScript disabled, blocked by an extension,
   or simply slow to parse -- would leave every `.rise` section permanently
   blank, which a full-page capture (no real scrolling, so no intersection
   ever fires) caught directly. */
.rise.pending {
  opacity: 0; transform: translateY(14px);
  transition: opacity .6s cubic-bezier(.22,.9,.3,1), transform .6s cubic-bezier(.22,.9,.3,1);
}
.rise.pending.in { opacity: 1; transform: none; }

/* A faint grain over the whole page, so large black areas have some tooth
   instead of reading as a dead flat fill. */
body::after {
  content: ""; position: fixed; inset: 0; z-index: 1; pointer-events: none;
  opacity: .04;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='140' height='140'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.85' numOctaves='3'/%3E%3C/filter%3E%3Crect width='140' height='140' filter='url(%23n)'/%3E%3C/svg%3E");
}
header.bar, main { position: relative; z-index: 2; }

/* -- reach: two-column row, bubble cluster + ranked list ------------------ */
.row2 { display: grid; grid-template-columns: 1.6fr 1fr; gap: 28px; align-items: stretch; }
@media (max-width: 900px) { .row2 { grid-template-columns: 1fr; } }
.panel {
  border: 1px solid var(--line); border-radius: 6px; padding: 26px 28px;
  background: rgba(255,255,255,.015);
}
.panel .chart-title { margin-bottom: 22px; }

.bubbles {
  display: flex; flex-wrap: wrap; align-items: center; justify-content: center;
  gap: 14px; min-height: 220px; padding: 10px 0;
}
.bubble {
  width: var(--d); height: var(--d); border-radius: 50%;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  background: radial-gradient(circle at 32% 28%, rgba(65,105,225,.55), rgba(65,105,225,.16) 72%);
  border: 1px solid rgba(65,105,225,.5);
  transition: transform .18s ease, border-color .18s ease;
  cursor: default;
}
.bubble:hover { transform: scale(1.05); border-color: rgba(65,105,225,.9); }
.bubble .bn {
  font: 700 var(--fs)/1 var(--sans); letter-spacing: -.02em;
  font-variant-numeric: tabular-nums;
}
.bubble .bl {
  font-size: 10px; text-transform: uppercase; letter-spacing: .1em;
  color: rgba(255,255,255,.68); margin-top: 4px; text-align: center;
  max-width: 88%; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}
.bubble.rise.pending { opacity: 0; transform: scale(.7); }
.bubble.rise.pending.in { opacity: 1; transform: scale(1); transition: opacity .55s ease, transform .55s cubic-bezier(.22,.9,.3,1); }

.ranked-list { list-style: none; margin: 0; padding: 0; }
.ranked-row {
  display: grid; grid-template-columns: 26px 1fr 96px 60px; align-items: center;
  gap: 14px; padding: 12px 0; border-top: 1px solid var(--line);
}
.ranked-row:first-child { border-top: 0; }
.rn { font: 11px/1 var(--mono); color: var(--faint); }
.rl {
  font-size: 13px; color: var(--muted); overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap;
}
.rank-track { height: 4px; border-radius: 2px; background: rgba(255,255,255,.08); overflow: hidden; }
.rank-fill {
  display: block; height: 100%; width: 0; background: var(--royal-blue);
  border-radius: 2px; transition: width .8s cubic-bezier(.22,.9,.3,1);
}
.rise.in .rank-fill { width: var(--w); }
.rv {
  font: 12px/1 var(--mono); text-align: right; color: var(--text);
  font-variant-numeric: tabular-nums;
}

/* -- donut ------------------------------------------------------------- */
.donut-wrap { display: flex; flex-direction: column; align-items: center; gap: 18px; }
svg.donut { max-width: 220px; }
.donut-pct {
  font: 700 30px/1 var(--sans); fill: var(--text); letter-spacing: -.02em;
}
.donut-sub {
  font: 10px/1 var(--sans); fill: var(--faint); text-transform: uppercase; letter-spacing: .12em;
}
.donut-legend { display: flex; gap: 22px; flex-wrap: wrap; justify-content: center; }
.donut-legend span {
  font-size: 12px; color: var(--muted); display: inline-flex; align-items: center; gap: 7px;
}
.donut-legend i { width: 8px; height: 8px; border-radius: 50%; display: inline-block; }
.donut-legend b { color: var(--text); font-variant-numeric: tabular-nums; font-weight: 600; }

/* -- activity row: three equal cards --------------------------------- */
.row3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 28px; align-items: stretch; }
.row3 .panel { display: flex; flex-direction: column; }
@media (max-width: 980px) { .row3 { grid-template-columns: 1fr; } }

/* -- filter row ----------------------------------------------------------- */
.filter-row {
  display: flex; align-items: center; gap: 16px; flex-wrap: wrap;
  margin: 0 0 26px;
}
.filter-row input { max-width: 340px; padding: 12px 15px; font-size: 14px; }
.filter-row .count {
  font: 11px/1 var(--mono); color: var(--faint);
  letter-spacing: .1em; text-transform: uppercase;
}

/* -- profile builder ------------------------------------------------------ */
.ach { display: flex; justify-content: space-between; align-items: flex-start; gap: 22px; }
/* An accomplishment is subordinate to the position it sits under, so it must
   not compete with the position's title for weight. */
.ach strong { font-weight: 400; font-size: 15px; line-height: 1.55; max-width: 78ch; display: block; }
.ach .muted { font-size: 14px; margin-top: 5px; max-width: 74ch; }
.impact {
  font-size: 11px; font-family: var(--mono); color: var(--royal-blue);
  margin-top: 7px; letter-spacing: .02em;
}
.answer-row {
  display: flex; justify-content: space-between; align-items: flex-start;
  gap: 22px; padding: 19px 0; border-top: 1px solid var(--line);
}
.answer-row .pattern { font-family: var(--mono); font-size: 13px; }
.answer-row .value { color: var(--muted); font-size: 15px; margin-top: 5px; max-width: 74ch; }
.count { font-family: var(--mono); color: var(--royal-red); font-weight: 700; }

details > summary {
  cursor: pointer; list-style: none; margin-top: 18px;
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: .14em; color: var(--faint);
}
details > summary:hover { color: var(--royal-blue); }
details > summary::-webkit-details-marker { display: none; }
details > summary::before { content: "+  "; }
details[open] > summary::before { content: "\2212  "; }
details[open] > summary { margin-bottom: 24px; color: var(--text); }

@media (max-width: 820px) {
  main { padding: 44px 22px 90px; }
  header.bar { padding: 18px 22px; }
  .row, .kv { grid-template-columns: 1fr; gap: 12px; }
  .stat { border-right: 0; border-bottom: 1px solid var(--line); padding-right: 0; }
}
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
        f"<title>{esc(title)} - Hole</title>"
        f"<style>{STYLESHEET}</style></head><body>"
        f'<header class="bar"><span class="brand">Hole</span><nav>{links}</nav></header>'
        f"<main>{body}</main>"
        f"<script>{SITE_JS}</script></body></html>"
    )


def _countable(number: Any) -> str:
    """Mark a figure for the count-up animation when it is really a number.

    Values like "10/20" are left alone -- animating them would need parsing that
    could only get it wrong, and a wrong number here is worse than a static one.
    """
    text = str(number)
    plain = text.replace(",", "").replace("%", "")
    try:
        float(plain)
    except ValueError:
        return f"<div class='n'>{esc(text)}</div>"
    suffix = "%" if text.endswith("%") else ""
    return (
        f"<div class='n' data-count='{esc(plain.rstrip('%'))}' "
        f"data-suffix='{esc(suffix)}'>{esc(text)}</div>"
    )


def stat(number: Any, label: str) -> str:
    return (
        f'<div class="card stat">{_countable(number)}'
        f'<div class="k">{esc(label)}</div></div>'
    )


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
    return (
        f'<label class="field" for="{ident}">'
        f'<span class="caption">{esc(label)}</span>{control}{note}</label>'
    )


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
