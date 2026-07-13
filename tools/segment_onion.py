"""Photo -> silhouette, take four: GrabCut with the purple layer-line lattice as
sure-foreground and the frame border as sure-background. The lines thread the
whole onion, so the graph cut claims the pale flesh between them and leaves
the board (similar color, but disconnected from the lattice) as background.
"""

import cv2
import numpy as np
from PIL import Image

SRC = r"C:\Users\hayde\OneDrive\Pictures\20260705_190801.jpg"
SCRATCH = r"C:\Users\hayde\AppData\Local\Temp\claude\C--Users-hayde-JulieAndOnions\23759322-260c-4af5-8dca-39c4ee22112d\scratchpad"
OUT_MASK = r"C:\Users\hayde\JulieAndOnions\JulieAndOnions\images\onion-mask.png"

WORK_W = 1000
SEED_P, SEED_L = 26, 198     # purpleness (raw, 0-centered) and lightness for sure-FG lines
GAP_P, GAP_L = 19, 209       # thresholds for punching layer-line gaps
GAP_MIN_AREA = 55            # drop gap specks smaller than this (px at WORK_W)
TARGET_W = 640
ROOM = (60, 41, 23)
PAPER = (220, 192, 154)

pil = Image.open(SRC).convert("RGB")
pil = pil.transpose(Image.Transpose.ROTATE_270).transpose(Image.Transpose.FLIP_LEFT_RIGHT)
W, H = pil.size
pil = pil.crop((round(0.17 * W), round(0.12 * H), round(0.17 * W) + round(0.83 * W), round(0.12 * H) + round(0.863 * H)))
pil = pil.resize((WORK_W, round(pil.height * WORK_W / pil.width)), Image.Resampling.LANCZOS)
rgb = np.asarray(pil, dtype=np.int16)
h, w = rgb.shape[:2]

r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
purple = (r + b) // 2 - g
light = rgb.max(axis=2)
yellow = (r + g) // 2 - b

lines = ((purple > SEED_P) & (light < SEED_L)).astype(np.uint8)
lines = cv2.medianBlur(lines * 255, 3) > 0
core = ((yellow > 44) & (light > 170))

# GrabCut mask: border ring sure-BG, line lattice + core sure-FG, rest probable-BG
gc = np.full((h, w), cv2.GC_PR_BGD, np.uint8)
ring = 14
gc[:ring, :] = gc[-ring:, :] = cv2.GC_BGD
gc[:, :ring] = gc[:, -ring:] = cv2.GC_BGD
gc[lines] = cv2.GC_FGD
gc[core] = cv2.GC_FGD

img_bgr = cv2.cvtColor(rgb.astype(np.uint8), cv2.COLOR_RGB2BGR)
bgd = np.zeros((1, 65), np.float64)
fgd = np.zeros((1, 65), np.float64)
cv2.grabCut(img_bgr, gc, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
fg = ((gc == cv2.GC_FGD) | (gc == cv2.GC_PR_FGD)).astype(np.uint8) * 255

# keep the component containing the core; drop stray blobs
n, labels, stats, _ = cv2.connectedComponentsWithStats(fg, connectivity=4)
core_label = np.bincount(labels[core], minlength=n)
core_label[0] = 0
fg = (labels == core_label.argmax()).astype(np.uint8) * 255

# tidy edges: close then open, slightly larger kernel for a calmer rim
k7 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
k5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, k7)
fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN, k5)

# punch the layer lines back out as gaps; keep long lines, drop specks
gap = ((purple > GAP_P) & (light < GAP_L)).astype(np.uint8) * 255
gn, glabels, gstats, _ = cv2.connectedComponentsWithStats(gap, connectivity=8)
sizes = gstats[:, cv2.CC_STAT_AREA]
keep_ids = np.nonzero(sizes >= GAP_MIN_AREA)[0]
keep_ids = keep_ids[keep_ids != 0]
gap = np.isin(glabels, keep_ids).astype(np.uint8) * 255
alpha = cv2.bitwise_and(fg, cv2.bitwise_not(gap))

ys, xs = np.nonzero(alpha)
mx, my = round((xs.max() - xs.min()) * 0.04), round((ys.max() - ys.min()) * 0.04)
x0, x1 = max(0, xs.min() - mx), min(w, xs.max() + mx)
y0, y1 = max(0, ys.min() - my), min(h, ys.max() + my)
alpha_img = Image.fromarray(alpha[y0:y1, x0:x1])
alpha_img = alpha_img.resize((TARGET_W, round(alpha_img.height * TARGET_W / alpha_img.width)), Image.Resampling.LANCZOS)

white = Image.new("RGBA", alpha_img.size, (255, 255, 255, 255))
clear = Image.new("RGBA", alpha_img.size, (255, 255, 255, 0))
Image.composite(white, clear, alpha_img).save(OUT_MASK)

review = Image.new("RGB", alpha_img.size, ROOM)
review.paste(Image.new("RGB", alpha_img.size, PAPER), (0, 0), alpha_img)
review.save(SCRATCH + r"\onion_mask_review.png")
print("mask:", OUT_MASK, alpha_img.size)
