# Julie and Onions

The site at [julieandonions.com](https://www.julieandonions.com). Hand-built:
static HTML, one stylesheet, no build step. What you edit is what gets served.

## Layout

    index.html            the landing
    writing.html          the rooms — each is a summary box plus a list of entries
    research.html
    workshop.html
    kitchen.html
    about.html
    essays.html           sections inside Writing
    poems.html
    journal.html          redirect kept for the old /journal.html URL

    writing/              the entries themselves, one file per piece
    workshop/
    research/

    style.css             the whole design — colours and type live in :root at the top
    images/               the onion photograph and its mask
    tools/                helper scripts (not served as pages)

Links are root-absolute (`/writing/flow.html`), so the same markup works from any
folder and pages can be moved without rewriting their links.

## Working on it

    python tools/site.py serve     preview at http://localhost:8000
    python tools/site.py check     dead links, unfinished [brackets], orphan pages
    python tools/site.py sync      push the nav and footer into every page
    python tools/site.py new writing "Title" [piece.md]
    python tools/photos.py [source-folder]      add photographs

**serve** — always preview through this rather than opening a file directly; the
onion is a CSS mask and browsers refuse to load it over `file://`.

**check** — run before committing. `TODO` means an unfilled `[bracket]`, `DEAD` a
broken link, `ORPH` a page nothing links to, `NOIX` a page hidden from search.

**sync** — the nav and footer are defined once, at the top of `tools/site.py`. Edit
`NAV` or `FOOTER` there, run sync, and every page is updated. Never hand-edit a
nav; it will only be overwritten.

**new** — creates an entry page and its card on the listing pages. Give it a
Markdown file and it converts: blank lines separate paragraphs, `## ` is a
subheading, `> ` lines become a pull-quote, and a `— Name` line inside one becomes
the citation. Then fill in the date line and write the card summary yourself — that
sentence is what earns the click.

## Before pushing

    python tools/site.py check

It also scans for credential-shaped strings — database URLs, private keys, API
tokens, JWTs — and fails on them. This repository is public and serves a live
site, so nothing here should ever hold a secret. `.gitignore` covers the usual
accidents (`.env`, key files, `*.docx`), but the scan is the safety net for
anything pasted into a file by hand.

Two standing rules that no tooling can enforce:

- **Nothing touching ConvexityEngine or FVFA credentials belongs in this repo.**
  Not a config, not a connection string, not a "temporary" test script.
- **The resume source stays out.** It carries a phone number and a home address.
  A PDF scrubbed of both can be published deliberately — that is why `.pdf` is
  not in `.gitignore` while `.docx` is.

Everything in the repo is served, including `tools/`, so `tools/site.py` is
readable at `julieandonions.com/tools/site.py`. It cannot execute — GitHub Pages
serves static files only — and it holds nothing private.

**photos** — reads originals from *outside* the repository (default
`../photo-originals`), writes resized copies into `images/photos/`, and rebuilds
the gallery on `photography.html`. It **strips every scrap of metadata** and verifies
each file afterwards, refusing to continue if anything survives — a decade of
geotagged photographs published together is a map of where you have been, and
anything shot at home carries home's coordinates. Keep the originals out of the
repo; git never forgets a large file.

Captions go in `images/photos/captions.txt`, one line each:

    kananaskis-01.jpg | Kananaskis, Alberta | Late September, going up.

Filename, place, sentence. Re-run the script after editing to rebuild the page.

## House rules

- Entry pages are `<div class="entry-body">`; the room pages are a `.room-grid` of
  a paper `.room-box` and an `.entry-list` of `.entry-card`s.
- On the paper box use `--ink` or `--ink-soft` for text; `--ink-mut` is too faint
  to read at small sizes. On the dark background use `#c9ad8b`, or `--parchment`
  for headings.
- Nothing is minified. Each paragraph is one line so prose stays editable.
