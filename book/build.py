#!/usr/bin/env python3
"""
Build "Mastering Apache Spark" from Markdown sources.

Pipeline
--------
    book/src/*.md  ──►  book/Mastering-Apache-Spark.md   (single print-ready file)
                   └─►  book/index.html                  (self-contained web book)

Usage
-----
    python book/build.py

Adding a chapter
----------------
    Drop a file into book/src/ named so that it sorts in the right place, e.g.
        03-project-01-retail-etl.md
    then re-run this script. No configuration to edit.

Dependencies: markdown>=3.6, pygments (pip install markdown pygments)
"""

from __future__ import annotations

import html as html_lib
import re
import sys
from datetime import datetime
from pathlib import Path

try:
    import markdown
    from pygments.formatters import HtmlFormatter
except ImportError:  # pragma: no cover - environment guard
    sys.exit(
        "Missing build dependencies.\n"
        "Install them with:\n"
        "    python -m pip install 'markdown>=3.6' pygments\n"
    )

# --------------------------------------------------------------------------- #
# Metadata
# --------------------------------------------------------------------------- #

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BOOK_DIR = Path(__file__).resolve().parent
SRC_DIR = BOOK_DIR / "src"
ASSETS_DIR = BOOK_DIR / "assets"

OUT_MD = BOOK_DIR / "Mastering-Apache-Spark.md"
OUT_HTML = BOOK_DIR / "index.html"

TITLE = "Mastering Apache Spark"
SUBTITLE = "20 Real-World Data Engineering Projects in Python & Java"
EDITION = "Apache Spark 3.5.x · Java 17 · Python 3.10+ · First Edition"
DESCRIPTION = (
    "A build-it book: twenty production-grade Apache Spark projects implemented twice, "
    "in PySpark and in the Java API, with internals deep-dives and tuning guidance."
)

MD_EXTENSIONS = [
    "tables",
    "fenced_code",
    "attr_list",
    "def_list",
    "footnotes",
    "md_in_html",
    "toc",
    "sane_lists",
    "admonition",
    "codehilite",
]

MD_CONFIG = {
    "toc": {
        "toc_depth": "1-3",
        "permalink": False,
        "anchorlink": False,
        "title": "",
    },
    "codehilite": {
        "css_class": "highlight",
        "guess_lang": False,
        "linenums": False,
        "wrapcode": True,
        "use_pygments": True,
    },
}

CHAPTER_SEPARATOR_HTML = '<div class="chapter-break"></div>'
CHAPTER_SEPARATOR_MD = "\n\n---\n\n"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def fail(message: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"BUILD FAILED: {message}", file=sys.stderr)
    raise SystemExit(1)


def read_sources() -> list[tuple[str, str]]:
    """Return (filename, text) pairs in build order."""
    if not SRC_DIR.is_dir():
        fail(f"source directory not found: {SRC_DIR}")

    files = sorted(p for p in SRC_DIR.glob("*.md") if not p.name.startswith("_"))
    if not files:
        fail(f"no markdown sources in {SRC_DIR}")

    sources: list[tuple[str, str]] = []
    for path in files:
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            fail(f"source file is empty: {path.name}")
        sources.append((path.name, text))
    return sources


def render_nav(tokens: list[dict]) -> str:
    """Sidebar: nested <ul> built from the TOC token tree."""
    if not tokens:
        return ""

    parts = ['<ul class="nav-list">']
    for token in tokens:
        parts.append(f'<li class="lvl-{token["level"]}">')
        parts.append(f'<a href="#{token["id"]}">{token["name"]}</a>')
        parts.append(render_nav(token.get("children") or []))
        parts.append("</li>")
    parts.append("</ul>")
    return "".join(parts)


def render_inline_toc(tokens: list[dict]) -> str:
    """In-page contents list, used for reading and for print output."""
    if not tokens:
        return ""

    parts = ["<ol>"]
    for token in tokens:
        parts.append("<li>")
        parts.append(f'<a href="#{token["id"]}">{token["name"]}</a>')
        parts.append(render_inline_toc(token.get("children") or []))
        parts.append("</li>")
    parts.append("</ol>")
    return "".join(parts)


def render_md_outline(tokens: list[dict], depth: int = 0) -> str:
    """Plain bullet outline for the Markdown edition (no fragile anchors)."""
    lines: list[str] = []
    for token in tokens:
        label = re.sub(r"\s+", " ", html_lib.unescape(str(token["name"]))).strip()
        lines.append(f"{'  ' * depth}- {label}")
        lines.append(render_md_outline(token.get("children") or [], depth + 1))
    return "\n".join(line for line in lines if line)


def strip_trailing_blank_lines(text: str) -> str:
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


# --------------------------------------------------------------------------- #
# Build
# --------------------------------------------------------------------------- #


