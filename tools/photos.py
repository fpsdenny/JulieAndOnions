#!/usr/bin/env python3
"""Prepare photographs for the site: resize, strip metadata, write the gallery.

    python tools/photos.py                  process ../photo-originals
    python tools/photos.py "D:/Pictures/Trip"    process any folder
    python tools/photos.py --width 2000     bigger long edge (default 1600)

Originals are read from OUTSIDE the repository and never copied into it. What
lands in images/photos/ is a resized JPEG with **every scrap of metadata
removed** — a decade of geotagged photographs published together is a map of
where you have been, and anything shot at home carries home's coordinates.

Captions live in images/photos/captions.txt, one per line:

    kananaskis-01.jpg | Kananaskis, Alberta | Late September, going up.

Filename, then the place, then a sentence. Missing lines just mean no caption.
Re-run the script after editing captions to rebuild the gallery.
"""
import os, re, sys, html

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "images", "photos")
CAPTIONS = os.path.join(OUT_DIR, "captions.txt")
PAGE = os.path.join(ROOT, "about", "album.html")
DEFAULT_SRC = os.path.join(os.path.dirname(ROOT), "photo-originals")
EXTS = (".jpg", ".jpeg", ".png", ".tif", ".tiff", ".heic", ".webp")

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("This needs Pillow:  pip install Pillow")


def slug(name):
    s = re.sub(r"[^a-z0-9]+", "-", os.path.splitext(name)[0].lower()).strip("-")
    return re.sub(r"-{2,}", "-", s)[:60] or "photo"


def strip_and_resize(src, dst, width):
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)          # honour rotation, then discard EXIF
        im = im.convert("RGB")
        if max(im.size) > width:
            scale = width / max(im.size)
            im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
        clean = Image.frombytes("RGB", im.size, im.tobytes())   # a fresh image carries no metadata
        clean.save(dst, "JPEG", quality=82, optimize=True, progressive=True)
    return os.path.getsize(dst)


def verify_clean(path):
    """Confirm nothing came through — belt and braces, since this one matters."""
    with Image.open(path) as im:
        exif = im.getexif()
        return (len(exif) == 0) and not im.info.get("exif") and not im.info.get("gps")


def read_captions():
    caps = {}
    if os.path.exists(CAPTIONS):
        for line in open(CAPTIONS, encoding="utf-8"):
            if line.strip() and not line.startswith("#"):
                parts = [p.strip() for p in line.split("|")]
                caps[parts[0]] = (parts[1] if len(parts) > 1 else "",
                                  parts[2] if len(parts) > 2 else "")
    return caps


