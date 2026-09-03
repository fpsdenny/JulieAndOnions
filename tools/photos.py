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


def build_gallery():
    caps = read_captions()
    files = sorted(f for f in os.listdir(OUT_DIR) if f.lower().endswith(".jpg"))
    if not files:
        return '          <p class="entry-empty">The first photographs are being sorted.</p>'
    out = []
    for f in files:
        place, note = caps.get(f, ("", ""))
        cap = ""
        if place or note:
            cap = ("\n            <figcaption>" +
                   (('<span class="place">%s</span>' % html.escape(place)) if place else "") +
                   html.escape(note) + "</figcaption>")
        alt = html.escape(place or note or os.path.splitext(f)[0].replace("-", " "))
        out.append('          <figure>\n'
                   '            <a href="/images/photos/%s"><img src="/images/photos/%s" alt="%s" loading="lazy"></a>%s\n'
                   '          </figure>' % (f, f, alt, cap))
    return "\n".join(out)


def write_page():
    s = open(PAGE, encoding="utf-8").read()
    start = s.index('<section class="gallery"')
    start = s.index(">", start) + 1
    end = s.index("</section>", start)
    s = s[:start] + "\n" + build_gallery() + "\n        " + s[end:]
    open(PAGE, "w", encoding="utf-8").write(s)


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

    if not os.path.exists(CAPTIONS):
        with open(CAPTIONS, "w", encoding="utf-8") as f:
            f.write("# filename | place | a sentence\n")
        print("Wrote a caption file at images/photos/captions.txt")

    write_page()
    n = len([f for f in os.listdir(OUT_DIR) if f.lower().endswith(".jpg")])
    print("about/album.html rebuilt — %d photograph(s) in the gallery" % n)


if __name__ == "__main__":
    main(sys.argv[1:])
