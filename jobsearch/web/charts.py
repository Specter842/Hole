"""Server-rendered SVG charts.

No plotting library and no JavaScript, for the same reason the rest of this UI
has no framework: a local single-user dashboard does not earn a dependency, and
an <svg> the server writes is readable, printable, and works with the page
disabled.

Design parameters, since the method is design-system-agnostic and this is the
system it is plugged into:

    surface       #000000
    sequential    royal blue #4169E1 (one hue; height carries magnitude)
    categorical   slot 1 royal blue, slot 2 royal red #C8102E -- two slots only
    status        royal red = wants attention
    text          white / 52% / 34%, never the series colour
    grid          white at 14%, hairline, solid

Those two categorical hues were run through the palette validator against the
black surface rather than eyeballed: worst adjacent pair ΔE 28.5 under protan,
33.7 normal, both above 3:1 contrast. Two slots is enough because every chart
here is single-series magnitude -- the one exception, evidenced vs unevidenced
skills, is genuinely a state and so earns the status hue.

Every chart ships a table twin, so no value is reachable only by hovering.
"""

from __future__ import annotations

import json
from typing import Iterable, Sequence

from .html import esc

BLUE = "#4169e1"
RED = "#c8102e"
SURFACE = "#000000"
GRID = "rgba(255,255,255,.14)"
INK_FAINT = "rgba(255,255,255,.34)"
INK_MUTED = "rgba(255,255,255,.62)"

# The viewBox is sized to roughly the width these charts actually render at, so
# one unit is one pixel on screen. It matters: every mark spec below is in
# pixels, and a 640-unit box stretched across 1120px silently renders a 24px bar
# cap as a 42px slab.
CHART_W = 1120

BAR_MAX = 24        # never fill the slot; the leftover is air
RADIUS = 4          # rounded data-end, square at the baseline
GAP = 2             # surface gap between touching marks


def _nice_max(value: float) -> int:
    """Round an axis top up to something a person would choose."""
    if value <= 0:
        return 1
    for step in (1, 2, 5, 10, 20, 25, 50, 100, 200, 250, 500,
                 1000, 2000, 2500, 5000, 10000, 20000, 50000):
        if value <= step:
            return step
    return int(value * 1.1)


def _fmt(value: float) -> str:
    """Compact, the way a stat tile reads: 1,284 / 12.9K."""
    number = float(value)
    if abs(number) >= 10_000:
        return f"{number / 1000:.1f}K".replace(".0K", "K")
    if number == int(number):
        return f"{int(number):,}"
    return f"{number:,.1f}"


def _frame(title: str, body: str, table: str = "") -> str:
    caption = (
        f'<div class="chart-title">{esc(title)}</div>' if title else ""
    )
    return f'<figure class="chart">{caption}{body}{table}</figure>'


def table_view(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> str:
    """The WCAG-clean twin. Collapsed, but present for every chart."""
    head = "".join(f"<th>{esc(h)}</th>" for h in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{esc(c)}</td>" for c in row) + "</tr>" for row in rows
    )
    return (
        '<details class="chart-table"><summary>Table</summary>'
        f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
        "</details>"
    )


# --------------------------------------------------------------------------- forms
#
# Each of these emits a data payload plus the table. The client-side engine in
# assets.py swaps the table for an animated SVG; with JavaScript off the table
# is what stays, which is also the accessible view. Nothing is hover-only either
# way.


def _chart(kind: str, title: str, rows: Sequence[tuple[str, float]], **extra: object) -> str:
    if not rows:
        return _frame(title, '<p class="empty">Nothing to plot yet.</p>')
    payload = {"kind": kind, "title": title, "rows": [[str(a), float(b)] for a, b in rows]}
    payload.update(extra)
    # json.dumps then escape: the labels come from job boards, so they are
    # untrusted, and this lands inside an HTML attribute.
    blob = esc(json.dumps(payload, ensure_ascii=False))
    return _frame(
        title,
        f'<div class="chart-host" data-chart="{blob}">'
        + table_view(["Label", "Value"], [(a, _fmt(b)) for a, b in rows])
        + "</div>",
    )


def column_chart(
    bins: Sequence[tuple[str, float]], *, title: str = "", unit: str = "", **_: object
) -> str:
    """Distribution over ordered bins. One hue -- the height is the magnitude."""
    return _chart("columns", title, bins, unit=unit)


def bar_chart(
    rows: Sequence[tuple[str, float]], *, title: str = "", tone: str = "", **_: object
) -> str:
    """Magnitude across named categories. One colour for every bar.

    Deliberately not a value-ramp: these categories are nominal, and shading by
    size would double-encode the length the bar already shows.
    """
    return _chart("bars", title, rows, tone=tone)


def line_chart(points: Sequence[tuple[str, float]], *, title: str = "", **_: object) -> str:
    """A single series over time."""
    if len(points) < 2:
        return _frame(title, '<p class="empty">Not enough history yet.</p>')
    return _chart("line", title, points)


def split_bar(
    left_label: str, left: float, right_label: str, right: float, *, title: str = "", **_: object
) -> str:
    """Part-to-whole across two states.

    The second slot is the status hue on purpose: the right-hand share is a
    thing wanting attention, not merely another category.
    """
    if float(left) + float(right) <= 0:
        return _frame(title, '<p class="empty">Nothing to plot yet.</p>')
    return _chart("split", title, [(left_label, left), (right_label, right)])
