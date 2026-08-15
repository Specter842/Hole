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


def column_chart(
    bins: Sequence[tuple[str, float]],
    *,
    title: str = "",
    height: int = 168,
    width: int = CHART_W,
    unit: str = "",
) -> str:
    """Distribution over ordered bins. One hue -- the height is the magnitude."""
    if not bins:
        return _frame(title, '<p class="empty">Nothing to plot yet.</p>')

    pad_l, pad_r, pad_t, pad_b = 44, 12, 14, 26
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    top = _nice_max(max(v for _, v in bins))
    slot = plot_w / len(bins)
    bar_w = min(BAR_MAX, slot - GAP)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{esc(title)}" class="plot">'
    ]
    # Gridlines first, so data sits on top of them.
    for tick in range(3):
        value = top * tick / 2
        y = pad_t + plot_h - (plot_h * tick / 2)
        parts.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_l - 8}" y="{y + 3.5:.1f}" text-anchor="end" '
            f'class="tick">{esc(_fmt(value))}</text>'
        )

    for index, (label, value) in enumerate(bins):
        h = 0 if top == 0 else plot_h * (float(value) / top)
        h = max(h, 1.5) if value else 0
        x = pad_l + slot * index + (slot - bar_w) / 2
        y = pad_t + plot_h - h
        if h:
            # Rounded at the data end, square at the baseline: draw a rounded
            # rect and square off the bottom with a second one.
            parts.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{bar_w:.1f}" height="{h:.1f}" '
                f'rx="{min(RADIUS, bar_w / 2):.1f}" fill="{BLUE}">'
                f"<title>{esc(label)}: {esc(_fmt(value))}{esc(unit)}</title></rect>"
            )
            if h > RADIUS:
                parts.append(
                    f'<rect x="{x:.1f}" y="{y + RADIUS:.1f}" width="{bar_w:.1f}" '
                    f'height="{h - RADIUS:.1f}" fill="{BLUE}"/>'
                )
        parts.append(
            f'<text x="{x + bar_w / 2:.1f}" y="{height - 8}" text-anchor="middle" '
            f'class="tick">{esc(label)}</text>'
        )
    parts.append("</svg>")
    return _frame(
        title,
        "".join(parts),
        table_view(["Bin", "Count"], [(b, _fmt(v)) for b, v in bins]),
    )


def bar_chart(
    rows: Sequence[tuple[str, float]],
    *,
    title: str = "",
    width: int = CHART_W,
    row_h: int = 34,
    label_w: int = 168,
) -> str:
    """Magnitude across named categories. One colour for every bar.

    Deliberately not a value-ramp: the categories here are nominal, and shading
    by size would double-encode the length the bar already shows.
    """
    if not rows:
        return _frame(title, '<p class="empty">Nothing to plot yet.</p>')

    height = row_h * len(rows) + 8
    value_w = 56
    track = width - label_w - value_w - 12
    top = _nice_max(max(v for _, v in rows))
    bar_h = min(BAR_MAX - 8, row_h - GAP - 8)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{esc(title)}" class="plot">'
    ]
    for index, (label, value) in enumerate(rows):
        y = index * row_h + 4
        w = 0 if top == 0 else track * (float(value) / top)
        w = max(w, 2) if value else 0
        mid = y + bar_h / 2
        parts.append(
            f'<text x="0" y="{mid + 4:.1f}" class="cat">{esc(label[:22])}</text>'
        )
        if w:
            parts.append(
                f'<rect x="{label_w}" y="{y:.1f}" width="{w:.1f}" height="{bar_h:.1f}" '
                f'rx="{min(RADIUS, bar_h / 2):.1f}" fill="{BLUE}">'
                f"<title>{esc(label)}: {esc(_fmt(value))}</title></rect>"
            )
            if w > RADIUS:
                # Square off the baseline end.
                parts.append(
                    f'<rect x="{label_w}" y="{y:.1f}" width="{min(w, RADIUS):.1f}" '
                    f'height="{bar_h:.1f}" fill="{BLUE}"/>'
                )
        # Value at the tip, always outside the bar so it can never be clipped.
        parts.append(
            f'<text x="{label_w + w + 8:.1f}" y="{mid + 4:.1f}" '
            f'class="val">{esc(_fmt(value))}</text>'
        )
    parts.append("</svg>")
    return _frame(
        title,
        "".join(parts),
        table_view(["Category", "Count"], [(r, _fmt(v)) for r, v in rows]),
    )


