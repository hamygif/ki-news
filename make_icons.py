#!/usr/bin/env python3
"""Erzeugt die App-Icons (PNG) für KI News – nur mit der Standardbibliothek.
Muss nur einmal laufen; die Icons liegen danach in site/.
"""

import math
import os
import struct
import zlib

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "site")

# Buchstaben "KI" als Liniensegmente im Einheitsquadrat (0..1)
W = 0.052  # halbe Strichstärke
SEGMENTS = [
    ((0.27, 0.30), (0.27, 0.70)),   # K – senkrecht
    ((0.31, 0.53), (0.52, 0.30)),   # K – oben
    ((0.37, 0.47), (0.54, 0.70)),   # K – unten
    ((0.70, 0.30), (0.70, 0.70)),   # I
]
SPARK = (0.83, 0.22, 0.035)  # kleiner Akzentpunkt (x, y, r)

TOP = (59, 91, 219)     # #3b5bdb
BOTTOM = (124, 58, 237)  # #7c3aed
WHITE = (255, 255, 255)
SPARK_COL = (186, 230, 253)


def seg_dist(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - ax - t * dx, py - ay - t * dy)


def mix(c1, c2, t):
    return tuple(round(a + (b - a) * t) for a, b in zip(c1, c2))


def render(size):
    px = 1.0 / size
    rows = []
    for y in range(size):
        row = bytearray([0])  # PNG-Filter "None"
        v = (y + 0.5) / size
        for x in range(size):
            u = (x + 0.5) / size
            col = mix(TOP, BOTTOM, (u + v) / 2)
            d = min(seg_dist(u, v, a, b) for a, b in SEGMENTS) - W
            cov = max(0.0, min(1.0, 0.5 - d / px))
            if cov:
                col = mix(col, WHITE, cov)
            ds = math.hypot(u - SPARK[0], v - SPARK[1]) - SPARK[2]
            cov = max(0.0, min(1.0, 0.5 - ds / px))
            if cov:
                col = mix(col, SPARK_COL, cov)
            row += bytes(col)
        rows.append(bytes(row))
    raw = b"".join(rows)

    def chunk(kind, data):
        c = kind + data
        return struct.pack(">I", len(data)) + c + struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9))
            + chunk(b"IEND", b""))


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for name, size in [("apple-touch-icon.png", 180), ("icon-192.png", 192),
                       ("icon-512.png", 512), ("favicon.png", 64)]:
        with open(os.path.join(OUT_DIR, name), "wb") as f:
            f.write(render(size))
        print("✓", name)


if __name__ == "__main__":
    main()
