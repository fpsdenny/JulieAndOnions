#!/usr/bin/env python3
"""Julie and Onions — site helper.

    python tools/site.py serve            preview at http://localhost:8000
    python tools/site.py check            dead links, leftover [brackets], orphans
    python tools/site.py sync             push the nav and footer into every page
    python tools/site.py new <room> "Title" [source.md]

Only the standard library. The HTML files stay the real thing — nothing here is a
build step, and the site works if you never run any of it.
"""
import os, re, sys, html as _html, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---- the one place the nav and footer are defined ---------------------------

NAV = [("Home", "/index.html"), ("Writing", "/writing.html"), ("Photography", "/photography.html"),
       ("Workshop", "/workshop.html"), ("Kitchen", "/kitchen.html"), ("About", "/about.html")]

FOOTER = ('Julie and Onions · planted 2026 · contact — '
          '<a href="mailto:hayden@julieandonions.com">hayden@julieandonions.com</a>')

# which nav item lights up for a given file
ROOM_OF = {"writing": "/writing.html", "workshop": "/workshop.html", "photography": "/photography.html"}
SELF = {"essays.html": "/writing.html", "poems.html": "/writing.html"}

ROOMS = {
    "writing":  dict(dir="writing",  listings=["essays.html", "writing.html"],
                     eyebrow="Julie and Onions · Writing", back=("/essays.html", "Back to the essays"),
                     more="Read the essay →"),
    "workshop": dict(dir="workshop", listings=["workshop.html"],
                     eyebrow="Julie and Onions · Workshop", back=("/workshop.html", "Back to the workshop"),
                     more="Read more →"),
}


def pages():
    for base, _, files in os.walk(ROOT):
        if os.path.basename(base) in ("tools", ".git", "images"):
            continue
        for f in sorted(files):
            if f.endswith(".html"):
                yield os.path.join(base, f)


def rel(path):
    return "/" + os.path.relpath(path, ROOT).replace(os.sep, "/")


# ---- sync -------------------------------------------------------------------

def active_for(path):
    r = rel(path)
    if r in SELF:
        return SELF[r]
    if r.lstrip("/") in SELF:
        return SELF[r.lstrip("/")]
    parts = r.strip("/").split("/")
    if len(parts) > 1 and parts[0] in ROOM_OF:
        return ROOM_OF[parts[0]]
    return r


def sync():
    changed = []
    for path in pages():
        src = open(path, encoding="utf-8").read()
        if 'class="site-nav"' not in src:
            continue                                  # redirect stubs have no nav
        active = active_for(path)
        links = "".join(
            '\n          <a href="%s"%s>%s</a>' % (href, ' class="active"' if href == active else "", label)
            for label, href in NAV)
        nav = '<nav class="site-nav" aria-label="Primary">%s\n        </nav>' % links
        out = re.sub(r'<nav class="site-nav".*?</nav>', lambda m: nav, src, flags=re.S)
        out = re.sub(r'(<footer class="site-footer">).*?(</footer>)',
                     lambda m: m.group(1) + FOOTER + m.group(2), out, flags=re.S)
        if out != src:
            open(path, "w", encoding="utf-8").write(out)
            changed.append(rel(path))
    print("synced nav + footer · %d file(s) changed" % len(changed))
    for c in changed:
        print("  ", c)


# ---- check ------------------------------------------------------------------

# credential shapes worth catching before they reach a public commit
SECRET_PATTERNS = [
    (r'(?i)\b(api[_-]?key|access[_-]?token|client[_-]?secret|passwd|password)\b\s*[:=]', "credential assignment"),
    (r'-----BEGIN [A-Z ]*PRIVATE KEY-----', "private key"),
    (r'\bpostgres(?:ql)?://\S+', "database URL"),
    (r'https?://[a-z0-9]+\.supabase\.co', "Supabase project URL"),
    (r'\bsk-[A-Za-z0-9]{20,}', "API secret key"),
    (r'\bgh[pousr]_[A-Za-z0-9]{20,}', "GitHub token"),
    (r'\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{15,}', "JWT"),
]


def scan_secrets():
    """Walk every tracked-ish file and flag anything credential-shaped."""
    hits = 0
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in (".git", "node_modules", "__pycache__", "_site")]
        for f in files:
            path = os.path.join(base, f)
            if f == os.path.basename(__file__):
                continue                      # this file lists the patterns themselves
            try:
                src = open(path, encoding="utf-8", errors="ignore").read()
            except OSError:
                continue
            for pattern, label in SECRET_PATTERNS:
                m = re.search(pattern, src)
                if m:
                    print("SECRET %s : looks like a %s — %s"
                          % (rel(path), label, m.group(0)[:40])); hits += 1
    return hits


def check():
    problems = scan_secrets()
    targets, linked, stubs = {}, set(), set()
    for path in pages():
        targets[rel(path)] = path
        if 'http-equiv="refresh"' in open(path, encoding="utf-8").read():
            stubs.add(rel(path))          # deliberate redirect for an old URL
    for path in pages():
        src = open(path, encoding="utf-8").read()
        for m in re.finditer(r'(?:href|src)="(/[^"]+)"', src):
            t = m.group(1)
            linked.add(t)
            if t.endswith((".html", ".css", ".svg", ".png", ".jpg")):
                if not os.path.exists(os.path.join(ROOT, t.lstrip("/"))):
                    print("DEAD  %s -> %s" % (rel(path), t)); problems += 1
        for m in re.finditer(r'\[[A-Za-z][^\]\n]{2,70}\]', re.sub(r'<!--.*?-->', '', src, flags=re.S)):
            print("TODO  %s : %s" % (rel(path), m.group(0))); problems += 1
        if 'name="robots" content="noindex"' in src:
            print("NOIX  %s is noindexed" % rel(path))
    for t, path in targets.items():
        if t not in linked and t not in stubs and os.path.basename(t) != "index.html":
            print("ORPH  %s is not linked from anywhere" % t); problems += 1
    print("\n%d page(s) checked · %d thing(s) to look at" % (len(targets), problems))
    return problems


