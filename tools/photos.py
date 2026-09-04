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
    """The grid of thumbnails, and nothing else.

    Each one is an ordinary link to the full-size file, so with JavaScript off
    it does what it always did. The caption travels on the anchor as data, which
    is what the viewer reads when it opens. There is no second copy of anything:
    one <img> per photograph on the page, and one overlay shared by all of them.
    """
    out = []
    for f in files:
        place, note = caps.get(f, ("", ""))
        cap = ""
        if place or note:
            cap = ("\n            <figcaption>" +
                   (('<span class="place">%s</span>' % html.escape(place)) if place else "") +
                   html.escape(note) + "</figcaption>")
        alt = html.escape(place or note or describe(f))
        data = ""
        if place:
            data += ' data-place="%s"' % html.escape(place)
        if note:
            data += ' data-note="%s"' % html.escape(note)
        out.append('          <figure>\n'
                   '            <a class="shot" href="/images/photos/%s"%s><img src="/images/photos/%s" '
                   'alt="%s" loading="lazy"></a>%s\n'
                   '          </figure>' % (f, data, f, alt, cap))
    return "\n".join(out)


VIEWER = """      <div class="lightbox" id="lightbox" role="dialog" aria-modal="true" aria-label="Photograph" tabindex="-1" hidden>
        <button class="lb-shade" type="button" aria-label="Close"></button>
        <button class="lb-prev" type="button" aria-label="Previous photograph"><span>&#8249;</span></button>
        <img alt="">
        <button class="lb-next" type="button" aria-label="Next photograph"><span>&#8250;</span></button>
        <button class="lb-close" type="button" aria-label="Close">&#215;</button>
        <p class="lb-count"></p>
        <p class="lb-caption"></p>
      </div>
      <script>
        /* One overlay, shared by every photograph. With JavaScript off the
           thumbnails stay ordinary links to the full-size files, which is what
           they were before this existed. */
        (function () {
          var box = document.getElementById('lightbox');
          if (!box) return;
          var shots = [].slice.call(document.querySelectorAll('.gallery .shot'));
          if (!shots.length) return;

          var img = box.querySelector('img'),
              count = box.querySelector('.lb-count'),
              caption = box.querySelector('.lb-caption'),
              at = 0, opener = null;

          function show(i) {
            at = (i + shots.length) % shots.length;
            var a = shots[at], place = a.dataset.place || '', note = a.dataset.note || '';
            img.src = a.getAttribute('href');
            img.alt = a.querySelector('img').alt;
            count.textContent = (at + 1) + ' / ' + shots.length;
            caption.innerHTML = '';
            if (place) {
              var s = document.createElement('span');
              s.className = 'place';
              s.textContent = place;
              caption.appendChild(s);
            }
            if (note) caption.appendChild(document.createTextNode(note));
            box.setAttribute('aria-label', 'Photograph ' + (at + 1) + ' of ' + shots.length);
            /* hold the neighbours in cache so stepping does not flash */
            [-1, 1].forEach(function (d) {
              var n = shots[(at + d + shots.length) % shots.length];
              new Image().src = n.getAttribute('href');
            });
          }

          function open_(i, from) {
            opener = from || null;
            show(i);
            box.hidden = false;
            document.documentElement.style.overflow = 'hidden';
            /* focus the dialog itself, not a control: programmatic focus on a
               tabindex="-1" element moves the keyboard in without painting a
               focus ring down one edge of the screen */
            box.focus();
          }

          function close_() {
            box.hidden = true;
            img.removeAttribute('src');
            document.documentElement.style.overflow = '';
            if (opener) { opener.focus(); opener = null; }
          }

          shots.forEach(function (a, i) {
            a.addEventListener('click', function (e) {
              if (e.metaKey || e.ctrlKey || e.shiftKey || e.button) return;
              e.preventDefault();
              open_(i, a);
            });
          });

          box.querySelector('.lb-prev').addEventListener('click', function () { show(at - 1); });
          box.querySelector('.lb-next').addEventListener('click', function () { show(at + 1); });
          box.querySelector('.lb-close').addEventListener('click', close_);
          box.querySelector('.lb-shade').addEventListener('click', close_);

          document.addEventListener('keydown', function (e) {
            if (box.hidden || e.metaKey || e.ctrlKey || e.altKey) return;
            if (e.key === 'ArrowLeft')       { e.preventDefault(); show(at - 1); }
            else if (e.key === 'ArrowRight') { e.preventDefault(); show(at + 1); }
            else if (e.key === 'Escape')     { e.preventDefault(); close_(); }
          });

          var startX = null;
          box.addEventListener('touchstart', function (e) {
            startX = e.touches[0].clientX;
          }, { passive: true });
          box.addEventListener('touchend', function (e) {
            if (startX === null) return;
            var dx = e.changedTouches[0].clientX - startX;
            startX = null;
            if (Math.abs(dx) > 45) show(dx < 0 ? at + 1 : at - 1);
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

    block = START + "\n" + VIEWER + "      " + END if files else START + "\n      " + END
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
    print("about/album.html rebuilt — %d photograph(s) in the gallery, one shared viewer" % n)


if __name__ == "__main__":
    main(sys.argv[1:])