def sync_captions(files):
    """Keep captions.txt in step with the folder, without ever losing your words.

    Every photograph gets a line, in the order it appears in the gallery. Ones
    you have not written yet arrive commented out, so you work down the file
    uncommenting and filling in rather than typing filenames. Lines for
    photographs that are no longer in the folder are moved to the bottom rather
    than deleted, in case the caption is worth keeping for a re-import.
    """
    caps = read_captions()
    lines = ["# One line per photograph:  filename | place | a sentence",
             "#",
             "# Uncomment a line and fill in the two fields to caption that photograph.",
             "# Leave it commented and the alt text falls back to the date in the filename.",
             "# Re-run this script afterwards to write the captions into the page.",
             ""]
    written = 0
    for f in files:
        if f in caps and (caps[f][0] or caps[f][1]):
            lines.append("%s | %s | %s" % (f, caps[f][0], caps[f][1]))
            written += 1
        else:
            lines.append("# %s | place | a sentence" % f)
    orphans = [f for f in caps if f not in files and (caps[f][0] or caps[f][1])]
    if orphans:
        lines += ["", "# --- no longer in the folder, kept in case you want them back ---"]
        lines += ["# %s | %s | %s" % (f, caps[f][0], caps[f][1]) for f in sorted(orphans)]
    open(CAPTIONS, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    return written, len(files) - written


def build_gallery(files, caps):
    """The grid of thumbnails. Each one links to its own lightbox panel below."""
    out = []
    for i, f in enumerate(files):
        place, note = caps.get(f, ("", ""))
        cap = ""
        if place or note:
            cap = ("\n            <figcaption>" +
                   (('<span class="place">%s</span>' % html.escape(place)) if place else "") +
                   html.escape(note) + "</figcaption>")
        alt = html.escape(place or note or describe(f))
        out.append('          <figure>\n'
                   '            <a class="shot" id="s%d" href="#p%d"><img src="/images/photos/%s" '
                   'alt="%s" loading="lazy"></a>%s\n'
                   '          </figure>' % (i, i, f, alt, cap))
    return "\n".join(out)


def build_lightboxes(files, caps):
    """One panel per photograph, hidden until the URL points at it.

    This is the whole viewer: :target does the showing, the arrows are ordinary
    links to the neighbouring ids, and closing jumps back to the thumbnail you
    came from so you land where you left the grid. It works with no JavaScript
    at all; the script at the foot of the page only adds the arrow keys, Escape
    and swipe, which CSS cannot reach.
    """
    out, n = [], len(files)
    for i, f in enumerate(files):
        place, note = caps.get(f, ("", ""))
        alt = html.escape(place or note or describe(f))
        label = ""
        if place or note:
            label = ('\n          <p class="lb-caption">' +
                     (('<span class="place">%s</span>' % html.escape(place)) if place else "") +
                     html.escape(note) + "</p>")
        out.append(
            '        <div class="lightbox" id="p%d" role="dialog" aria-modal="true" aria-label="Photograph %d of %d">\n'
            '          <a class="lb-shade" href="#s%d" aria-label="Close"></a>\n'
            '          <a class="lb-prev" href="#p%d" aria-label="Previous photograph"><span>&#8249;</span></a>\n'
            '          <img src="/images/photos/%s" alt="%s" loading="lazy">\n'
            '          <a class="lb-next" href="#p%d" aria-label="Next photograph"><span>&#8250;</span></a>\n'
            '          <a class="lb-close" href="#s%d" aria-label="Close">&#215;</a>\n'
            '          <p class="lb-count">%d / %d</p>%s\n'
            '        </div>'
            % (i, i + 1, n, i, (i - 1) % n, f, alt, (i + 1) % n, i, i + 1, n, label))
    return "\n".join(out)


SCRIPT = """      <script>
        /* Progressive enhancement only. The lightbox is CSS; this adds the arrow
           keys, Escape and swipe, none of which CSS can reach. If it never runs,
           the on-screen arrows still work and nothing looks broken. */
        (function () {
          function open_() { return document.querySelector('.lightbox:target'); }
          function go(sel) {
            var box = open_();
            if (!box) return;
            var link = box.querySelector(sel);
            if (link) location.replace(link.getAttribute('href'));
          }
          document.addEventListener('keydown', function (e) {
            if (!open_() || e.metaKey || e.ctrlKey || e.altKey) return;
            if (e.key === 'ArrowLeft')  { e.preventDefault(); go('.lb-prev'); }
            else if (e.key === 'ArrowRight') { e.preventDefault(); go('.lb-next'); }
            else if (e.key === 'Escape')     { e.preventDefault(); go('.lb-close'); }
          });
          var startX = null;
          document.addEventListener('touchstart', function (e) {
            startX = open_() ? e.touches[0].clientX : null;
          }, { passive: true });
          document.addEventListener('touchend', function (e) {
            if (startX === null) return;
            var dx = e.changedTouches[0].clientX - startX;
            startX = null;
            if (Math.abs(dx) > 45) go(dx < 0 ? '.lb-next' : '.lb-prev');
          }, { passive: true });
        }());
      </script>
"""


MONTHS = ("January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December")


def describe(f):
    """A readable fallback for alt text: the filenames carry their date, and
    'Photograph, 25 September 2016' is worth rather more to someone using a
    screen reader than '20160925 155817'. A real caption always wins."""
    m = re.search(r'(19|20)(\d{2})(\d{2})(\d{2})', f)
    if m:
        year, mon, day = m.group(1) + m.group(2), int(m.group(3)), int(m.group(4))
        if 1 <= mon <= 12 and 1 <= day <= 31:
            return "Photograph, %d %s %s" % (day, MONTHS[mon - 1], year)
    return "Photograph"


START = "<!-- lightboxes:start -->"
END = "<!-- lightboxes:end -->"


def write_page():
    """Rewrite the thumbnail grid and the lightbox panels in place.

    Both regions are delimited, so this is idempotent: run it as often as you
    like and anything you have written around them is left alone."""
    files = sorted(f for f in os.listdir(OUT_DIR) if f.lower().endswith(".jpg"))
    caps = read_captions()

    s = open(PAGE, encoding="utf-8").read()

    start = s.index('<section class="gallery"')
    start = s.index(">", start) + 1
    end = s.index("</section>", start)
    grid = ('\n          <p class="entry-empty">The first photographs are being sorted.</p>\n        '
            if not files else "\n" + build_gallery(files, caps) + "\n        ")
    s = s[:start] + grid + s[end:]

    block = (START + "\n" + build_lightboxes(files, caps) + "\n" + SCRIPT + "      " + END) \
        if files else (START + "\n      " + END)
    if START in s:
        s = s[:s.index(START)] + block + s[s.index(END) + len(END):]
    else:
        anchor = "      </main>"
        s = s[:s.index(anchor)] + "      " + block + "\n" + s[s.index(anchor):]
    open(PAGE, "w", encoding="utf-8").write(s)
    return len(files)


def main(argv):
    width = 1600
    if "--width" in argv:
        width = int(argv[argv.index("--width") + 1])
        argv = [a for i, a in enumerate(argv) if i not in (argv.index("--width"), argv.index("--width") + 1)]
    src_dir = argv[0] if argv and not argv[0].startswith("--") else DEFAULT_SRC

    os.makedirs(OUT_DIR, exist_ok=True)
    if not os.path.isdir(src_dir):
        print("No source folder at %s — nothing new to process." % src_dir)
    else:
        done = skipped = 0
        total = 0
        for name in sorted(os.listdir(src_dir)):
            if not name.lower().endswith(EXTS):
                continue
            dst = os.path.join(OUT_DIR, slug(name) + ".jpg")
            if os.path.exists(dst):
                skipped += 1
                continue
            size = strip_and_resize(os.path.join(src_dir, name), dst, width)
            ok = verify_clean(dst)
            total += size
            done += 1
            print("  %-40s %6.0f KB  %s" % (os.path.basename(dst), size / 1024,
                                            "metadata clean" if ok else "!! METADATA REMAINS"))
            if not ok:
                sys.exit("Stopping: %s still carries metadata. Do not publish it." % dst)
        print("\n%d processed, %d already present, %.1f MB added" % (done, skipped, total / 1e6))

    files = sorted(f for f in os.listdir(OUT_DIR) if f.lower().endswith(".jpg"))
    done, todo = sync_captions(files)
    print("captions: %d written, %d still to write — images/photos/captions.txt" % (done, todo))

    n = write_page()
    print("about/album.html rebuilt — %d photograph(s), each with its own lightbox panel" % n)


if __name__ == "__main__":
    main(sys.argv[1:])
