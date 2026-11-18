# Mastering Apache Spark — book project

Source of truth for the book, plus a zero-config build that produces both editions.

## Layout

```text
book/
├── build.py                     # assembles src/*.md -> .md + .html
├── src/                         # Markdown sources, built in filename order
│   ├── 00-cover.md              # title page + introduction
│   ├── 01-environment-setup.md  # toolchain, smoke tests, troubleshooting
│   └── 02-syllabus.md           # 20-project master syllabus
├── assets/
│   ├── book.css                 # print-ready typography (no external fonts/CDN)
│   └── book.js                  # nav, scroll spy, copy buttons, progress bar
├── Mastering-Apache-Spark.md    # GENERATED — single-file Markdown edition
└── index.html                   # GENERATED — self-contained web edition
```

## Build

```powershell
python -m pip install "markdown>=3.6" pygments
python book/build.py
```

Output:

| File | Use |
|---|---|
| `book/Mastering-Apache-Spark.md` | Portable Markdown; renders on GitHub, in VS Code, Pandoc, Obsidian |
| `book/index.html` | Open directly in a browser — no server, no CDN, works from `file://` |

`index.html` inlines the CSS, the JS and the Pygments token styles, so it is a single
distributable artefact. `Print / PDF` in the top bar produces a paginated PDF with a
page break at every chapter.

## Adding a chapter

Chapters are discovered by filename sort order. Nothing else to edit.

```text
src/03-project-01-retail-etl.md
src/04-project-02-customer-360.md
...
```

Rules enforced by the build:

- every file must be non-empty;
- files starting with `_` are ignored (good for drafts);
- the first file is treated as the cover/front matter;
- headings `h1`–`h3` become the sidebar, the in-page contents and the Markdown outline;
- fenced code blocks are syntax-highlighted; declare the language (`python`, `java`, `xml`,
  `properties`, `bash`, `powershell`, `json`, `sql`, `yaml`, `text`).

## Chapter numbering

```text
00-cover.md                  front matter
01-environment-setup.md      setup
02-syllabus.md               syllabus
03-project-01-*.md           Project 1
04-project-02-*.md           Project 2
...
22-project-20-*.md           Project 20
```

## Design notes

- **No network dependencies.** Fonts fall back to the OS stack; there is no CDN, no
  analytics, no external stylesheet. The book works offline and archives cleanly.
- **Print-first.** `@page` margins, `break-inside: avoid` on code blocks, tables and
  callouts, `break-before: page` per chapter.
- **One source, two artefacts.** The Markdown edition carries a plain bullet outline
  rather than anchor links, because GitHub, VS Code and Pandoc slugify headings
  differently from Python-Markdown.
