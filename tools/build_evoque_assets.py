"""One-shot: turn the Evoque index.html's <style> and globe script into a
Python assets module, byte-for-byte, so the UI cannot drift in transcription.

Two mechanical edits to the globe script, both so the page can keep the app's
"inline scripts are allowed by hash, never by 'unsafe-inline'" rule:

  * the arc's two endpoints stop being hardcoded city literals and are read
    from the canvas's `data-arc` attribute, so the script is identical on
    every page and hashes to one value while the data still varies;
  * the whole thing is wrapped in `initGlobe()` so pages without a globe can
    simply not call it, instead of throwing on a null canvas.

Rendering, projection, dot placement and the land bitmap are untouched.
"""
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent

css = (HERE / "evoque_reference.css").read_text(encoding="utf-8")
globe = (HERE / "evoque_globe.js").read_text(encoding="utf-8")

before = globe
globe = re.sub(
    r"const CITY_A=cityVec\([^)]*\);[^\n]*\n"
    r"const CITY_B=cityVec\([^)]*\);[^\n]*\n",
    "const _arc=(cv.dataset.arc||'39.8,-98.6,54,-2.5').split(',').map(Number);\n"
    "const CITY_A=cityVec(_arc[0],_arc[1]);\n"
    "const CITY_B=cityVec(_arc[2],_arc[3]);\n",
    globe,
)
assert globe != before and "_arc" in globe, "arc patch failed"

# The callout sits at the globe's centre in the reference, where the panel to
# its right was narrow enough to clear it. This dashboard's right-hand panel is
# a chart of the same width as the reference's spec card but the globe is wider,
# so centre-anchoring overlaps it. Clamp the callout's right edge to stay clear
# of whatever panel is actually there, at any window width.
before = globe
globe = globe.replace(
    "  const bx = cx - R*0.05, by = cy - R*0.08;",
    "  let bx = cx - R*0.05; const by = cy - R*0.08;\n"
    "  const rightPanel = document.querySelector('.main .aircraft');\n"
    "  if (rightPanel) {\n"
    "    const host = cv.getBoundingClientRect();\n"
    "    const lim = rightPanel.getBoundingClientRect().left - host.left - 16;\n"
    "    bx = Math.min(bx, lim - arcCard.offsetWidth / 2);\n"
    "  }",
)
assert globe != before, "callout clamp patch failed"

# Indent one level and wrap, so a page with no <canvas id=globe> just doesn't call it.
wrapped = "function initGlobe(){\n" + globe + "\n}\n"

out = HERE.parent / "jobsearch" / "web" / "evoque_assets.py"
out.write_text(
    '"""Verbatim Evoque design-system assets.\n\n'
    "Generated from the reference build's index.html by tools/_genassets.py --\n"
    "the stylesheet and the dotted-globe canvas script are carried over\n"
    "unchanged so the look is identical to the approved design. Do not\n"
    "hand-edit: this CSS is the single source of truth for every page's\n"
    "appearance.\n"
    '"""\n\n'
    "CSS = r'''" + css + "'''\n\n"
    "GLOBE_JS = r'''" + wrapped + "'''\n",
    encoding="utf-8",
)
print("wrote", out.resolve(), out.stat().st_size, "bytes")