# ---- new entry --------------------------------------------------------------

def md_to_html(text):
    out, para = [], []

    def flush():
        if para:
            out.append("<p>%s</p>" % " ".join(para).strip())
            para.clear()

    quote, cite = [], None
    for raw in text.splitlines():
        line = raw.rstrip()
        if line.startswith(">"):
            body = line[1:].strip()
            if body.startswith("—") or body.startswith("--"):
                cite = body.lstrip("—- ").strip()
            elif body:
                quote.append(body)
            continue
        if quote:
            flush()
            q = "".join("<p>%s</p>" % q for q in quote)
            out.append("<blockquote>%s%s</blockquote>" % (q, "<cite>%s</cite>" % cite if cite else ""))
            quote, cite = [], None
        if not line.strip():
            flush(); continue
        if line.startswith("## "):
            flush(); out.append("<h2>%s</h2>" % line[3:].strip()); continue
        if line.strip() in ("---", "***"):
            flush(); out.append("<hr>"); continue
        para.append(line.strip())
    flush()
    if quote:
        q = "".join("<p>%s</p>" % x for x in quote)
        out.append("<blockquote>%s%s</blockquote>" % (q, "<cite>%s</cite>" % cite if cite else ""))
    body = "\n".join(out)
    body = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', body)
    body = re.sub(r'(?<!\*)\*([^*\n]+)\*(?!\*)', r'<em>\1</em>', body)
    return body


def slugify(title):
    s = re.sub(r'[^a-z0-9]+', '-', title.lower()).strip('-')
    return re.sub(r'-{2,}', '-', s)[:60]


def new_entry(room, title, source=None):
    if room not in ROOMS:
        sys.exit("unknown room %r — one of: %s" % (room, ", ".join(ROOMS)))
    cfg = ROOMS[room]
    slug = slugify(title)
    path = os.path.join(ROOT, cfg["dir"], slug + ".html")
    if os.path.exists(path):
        sys.exit("%s already exists" % rel(path))

    body = md_to_html(open(source, encoding="utf-8").read()) if source else \
        "<p>[Write it here. Blank lines separate paragraphs; '## ' makes a subheading; " \
        "lines starting with '&gt;' make a pull-quote, and a '— Name' line inside one becomes the citation.]</p>"
    meta = "[date or tag line]"
    first = re.search(r'<p>(.*?)</p>', re.sub(r'<blockquote.*?</blockquote>', '', body, flags=re.S), re.S)
    summary = re.sub(r'<[^>]+>', '', first.group(1))[:260] if first else "[Two or three sentences.]"

    shell = open(os.path.join(ROOT, "kitchen.html"), encoding="utf-8").read()
    head = shell[:shell.index("<main")]
    head = head.replace("<title>Kitchen • Julie and Onions</title>",
                        "<title>%s • Julie and Onions</title>" % _html.escape(title))
    head = re.sub(r'<meta name="description"[^>]*>',
                  '<meta name="description" content="Julie and Onions — %s.">' % _html.escape(title), head)
    page = (head +
            '<main class="page-main">\n'
            '        <section class="page-hero">\n'
            '          <span class="page-eyebrow">%s</span>\n'
            '          <h1 class="page-title">%s</h1>\n'
            '          <p class="page-description">%s</p>\n'
            '        </section>\n'
            '        <div class="entry-body">\n%s\n        </div>\n'
            '        <p class="quiet-door"><a href="%s">%s</a>.</p>\n'
            '      </main>\n'
            '      <footer class="site-footer">%s</footer>\n'
            '    </div>\n  </body>\n</html>\n'
            % (cfg["eyebrow"], _html.escape(title), meta,
               "\n".join("          " + l for l in body.splitlines()),
               cfg["back"][0], cfg["back"][1], FOOTER))
    open(path, "w", encoding="utf-8").write(page)

    card = ('<a class="entry-card" href="%s">\n'
            '            <h2>%s</h2>\n'
            '            <p class="entry-meta">%s</p>\n'
            '            <p class="entry-summary">%s</p>\n'
            '            <span class="entry-more">%s</span>\n'
            '          </a>' % (rel(path), _html.escape(title), meta, _html.escape(summary), cfg["more"]))
    for listing in cfg["listings"]:
        lp = os.path.join(ROOT, listing)
        if not os.path.exists(lp):
            continue
        s = open(lp, encoding="utf-8").read()
        anchor = '<div class="entry-list">'
        i = s.index(anchor) + len(anchor)
        open(lp, "w", encoding="utf-8").write(s[:i] + "\n          " + card + s[i:])
        print("carded in  %s" % listing)
    print("created    %s" % rel(path))
    print("\nfill in the [date or tag line] and check the summary, then: python tools/site.py check")


def serve():
    os.chdir(ROOT)
    print("serving %s at http://localhost:8000  (ctrl-c to stop)" % ROOT)
    subprocess.call([sys.executable, "-m", "http.server", "8000"])


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "sync":   sync()
    elif cmd == "check": sys.exit(1 if check() else 0)
    elif cmd == "serve": serve()
    elif cmd == "new":   new_entry(sys.argv[2], sys.argv[3], sys.argv[4] if len(sys.argv) > 4 else None)
    else: print(__doc__)
