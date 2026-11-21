#!/usr/bin/env python3
"""VELMARA - travel poster generator (pure Python 3.13 stdlib, deterministic).

Draws a 1024x1024 PNG travel poster for VELMARA, an invented place:
floating stone terraces above a teal sea at golden hour, one great
waterfall falling UPWARD into the sky.

Writes to /output/entry.png (or $OUTPUT_DIR/entry.png for local runs).
No network, no third-party imports, no clock/randomness: same bytes
every run.
"""
import math
import os
import struct
import zlib
from binascii import crc32

W, H = 1024, 1024
OUT_DIR = os.environ.get("OUTPUT_DIR") or "/output"

# ---------------------------------------------------------------- font (5x7)
# '#' = ink, '.' = empty. Letters A-Z, digits 0-9, space and . , - ' !
FONT = {
    "A": (".###.", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "B": ("####.", "#...#", "#...#", "####.", "#...#", "#...#", "####."),
    "C": (".####", "#....", "#....", "#....", "#....", "#....", ".####"),
    "D": ("####.", "#...#", "#...#", "#...#", "#...#", "#...#", "####."),
    "E": ("#####", "#....", "#....", "####.", "#....", "#....", "#####"),
    "F": ("#####", "#....", "#....", "####.", "#....", "#....", "#...."),
    "G": (".####", "#....", "#....", "#.###", "#...#", "#...#", ".###."),
    "H": ("#...#", "#...#", "#...#", "#####", "#...#", "#...#", "#...#"),
    "I": (".###.", "..#..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "J": ("..###", "...#.", "...#.", "...#.", "...#.", "#..#.", ".##.."),
    "K": ("#...#", "#..#.", "#.#..", "##...", "#.#..", "#..#.", "#...#"),
    "L": ("#....", "#....", "#....", "#....", "#....", "#....", "#####"),
    "M": ("#...#", "##.##", "#.#.#", "#.#.#", "#...#", "#...#", "#...#"),
    "N": ("#...#", "##..#", "##..#", "#.#.#", "#..##", "#..##", "#...#"),
    "O": (".###.", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "P": ("####.", "#...#", "#...#", "####.", "#....", "#....", "#...."),
    "Q": (".###.", "#...#", "#...#", "#...#", "#.#.#", "#..#.", ".##.#"),
    "R": ("####.", "#...#", "#...#", "####.", "#.#..", "#..#.", "#...#"),
    "S": (".####", "#....", "#....", ".###.", "....#", "....#", "####."),
    "T": ("#####", "..#..", "..#..", "..#..", "..#..", "..#..", "..#.."),
    "U": ("#...#", "#...#", "#...#", "#...#", "#...#", "#...#", ".###."),
    "V": ("#...#", "#...#", "#...#", "#...#", "#...#", ".#.#.", "..#.."),
    "W": ("#...#", "#...#", "#...#", "#.#.#", "#.#.#", "##.##", "#...#"),
    "X": ("#...#", "#...#", ".#.#.", "..#..", ".#.#.", "#...#", "#...#"),
    "Y": ("#...#", "#...#", ".#.#.", "..#..", "..#..", "..#..", "..#.."),
    "Z": ("#####", "....#", "...#.", "..#..", ".#...", "#....", "#####"),
    "0": (".###.", "#..##", "#.#.#", "##..#", "#...#", "#...#", ".###."),
    "1": ("..#..", ".##..", "..#..", "..#..", "..#..", "..#..", ".###."),
    "2": (".###.", "#...#", "....#", "...#.", "..#..", ".#...", "#####"),
    "3": ("####.", "....#", "....#", ".###.", "....#", "....#", "####."),
    "4": ("...#.", "..##.", ".#.#.", "#..#.", "#####", "...#.", "...#."),
    "5": ("#####", "#....", "####.", "....#", "....#", "#...#", ".###."),
    "6": (".###.", "#....", "#....", "####.", "#...#", "#...#", ".###."),
    "7": ("#####", "....#", "...#.", "..#..", "..#..", "..#..", "..#.."),
    "8": (".###.", "#...#", "#...#", ".###.", "#...#", "#...#", ".###."),
    "9": (".###.", "#...#", "#...#", ".####", "....#", "....#", ".###."),
    " ": (".....", ".....", ".....", ".....", ".....", ".....", "....."),
    ".": (".....", ".....", ".....", ".....", ".....", ".##..", ".##.."),
    ",": (".....", ".....", ".....", ".....", ".##..", ".##..", ".#..."),
    "-": (".....", ".....", ".....", ".###.", ".....", ".....", "....."),
    "'": ("..#..", "..#..", ".#...", ".....", ".....", ".....", "....."),
    "!": ("..#..", "..#..", "..#..", "..#..", "..#..", ".....", "..#.."),
}


def text_width(text, scale):
    return len(text) * 6 * scale - scale


def draw_text(buf, text, x, y, scale, color):
    """Draw text left-aligned at (x, y). Returns the x after the last glyph."""
    cx = x
    for ch in text:
        glyph = FONT.get(ch)
        if glyph is not None:
            for r in range(7):
                row = glyph[r]
                for c in range(5):
                    if row[c] == "#":
                        fill_rect(buf, cx + c * scale, y + r * scale,
                                  scale, scale, color)
        cx += 6 * scale
    return cx


def draw_text_alpha(buf, text, x, y, scale, color, alpha):
    """Draw text blending each glyph pixel with alpha (for glows)."""
    cx = x
    for ch in text:
        glyph = FONT.get(ch)
        if glyph is not None:
            for r in range(7):
                row = glyph[r]
                for c in range(5):
                    if row[c] == "#":
                        for yy in range(y + r * scale, y + (r + 1) * scale):
                            for xx in range(cx + c * scale,
                                           cx + (c + 1) * scale):
                                blend(buf, xx, yy, color[0], color[1],
                                      color[2], alpha)
        cx += 6 * scale


# ---------------------------------------------------------------- canvas
def new_canvas():
    return bytearray(W * H * 3)


def row_fill(buf, y, x0, x1, color):
    x0 = max(0, x0)
    x1 = min(W, x1)
    if x1 <= x0 or not (0 <= y < H):
        return
    r, g, b = color
    n = x1 - x0
    i = (y * W + x0) * 3
    buf[i:i + n * 3] = bytes((r, g, b)) * n


def fill_rect(buf, x, y, w, h, color):
    for yy in range(y, y + h):
        row_fill(buf, yy, x, x + w, color)


def blend(buf, x, y, r, g, b, a):
    """Blend colour (r,g,b) onto pixel (x,y) with alpha a (0..1)."""
    if 0 <= x < W and 0 <= y < H and a > 0:
        i = (y * W + x) * 3
        ia = 1.0 - a
        buf[i] = int(buf[i] * ia + r * a)
        buf[i + 1] = int(buf[i + 1] * ia + g * a)
        buf[i + 2] = int(buf[i + 2] * ia + b * a)


def ellipse(buf, cx, cy, rx, ry, color):
    for dy in range(-ry, ry + 1):
        t = 1.0 - (dy * dy) / float(ry * ry)
        if t < 0:
            continue
        dx = int(rx * math.sqrt(t))
        row_fill(buf, cy + dy, cx - dx, cx + dx + 1, color)


def disc_soft(buf, cx, cy, radius, color, alpha):
    """Soft-edged disc: alpha fades to 0 at the rim."""
    r0 = int(radius)
    for dy in range(-r0, r0 + 1):
        for dx in range(-r0, r0 + 1):
            d = math.sqrt(dx * dx + dy * dy)
            if d < radius:
                a = alpha * (1.0 - d / radius) ** 2
                blend(buf, cx + dx, cy + dy, color[0], color[1], color[2], a)


def line(buf, x0, y0, x1, y1, color):
    """Bresenham line."""
    dx = abs(x1 - x0)
    dy = -abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx + dy
    x, y = x0, y0
    while True:
        blend(buf, x, y, color[0], color[1], color[2], 0.9)
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 >= dy:
            err += dy
            x += sx
        if e2 <= dx:
            err += dx
            y += sy


def lerp(c0, c1, t):
    return (int(c0[0] + (c1[0] - c0[0]) * t),
            int(c0[1] + (c1[1] - c0[1]) * t),
            int(c0[2] + (c1[2] - c0[2]) * t))


def grad_rows(buf, y0, y1, c_top, c_bot):
    """Vertical gradient between rows y0..y1 (inclusive)."""
    span = max(1, y1 - y0)
    for y in range(y0, y1 + 1):
        row_fill(buf, y, 0, W, lerp(c_top, c_bot, (y - y0) / span))


# ---------------------------------------------------------------- scene
def draw_sky(buf):
    grad_rows(buf, 0, 300, (40, 22, 70), (148, 66, 108))
    grad_rows(buf, 300, 640, (148, 66, 108), (255, 168, 92))
    # faint early stars high up, more of them fading in
    for k in range(110):
        sx = int((math.sin(k * 12.9898) * 43758.5453 % 1.0) * W)
        sy = int((math.sin(k * 78.233) * 12543.1234 % 1.0) * 300)
        a = 0.25 + 0.35 * abs(math.sin(k * 3.7))
        blend(buf, sx, sy, 255, 240, 220, a)
        if k % 3 == 0:
            blend(buf, sx + 1, sy, 255, 240, 220, a * 0.6)


def draw_sun(buf):
    cx, cy = 700, 470
    # wide warm glow, stronger for golden hour
    for dy in range(-285, 286, 2):
        for dx in range(-285, 286, 2):
            d = math.sqrt(dx * dx + dy * dy)
            if d < 285:
                a = 0.62 * (1.0 - d / 285.0) ** 2
                blend(buf, cx + dx, cy + dy, 255, 170, 90, a)
    # solid disc
    ellipse(buf, cx, cy, 86, 86, (255, 222, 150))
    ellipse(buf, cx, cy, 62, 62, (255, 238, 190))


def sun_ray(buf, cx, cy, angle_deg, length, color, alpha):
    """One soft sun ray: a widening wedge of low-alpha light."""
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    px, py = -sa, ca  # perpendicular unit vector
    for s in range(0, length, 3):
        t = s / float(length)
        wdt = 2 + int(10 * t)
        x0 = cx + int(s * ca)
        y0 = cy + int(s * sa)
        for w in range(-wdt, wdt + 1):
            blend(buf, x0 + int(w * px), y0 + int(w * py),
                  color[0], color[1], color[2], alpha * (1.0 - t * 0.7))


def draw_sunrays(buf):
    """Golden-hour rays fanning out from the sun (drawn under the disc)."""
    cx, cy = 700, 470
    for ang in (205, 230, 250, 290, 310, 335):
        sun_ray(buf, cx, cy, ang, 340, (255, 190, 110), 0.08)
    for ang in (35, 145):
        sun_ray(buf, cx, cy, ang, 200, (255, 190, 110), 0.07)


def draw_clouds(buf):
    # soft clouds, semi-transparent; lower ones catch the sunset orange
    clouds = (
        (180, 250, 150, 20, (255, 190, 170), 0.10),
        (880, 210, 170, 24, (255, 190, 170), 0.10),
        (430, 150, 120, 16, (255, 200, 190), 0.10),
        (120, 420, 110, 16, (255, 190, 170), 0.10),
        (640, 120, 150, 14, (255, 205, 200), 0.09),
        (330, 565, 190, 18, (255, 165, 115), 0.13),
        (920, 480, 120, 14, (255, 175, 130), 0.11),
    )
    for (cx, cy, rx, ry, col, al) in clouds:
        for dy in range(-ry, ry + 1):
            t = 1.0 - (dy * dy) / float(ry * ry)
            if t <= 0:
                continue
            dx = int(rx * math.sqrt(t))
            for x in range(cx - dx, cx + dx + 1):
                blend(buf, x, cy + dy, col[0], col[1], col[2], al)


def draw_sea(buf):
    grad_rows(buf, 640, H - 1, (18, 128, 138), (6, 58, 88))
    # sun reflection column: soft vertical glow, smooth falloff, no banding
    for y in range(640, H):
        t = (y - 640) / float(H - 640)
        half = int(150 * (1.0 - 0.45 * t))
        for x in range(700 - half, 700 + half + 1):
            d = abs(x - 700) / float(max(1, half))
            a = 0.20 * (1.0 - d) ** 2 * (1.0 - 0.55 * t)
            blend(buf, x, y, 255, 205, 130, a)
    # faint horizontal shimmer streaks, more of them
    for k in range(70):
        y = 660 + int((math.sin(k * 26.31) * 43758.5453 % 1.0) * 340)
        x0 = int((math.sin(k * 11.17) * 24634.6345 % 1.0) * 900)
        ln = 30 + int((math.sin(k * 7.77) * 12345.6789 % 1.0) * 120)
        for x in range(x0, min(W, x0 + ln)):
            blend(buf, x, y, 190, 235, 235, 0.16)


def draw_horizon_glow(buf):
    """Warm glow band hugging the horizon where sky meets sea."""
    for y in range(560, 641):
        t = (y - 560) / 80.0
        a = 0.22 * math.sin(math.pi * t) ** 2
        for x in range(0, W, 2):
            blend(buf, x, y, 255, 150, 80, a)
            blend(buf, x + 1, y, 255, 150, 80, a)


def draw_sea_reflections(buf):
    """Soft dark reflections of the floating terraces on the water."""
    # mid terrace (cx 270, root tip above the waterline): reflection below it
    for y in range(640, 790):
        t = (y - 640) / 150.0
        half = int(95 * (1.0 - 0.5 * t))
        for x in range(270 - half, 270 + half + 1):
            d = abs(x - 270) / float(max(1, half))
            blend(buf, x, y, 8, 42, 62, 0.16 * (1.0 - d) * (1.0 - 0.7 * t))
    # near terrace (cx 560): its root already plunges into the sea, so the
    # reflection continues the dark root downward, fading out
    for y in range(756, 930):
        t = (y - 756) / 174.0
        half = int(42 * (1.0 - 0.6 * t))
        for x in range(560 - half, 560 + half + 1):
            d = abs(x - 560) / float(max(1, half))
            blend(buf, x, y, 8, 42, 62, 0.14 * (1.0 - d) * (1.0 - 0.6 * t))


def draw_distant_boat(buf):
    """One tiny distant sailboat for scale, hazy near the horizon."""
    hx, hy = 868, 668
    for y in range(hy - 5, hy):
        t = (y - (hy - 5)) / 5.0
        half = int(11 * (1.0 - 0.4 * t))
        row_fill(buf, y, hx - half, hx + half + 1, (70, 60, 58))
    line(buf, hx, hy - 5, hx, hy - 30, (70, 60, 58))
    for y in range(hy - 30, hy - 5):
        t = (y - (hy - 30)) / 25.0
        half = int(9 * t)
        row_fill(buf, y, hx + 1, hx + 1 + half, (232, 226, 214))


def terrace(buf, cx, top, width, body, depth, pale=False):
    """One floating island: grass cap, stone body, tapering rock root.
    pale=True renders a distant island in hazy, lighter colours, no details."""
    if pale:
        grass = (150, 178, 140)
        stone = (168, 148, 132)
        rock = (120, 104, 96)
    else:
        grass = (88, 142, 82)
        stone = (124, 98, 80)
        rock = (72, 56, 48)
    # grass cap
    ellipse(buf, cx, top, width // 2, 13, grass)
    # stone body: trapezoid narrowing downward
    for y in range(top, top + body):
        t = (y - top) / float(max(1, body))
        half = int((width // 2) * (1.0 - 0.35 * t))
        row_fill(buf, y, cx - half, cx + half + 1, stone)
    # rock root tapering to a point
    y0 = top + body
    for y in range(y0, y0 + depth):
        t = (y - y0) / float(max(1, depth))
        half = int((width // 2) * 0.65 * (1.0 - t))
        row_fill(buf, y, cx - half, cx + half + 1, rock)
    if pale:
        return
    # tiny trees on top
    for (tx, tr) in ((-width // 4, 12), (width // 5, 9), (0, 14)):
        ellipse(buf, cx + tx, top - tr, tr, tr, (46, 96, 58))
    # one tiny white house
    hx = cx + width // 3
    fill_rect(buf, hx, top - 22, 22, 16, (245, 238, 222))
    for yy in range(6):
        row_fill(buf, top - 28 + yy, hx - yy, hx + 22 + yy, (150, 60, 60))


def draw_terraces(buf):
    terrace(buf, 150, 288, 150, 20, 55, pale=True)  # distant, hazy, small
    terrace(buf, 780, 300, 250, 34, 120)   # far, high
    terrace(buf, 270, 392, 310, 40, 150)   # mid, holds the waterfall top
    terrace(buf, 560, 520, 380, 46, 190)   # near, low


def draw_waterfall(buf):
    """The landmark: a jet of sea that LAUNCHES upward to a terrace.
    It takes off from the waterline with a splash crown (widest at the
    base), narrows and disperses as it climbs, and bursts into spray
    where it arrives at the terrace above."""
    x_base, y_top, y_bot = 300, 400, 646
    # --- splash crown where the jet launches off the sea surface
    ellipse(buf, x_base, 644, 52, 10, (235, 248, 250))  # foam ring
    for k in range(9):
        ang = math.pi * (0.15 + 0.7 * k / 8.0)
        r = 46
        dx = int(r * math.cos(ang))
        dy = -int(r * math.sin(ang) * 0.55)
        disc_soft(buf, x_base + dx, 640 + dy, 7, (230, 246, 250), 0.85)
    # --- the rising column: widest at the base, dispersing toward the top
    for y in range(y_top, y_bot):
        t = (y - y_top) / float(y_bot - y_top)  # 0 top, 1 base
        sway = int(6 * math.sin(y * 0.02))
        cx = x_base + sway
        half = 8 + int(22 * t * t)  # narrow at the top, flaring at the sea
        if t < 0.18:
            # near the top the jet breaks up into droplets, not a band
            for (ox, oy, rr) in ((-6, 0, 4), (4, 6, 5), (-2, 12, 4),
                                 (8, -4, 3)):
                disc_soft(buf, cx + ox, y + oy, rr, (214, 240, 247), 0.8)
            continue
        row_fill(buf, y, cx - half, cx + half + 1, (206, 238, 246))
        # bright rising streaks
        for x in range(cx - half, cx + half + 1):
            if (x * 7 + y * 3) % 13 < 2:
                blend(buf, x, y, 255, 255, 255, 0.75)
        # warm golden core so the jet glows in the sunset light
        core = max(1, half // 3)
        for x in range(cx - core, cx + core + 1):
            blend(buf, x, y, 255, 205, 120, 0.20)
    # --- droplets arcing upward alongside the column, trails trailing below
    for (dx, dy, rr) in ((-38, 96, 4), (-30, 60, 3), (36, 110, 4),
                         (30, 70, 3), (-44, 150, 3), (42, 160, 3),
                         (-26, 30, 3), (26, 40, 4)):
        disc_soft(buf, x_base + dx, y_bot - dy, rr, (235, 247, 250), 0.9)
        for s in range(1, 7):
            blend(buf, x_base + dx, y_bot - dy + s * 2, 235, 247, 250, 0.5)
    # --- spray burst where the water arrives at the terrace (brighter)
    disc_soft(buf, x_base, y_top + 4, 60, (225, 246, 250), 0.65)
    disc_soft(buf, x_base, y_top + 2, 26, (240, 250, 252), 0.6)
    disc_soft(buf, x_base - 26, y_top + 12, 34, (225, 246, 250), 0.55)
    disc_soft(buf, x_base + 28, y_top + 12, 34, (225, 246, 250), 0.55)
    for k in range(12):
        ang = math.pi * (0.08 + 0.84 * k / 11.0)
        r = 58 + (k % 3) * 8
        dx = int(r * math.cos(ang))
        dy = -int(r * math.sin(ang) * 0.5)
        disc_soft(buf, x_base + dx, y_top + 6 + dy, 5, (235, 247, 250), 0.95)


def draw_sailboat(buf):
    """A tiny sailboat on the teal sea, left of the sun column."""
    hx, hy = 470, 724  # hull waterline
    for y in range(hy - 8, hy):
        t = (y - (hy - 8)) / 8.0
        half = int(20 * (1.0 - 0.45 * t))
        row_fill(buf, y, hx - half, hx + half + 1, (52, 38, 34))
    line(buf, hx, hy - 8, hx, hy - 52, (40, 30, 28))  # mast
    for y in range(hy - 52, hy - 8):  # cream sail, wide at the boom
        t = (y - (hy - 52)) / 44.0
        half = int(16 * t)
        row_fill(buf, y, hx + 2, hx + 2 + half, (250, 244, 226))
    fill_rect(buf, hx + 1, hy - 56, 10, 5, (220, 90, 70))  # tiny flag
    for y in range(hy, hy + 10):  # soft reflection
        a = 0.18 * (1.0 - (y - hy) / 10.0)
        for x in range(hx - 14, hx + 15):
            blend(buf, x, y, 120, 150, 150, a)


def draw_lanterns(buf):
    """Warm floating lanterns rising beside the waterfall jet."""
    for (lx, ly, r) in ((186, 472, 6), (196, 545, 5), (392, 505, 5),
                        (410, 575, 6)):
        disc_soft(buf, lx, ly, r + 9, (255, 170, 80), 0.35)  # halo
        ellipse(buf, lx, ly, r, r, (255, 196, 110))           # glow core
        ellipse(buf, lx, ly - 1, r - 2, r - 2, (255, 226, 160))
        fill_rect(buf, lx - 3, ly - r - 2, 6, 3, (60, 40, 30))  # cap


def draw_rainbow(buf):
    """A faint rainbow arc in the spray where the jet arrives."""
    cx, cy = 300, 408
    bands = ((255, 96, 86), (255, 210, 96), (130, 205, 130),
             (130, 175, 255))
    for bi, col in enumerate(bands):
        r = 84 - bi * 7
        for deg in range(195, 346, 2):
            a = math.radians(deg)
            x = cx + int(r * math.cos(a))
            y = cy + int(r * math.sin(a))
            blend(buf, x, y, col[0], col[1], col[2], 0.30)
            blend(buf, x + 1, y, col[0], col[1], col[2], 0.22)


def draw_birds(buf):
    for (bx, by, s) in ((180, 180, 14), (240, 150, 11), (860, 330, 12),
                        (900, 300, 9)):
        line(buf, bx - s, by, bx, by - s // 2, (30, 18, 46))
        line(buf, bx, by - s // 2, bx + s, by, (30, 18, 46))


def draw_foreground(buf):
    # foreground terrace edge, bottom-left: a dark cliff that reads as the
    # nearest floating island, with its own grass cap, trees and tiny house
    for y in range(880, H):
        t = (y - 880) / float(H - 880)
        half = int(330 * (1.0 - t * 0.55))
        row_fill(buf, y, 0, half, (16, 26, 44))
    # grass cap along the cliff's top edge
    ellipse(buf, 160, 880, 160, 11, (52, 96, 62))
    # two small trees and one tiny house on the foreground terrace
    ellipse(buf, 70, 866, 11, 11, (40, 88, 54))
    ellipse(buf, 225, 864, 9, 9, (40, 88, 54))
    fill_rect(buf, 268, 860, 18, 13, (228, 220, 204))
    for yy in range(5):
        row_fill(buf, 855 + yy, 268 - yy, 268 + 18 + yy, (140, 56, 56))


def draw_frame(buf):
    for t in range(5):
        inset = 20 + t
        row_fill(buf, inset, inset, W - inset, (255, 244, 214))
        row_fill(buf, H - 1 - inset, inset, W - inset, (255, 244, 214))
        for y in range(inset, H - inset):
            blend(buf, inset, y, 255, 244, 214, 1.0)
            blend(buf, W - 1 - inset, y, 255, 244, 214, 1.0)


def draw_poster():
    buf = new_canvas()
    draw_sky(buf)
    draw_sunrays(buf)
    draw_sun(buf)
    draw_clouds(buf)
    draw_horizon_glow(buf)
    draw_sea(buf)
    draw_sea_reflections(buf)
    draw_sailboat(buf)
    draw_distant_boat(buf)
    draw_terraces(buf)
    draw_waterfall(buf)
    draw_lanterns(buf)
    draw_rainbow(buf)
    draw_birds(buf)
    draw_foreground(buf)
    # place name, large, with a soft warm glow and shadow
    name = "VELMARA"
    scale = 14
    nx = (W - text_width(name, scale)) // 2
    for (gx, gy) in ((-3, 0), (3, 0), (0, -3), (0, 3)):
        draw_text_alpha(buf, name, nx + gx, 88 + gy, scale,
                        (255, 180, 90), 0.28)
    draw_text(buf, name, nx + 5, 92, scale, (28, 14, 48))
    draw_text(buf, name, nx, 88, scale, (255, 244, 214))
    # one short tagline under the name
    tag = "WHERE THE SEA FALLS UP"
    tscale = 4
    tx = (W - text_width(tag, tscale)) // 2
    draw_text(buf, tag, tx + 2, 198, tscale, (28, 14, 48))
    draw_text(buf, tag, tx, 196, tscale, (255, 226, 170))
    draw_frame(buf)
    return buf


# ---------------------------------------------------------------- png output
def chunk(typ, data):
    out = struct.pack(">I", len(data)) + typ + data
    out += struct.pack(">I", crc32(typ + data) & 0xFFFFFFFF)
    return out


def write_png(path, buf):
    raw = bytearray()
    stride = W * 3
    for y in range(H):
        raw.append(0)
        raw += buf[y * stride:(y + 1) * stride]
    ihdr = struct.pack(">IIBBBBB", W, H, 8, 2, 0, 0, 0)
    data = b"\x89PNG\r\n\x1a\n"
    data += chunk(b"IHDR", ihdr)
    data += chunk(b"IDAT", zlib.compress(bytes(raw), 9))
    data += chunk(b"IEND", b"")
    with open(path, "wb") as f:
        f.write(data)
    return len(data)


def main():
    buf = draw_poster()
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, "entry.png")
    size = write_png(path, buf)
    print("wrote %s (%d bytes, %dx%d)" % (path, size, W, H))


if __name__ == "__main__":
    main()
