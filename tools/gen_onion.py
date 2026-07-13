"""Generate the julienned-onion silhouette SVG paths from a parametric layer model.

Modelled on the photo (flipped): a cut column at left whose face shows its own
lamination; a root plate and fringe at its foot where the layer tips converge;
and a fan of strictly nested crescent layers with individual widths — thin and
tight near the core, one distinctly fat band near the outer top, a thin skin
outside — hinging densely at the top and slumping apart toward the tips.
"""

import math

# ---------- fan boundary family (continuous parameter t in [0, TMAX]) ----------

TMAX = 12.3

def H(t):   # hinge points near column top (dense laminate)
    return (86 + 2.3 * t, 37 + 3.6 * t + 0.04 * t * t)

def B(t):   # tips, slumping along a rounded bottom-right
    return (64 + 5.8 * t + 0.33 * t * t, 250 + 3.2 * t - 0.08 * t * t)

def A(t):   # bulge amplitude, growing outward
    return 12 + 7.0 * t

def _controls(t):
    hx, hy = H(t)
    bx, by = B(t)
    dx, dy = bx - hx, by - hy
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = uy, -ux
    mx, my = (hx + bx) / 2, (hy + by) / 2
    a = A(t)
    p1 = (mx - ux * L * 0.28 + nx * a * 1.30, my - uy * L * 0.28 + ny * a * 1.30)
    p2 = (mx + ux * L * 0.20 + nx * a * 1.16, my + uy * L * 0.20 + ny * a * 1.16)
    return p1, p2

def cubic(p0, p1, p2, p3, u):
    v = 1 - u
    return tuple(
        v * v * v * a + 3 * v * v * u * b + 3 * v * u * u * c + u * u * u * d
        for a, b, c, d in zip(p0, p1, p2, p3)
    )

def f(v):
    return f"{v:.1f}".rstrip("0").rstrip(".")

def ribbon(t0, t1):
    h1, b1 = H(t1), B(t1)
    p11, p21 = _controls(t1)
    h0, b0 = H(t0), B(t0)
    p10, p20 = _controls(t0)
    return (
        f"M{f(h1[0])} {f(h1[1])} "
        f"C{f(p11[0])} {f(p11[1])} {f(p21[0])} {f(p21[1])} {f(b1[0])} {f(b1[1])} "
        f"L{f(b0[0])} {f(b0[1])} "
        f"C{f(p20[0])} {f(p20[1])} {f(p10[0])} {f(p10[1])} {f(h0[0])} {f(h0[1])} Z"
    )

# ---------- individual layer widths (inner -> outer), one fat band, thin skin ----------

WIDTHS = [0.55, 0.65, 0.75, 0.90, 1.05, 1.15, 1.10, 0.95, 1.90, 0.80, 0.60, 0.45]
GAP = 0.26

def layer_spans():
    total = sum(WIDTHS) + GAP * len(WIDTHS)
    scale = TMAX / total
    spans, pos = [], 0.0
    for w in WIDTHS:
        spans.append((pos * scale, (pos + w) * scale))
        pos += w + GAP
    return spans

# ---------- the cut column, split into laminae (the face has layers too) ----------

COL_L = [(63, 33), (56, 92), (50, 166), (48, 238)]   # left edge control points
COL_R = [(87, 40), (79, 96), (74, 168), (72, 240)]   # right edge control points
STRIPS = [(0.0, 0.34), (0.42, 0.72), (0.80, 1.0)]

def col_edge(frac):
    return [
        (l[0] + (r[0] - l[0]) * frac, l[1] + (r[1] - l[1]) * frac)
        for l, r in zip(COL_L, COL_R)
    ]

def col_strip(fa, fb):
    a = col_edge(fa)
    b = col_edge(fb)
    return (
        f"M{f(a[0][0])} {f(a[0][1])} "
        f"C{f(a[1][0])} {f(a[1][1])} {f(a[2][0])} {f(a[2][1])} {f(a[3][0])} {f(a[3][1])} "
        f"L{f(b[3][0])} {f(b[3][1])} "
        f"C{f(b[2][0])} {f(b[2][1])} {f(b[1][0])} {f(b[1][1])} {f(b[0][0])} {f(b[0][1])} Z"
    )

# ---------- root plate and fringe at the column's foot ----------

ROOT = [
    "M51 243 C52.5 249.5 67.5 249.5 69 243 C63 245.5 57 245.5 51 243 Z",
    "M56 250 C54 255 52 259 49.5 263 L52.5 263.5 C54.5 258.5 56.5 254 58 250.5 Z",
    "M61 250.5 C60.5 256 60 261 60 265.5 L63 265.5 C63 260.5 63.5 255 64 250.5 Z",
    "M66 250.5 C68 255 70 258.5 73 262 L70 263 C67.5 258.5 65.5 254.5 64.5 250.5 Z",
]

# ---------- checks ----------

def bounds(paths_pts):
    xs, ys = [], []
    t = 0.0
    while t <= TMAX + 1e-9:
        for u in (i / 24 for i in range(25)):
            x, y = cubic(H(t), *_controls(t), B(t), u)
            xs.append(x)
            ys.append(y)
        t += 0.25
    return min(xs), max(xs), min(ys), max(ys)

def min_facing_gap(spans):
    worst = 1e9
    for (a0, a1), (b0, b1) in zip(spans, spans[1:]):
        for u in (i / 24 for i in range(25)):
            x0, y0 = cubic(H(a1), *_controls(a1), B(a1), u)
            x1, y1 = cubic(H(b0), *_controls(b0), B(b0), u)
            worst = min(worst, math.hypot(x1 - x0, y1 - y0))
    return worst

# ---------- emit ----------

spans = layer_spans()
paths = [col_strip(fa, fb) for fa, fb in STRIPS] + ROOT + [ribbon(t0, t1) for t0, t1 in spans]

print("bounds (xmin xmax ymin ymax):", " ".join(f(v) for v in bounds(None)))
print("min facing gap between consecutive layers:", f(min_facing_gap(spans)))
print("fat layer span (t units):", f(spans[8][1] - spans[8][0]), "vs neighbor:", f(spans[7][1] - spans[7][0]))
print()
for i, d in enumerate(paths):
    print(f'            <path style="--i:{i}" d="{d}" />')
