"""Markdown -> print-ready HTML -> PDF.

A tiny markdown subset renderer (headings, emphasis, lists, links, rules) keeps
the dependency list at exactly one package. The HTML carries print CSS sized for
a one-page US Letter resume, so "print to PDF" from any browser produces a clean
document. If weasyprint or wkhtmltopdf happens to be installed, PDF generation
is done directly instead.
"""

from __future__ import annotations

import html
import re
import shutil
import subprocess
from pathlib import Path

INLINE_CODE_RE = re.compile(r"`([^`]+)`")
BOLD_RE = re.compile(r"\*\*([^*]+)\*\*")
ITALIC_RE = re.compile(r"(?<!\*)\*([^*\n]+)\*(?!\*)")
LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")
BARE_URL_RE = re.compile(r"(?<!\()(?<!href=\")(https?://[^\s<>\"]+)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
UL_RE = re.compile(r"^\s*[-*+]\s+(.*)$")
OL_RE = re.compile(r"^\s*\d+[.)]\s+(.*)$")
HR_RE = re.compile(r"^\s*(?:-{3,}|\*{3,}|_{3,})\s*$")

PRINT_CSS = """
:root { color-scheme: light; }
@page { size: Letter; margin: 0.5in; }
* { box-sizing: border-box; }
body {
  font-family: "Source Sans Pro", Calibri, "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 10.5pt;
  line-height: 1.35;
  color: #16191d;
  background: #fff;
  margin: 0 auto;
  padding: 0.5in;
  max-width: 8.5in;
}
h1 { font-size: 19pt; margin: 0 0 2pt; letter-spacing: -0.01em; }
h2 {
  font-size: 11pt;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  margin: 13pt 0 4pt;
  padding-bottom: 2pt;
  border-bottom: 0.75pt solid #b9c0c8;
}
h3 { font-size: 10.5pt; margin: 8pt 0 1pt; }
h4 { font-size: 10pt; margin: 6pt 0 1pt; font-weight: 600; color: #3d444d; }
p { margin: 0 0 5pt; }
ul, ol { margin: 0 0 6pt; padding-left: 16pt; }
li { margin: 0 0 2.5pt; }
a { color: #1a4f8a; text-decoration: none; }
hr { border: 0; border-top: 0.75pt solid #d3d8de; margin: 9pt 0; }
code { font-family: Consolas, "Courier New", monospace; font-size: 9.5pt; background: #f2f4f6; padding: 0 2px; }
strong { font-weight: 650; }
.contact { color: #3d444d; font-size: 9.5pt; margin-bottom: 8pt; }
h1 + p { color: #3d444d; font-size: 9.5pt; margin-bottom: 9pt; }
@media print {
  body { padding: 0; max-width: none; }
  a { color: inherit; }
}
"""


def _inline(text: str) -> str:
    out = html.escape(text, quote=False)
    out = INLINE_CODE_RE.sub(r"<code>\1</code>", out)
    out = BOLD_RE.sub(r"<strong>\1</strong>", out)
    out = ITALIC_RE.sub(r"<em>\1</em>", out)
    out = LINK_RE.sub(r'<a href="\2">\1</a>', out)
    out = BARE_URL_RE.sub(r'<a href="\1">\1</a>', out)
    return out


def markdown_to_html_body(markdown: str) -> str:
    lines = markdown.replace("\r\n", "\n").split("\n")
    parts: list[str] = []
    list_stack: list[str] = []
    paragraph: list[str] = []

    def flush_paragraph() -> None:
        if paragraph:
            parts.append(f"<p>{'<br>'.join(_inline(l) for l in paragraph)}</p>")
            paragraph.clear()

    def close_lists() -> None:
        while list_stack:
            parts.append(f"</{list_stack.pop()}>")

    for line in lines:
        if not line.strip():
            flush_paragraph()
            close_lists()
            continue

        if HR_RE.match(line):
            flush_paragraph()
            close_lists()
            parts.append("<hr>")
            continue

        heading = HEADING_RE.match(line)
        if heading:
            flush_paragraph()
            close_lists()
            level = len(heading.group(1))
            parts.append(f"<h{level}>{_inline(heading.group(2).strip())}</h{level}>")
            continue

        unordered = UL_RE.match(line)
        if unordered:
            flush_paragraph()
            if list_stack and list_stack[-1] != "ul":
                parts.append(f"</{list_stack.pop()}>")
            if not list_stack:
                list_stack.append("ul")
                parts.append("<ul>")
            parts.append(f"<li>{_inline(unordered.group(1).strip())}</li>")
            continue

        ordered = OL_RE.match(line)
        if ordered:
            flush_paragraph()
            if list_stack and list_stack[-1] != "ol":
                parts.append(f"</{list_stack.pop()}>")
            if not list_stack:
                list_stack.append("ol")
                parts.append("<ol>")
            parts.append(f"<li>{_inline(ordered.group(1).strip())}</li>")
            continue

        close_lists()
        paragraph.append(line.strip())

    flush_paragraph()
    close_lists()
    return "\n".join(parts)


def markdown_to_html(markdown: str, title: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>{html.escape(title)}</title>\n<style>{PRINT_CSS}</style>\n"
        "</head>\n<body>\n"
        f"{markdown_to_html_body(markdown)}\n"
        "</body>\n</html>\n"
    )


def write_html(markdown_path: Path, title: str | None = None) -> Path:
    markdown = markdown_path.read_text(encoding="utf-8")
    html_path = markdown_path.with_suffix(".html")
    html_path.write_text(
        markdown_to_html(markdown, title or markdown_path.stem.replace("_", " ").title()),
        encoding="utf-8",
    )
    return html_path


def _playwright_pdf(html_path: Path, pdf_path: Path) -> tuple[Path | None, str]:
    """If Playwright is installed for ATS submission, it can also print the PDF."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return None, ""
    try:
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(html_path.resolve().as_uri(), wait_until="load")
            page.pdf(
                path=str(pdf_path),
                format="Letter",
                print_background=True,
                margin={"top": "0.5in", "bottom": "0.5in", "left": "0.5in", "right": "0.5in"},
            )
            browser.close()
        return pdf_path, "rendered with playwright/chromium"
    except Exception as exc:
        return None, f"playwright failed: {exc}"


def write_pdf(html_path: Path) -> tuple[Path | None, str]:
    """Best-effort PDF. Returns (path, message); path is None if no engine is available."""
    pdf_path = html_path.with_suffix(".pdf")

    result, message = _playwright_pdf(html_path, pdf_path)
    if result:
        return result, message
    if message:
        return None, message

    try:
        from weasyprint import HTML  # type: ignore

        HTML(filename=str(html_path)).write_pdf(str(pdf_path))
        return pdf_path, "rendered with weasyprint"
    except ImportError:
        pass
    except Exception as exc:  # engine present but unhappy
        return None, f"weasyprint failed: {exc}"

    wkhtmltopdf = shutil.which("wkhtmltopdf")
    if wkhtmltopdf:
        try:
            subprocess.run(
                [wkhtmltopdf, "--quiet", "--page-size", "Letter", str(html_path), str(pdf_path)],
                check=True,
                capture_output=True,
            )
            return pdf_path, "rendered with wkhtmltopdf"
        except subprocess.CalledProcessError as exc:
            return None, f"wkhtmltopdf failed: {exc.stderr.decode(errors='replace')[:200]}"

    return None, (
        "no PDF engine found -- open the .html file in a browser and print to PDF "
        "(or install one: pip install playwright && playwright install chromium)"
    )