def build() -> None:
    sources = read_sources()

    cover_name, cover_md = sources[0]
    chapter_sources = sources[1:]

    # ---- render cover ----------------------------------------------------- #
    cover_renderer = markdown.Markdown(
        extensions=["tables", "attr_list", "md_in_html", "fenced_code", "codehilite"],
        extension_configs={"codehilite": MD_CONFIG["codehilite"]},
        output_format="html5",
    )
    cover_html = cover_renderer.convert(cover_md)

    # ---- render body ------------------------------------------------------ #
    body_md = f"\n\n{CHAPTER_SEPARATOR_HTML}\n\n".join(text for _, text in chapter_sources)

    body_renderer = markdown.Markdown(
        extensions=MD_EXTENSIONS,
        extension_configs=MD_CONFIG,
        output_format="html5",
    )
    body_html = body_renderer.convert(body_md)
    toc_tokens = body_renderer.toc_tokens

    nav_html = render_nav(toc_tokens)
    inline_toc_html = render_inline_toc(toc_tokens)

    # ---- markdown edition ------------------------------------------------- #
    outline = render_md_outline(toc_tokens)
    md_body = f"\n\n{CHAPTER_SEPARATOR_MD}\n\n".join(text for _, text in chapter_sources)

    markdown_edition = (
        "<!--\n"
        f"  {TITLE}\n"
        f"  {SUBTITLE}\n"
        f"  {EDITION}\n\n"
        "  Generated by book/build.py. Edit files in book/src/ and rebuild.\n"
        "-->\n\n"
        f"{cover_md}\n\n"
        "---\n\n"
        f"## Contents\n\n{outline}\n\n"
        "---\n\n"
        f"{md_body}\n"
    )
    markdown_edition = strip_trailing_blank_lines(markdown_edition)
    OUT_MD.write_text(markdown_edition, encoding="utf-8")

    # ---- html edition ----------------------------------------------------- #
    base_css = (ASSETS_DIR / "book.css").read_text(encoding="utf-8")
    book_js = (ASSETS_DIR / "book.js").read_text(encoding="utf-8")
    pygments_css = HtmlFormatter(style="friendly").get_style_defs(".highlight")

    built = datetime.now().strftime("%d %B %Y")
    html = (
        TEMPLATE.replace("{{TITLE}}", TITLE)
        .replace("{{SUBTITLE}}", html_lib.escape(SUBTITLE))
        .replace("{{EDITION}}", html_lib.escape(EDITION))
        .replace("{{DESCRIPTION}}", DESCRIPTION)
        .replace("{{PYGMENTS_CSS}}", pygments_css)
        .replace("{{BASE_CSS}}", base_css)
        .replace("{{BOOK_JS}}", book_js)
        .replace("{{NAV}}", nav_html)
        .replace("{{INLINE_TOC}}", inline_toc_html)
        .replace("{{COVER}}", cover_html)
        .replace("{{CONTENT}}", body_html)
        .replace("{{BUILT}}", built)
        .replace("{{CHAPTER_COUNT}}", str(len(sources)))
    )
    OUT_HTML.write_text(html, encoding="utf-8")

    # ---- report ----------------------------------------------------------- #
    md_kb = OUT_MD.stat().st_size / 1024
    html_kb = OUT_HTML.stat().st_size / 1024
    print(f"{TITLE} — {SUBTITLE}")
    print(f"  sources   : {len(sources)} file(s) in {SRC_DIR.name}/")
    for name, text in sources:
        words = len(text.split())
        print(f"    - {name:<42} {words:>6,} words")
    print(f"  headings  : {_count_tokens(toc_tokens)} in navigation")
    print(f"  markdown  : {OUT_MD.name:<42} {md_kb:>7.1f} KB")
    print(f"  html      : {OUT_HTML.name:<42} {html_kb:>7.1f} KB  (self-contained)")
    print("  status    : OK")


def _count_tokens(tokens: list[dict]) -> int:
    return sum(1 + _count_tokens(token.get("children") or []) for token in tokens)


# --------------------------------------------------------------------------- #
# HTML shell
# --------------------------------------------------------------------------- #

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}} — {{SUBTITLE}}</title>
<meta name="description" content="{{DESCRIPTION}}">
<meta name="author" content="Mastering Apache Spark">
<meta name="generator" content="book/build.py">
<style>
/* pygments token colours */
{{PYGMENTS_CSS}}
</style>
<style>
{{BASE_CSS}}
</style>
</head>
<body>

<div class="progress" id="progress"></div>

<header class="topbar">
  <button class="nav-toggle" id="navToggle" type="button" aria-label="Toggle navigation">&#9776;</button>
  <a class="brand" href="#top">{{TITLE}}</a>
  <span class="brand-sub">{{EDITION}}</span>
  <span class="spacer"></span>
  <button class="print-btn" type="button" onclick="window.print()">Print / PDF</button>
</header>

<div class="layout">

  <aside class="sidebar" id="sidebar">
    <nav class="nav" aria-label="Table of contents">
      <ul class="nav-list nav-list-root">
        <li class="lvl-1"><a href="#top">Cover &amp; Introduction</a></li>
        <li class="lvl-1"><a href="#contents">Contents</a></li>
      </ul>
      {{NAV}}
    </nav>
    <div class="sidebar-foot">
      <strong>{{CHAPTER_COUNT}} source file(s)</strong><br>
      Built {{BUILT}}
    </div>
  </aside>

  <main class="main" id="top">

    <header class="book-cover">
      {{COVER}}
    </header>

    <section class="toc-inline" id="contents">
      <h2>Contents</h2>
      {{INLINE_TOC}}
    </section>

    <article class="content">
      {{CONTENT}}
    </article>

    <footer class="book-footer">
      <p><strong>{{TITLE}}</strong> — {{SUBTITLE}}<br>
      {{EDITION}}</p>
      <p>Every listing in this book is complete and runnable. Verify your environment with the
      two smoke tests in the Environment Setup chapter before starting Project 1.</p>
    </footer>

  </main>

</div>

<script>
{{BOOK_JS}}
</script>
</body>
</html>
"""


if __name__ == "__main__":
    build()