def line_chart(
    points: Sequence[tuple[str, float]],
    *,
    title: str = "",
    width: int = CHART_W,
    height: int = 168,
) -> str:
    """A single series over time: 2px line, 10% wash, one labelled end point."""
    if len(points) < 2:
        return _frame(title, '<p class="empty">Not enough history yet.</p>')

    pad_l, pad_r, pad_t, pad_b = 44, 44, 14, 26
    plot_w = width - pad_l - pad_r
    plot_h = height - pad_t - pad_b
    top = _nice_max(max(v for _, v in points))
    step = plot_w / (len(points) - 1)

    coords = [
        (pad_l + step * i, pad_t + plot_h - (plot_h * (float(v) / top) if top else 0))
        for i, (_, v) in enumerate(points)
    ]

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{esc(title)}" class="plot">'
    ]
    for tick in range(3):
        value = top * tick / 2
        y = pad_t + plot_h - (plot_h * tick / 2)
        parts.append(
            f'<line x1="{pad_l}" y1="{y:.1f}" x2="{width - pad_r}" y2="{y:.1f}" '
            f'stroke="{GRID}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{pad_l - 8}" y="{y + 3.5:.1f}" text-anchor="end" '
            f'class="tick">{esc(_fmt(value))}</text>'
        )

    area = (
        f"M {coords[0][0]:.1f} {pad_t + plot_h:.1f} "
        + " ".join(f"L {x:.1f} {y:.1f}" for x, y in coords)
        + f" L {coords[-1][0]:.1f} {pad_t + plot_h:.1f} Z"
    )
    parts.append(f'<path d="{area}" fill="{BLUE}" fill-opacity="0.1"/>')
    line = "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in coords)
    parts.append(
        f'<path d="{line}" fill="none" stroke="{BLUE}" stroke-width="2" '
        'stroke-linecap="round" stroke-linejoin="round"/>'
    )

    # Hit targets over each point, larger than the mark itself.
    for (x, y), (label, value) in zip(coords, points):
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="12" fill="transparent">'
            f"<title>{esc(label)}: {esc(_fmt(value))}</title></circle>"
        )

    end_x, end_y = coords[-1]
    parts.append(
        f'<circle cx="{end_x:.1f}" cy="{end_y:.1f}" r="4.5" fill="{BLUE}" '
        f'stroke="{SURFACE}" stroke-width="2"/>'
    )
    parts.append(
        f'<text x="{end_x + 10:.1f}" y="{end_y + 4:.1f}" '
        f'class="val">{esc(_fmt(points[-1][1]))}</text>'
    )
    for index in (0, len(points) - 1):
        x = coords[index][0]
        anchor = "start" if index == 0 else "end"
        parts.append(
            f'<text x="{x:.1f}" y="{height - 8}" text-anchor="{anchor}" '
            f'class="tick">{esc(points[index][0])}</text>'
        )
    parts.append("</svg>")
    return _frame(
        title,
        "".join(parts),
        table_view(["Date", "Count"], [(d, _fmt(v)) for d, v in points]),
    )


def split_bar(
    left_label: str,
    left: float,
    right_label: str,
    right: float,
    *,
    title: str = "",
    width: int = CHART_W,
) -> str:
    """Part-to-whole across two states, with a legend because there are two.

    The second slot is the status hue on purpose: the right-hand share is a
    thing wanting attention, not merely another category.
    """
    total = float(left) + float(right)
    if total <= 0:
        return _frame(title, '<p class="empty">Nothing to plot yet.</p>')

    height, bar_h = 54, 22
    left_w = (width * float(left) / total) if total else 0
    right_w = width - left_w - (GAP if left_w and left_w < width else 0)

    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="{esc(title)}" class="plot">'
    ]
    if left_w > 0:
        parts.append(
            f'<rect x="0" y="0" width="{max(left_w, 2):.1f}" height="{bar_h}" '
            f'rx="2" fill="{BLUE}">'
            f"<title>{esc(left_label)}: {esc(_fmt(left))}</title></rect>"
        )
    if right_w > 0 and right:
        parts.append(
            f'<rect x="{left_w + GAP:.1f}" y="0" width="{max(right_w, 2):.1f}" '
            f'height="{bar_h}" rx="2" fill="{RED}">'
            f"<title>{esc(right_label)}: {esc(_fmt(right))}</title></rect>"
        )
    # Legend: a swatch beside text, the text itself in ink.
    parts.append(f'<rect x="0" y="{bar_h + 16}" width="9" height="9" rx="2" fill="{BLUE}"/>')
    parts.append(
        f'<text x="15" y="{bar_h + 25}" class="cat">'
        f"{esc(left_label)} {esc(_fmt(left))}</text>"
    )
    offset = 168
    parts.append(
        f'<rect x="{offset}" y="{bar_h + 16}" width="9" height="9" rx="2" fill="{RED}"/>'
    )
    parts.append(
        f'<text x="{offset + 15}" y="{bar_h + 25}" class="cat">'
        f"{esc(right_label)} {esc(_fmt(right))}</text>"
    )
    parts.append("</svg>")
    return _frame(
        title,
        "".join(parts),
        table_view(["State", "Count"], [(left_label, _fmt(left)), (right_label, _fmt(right))]),
    )
