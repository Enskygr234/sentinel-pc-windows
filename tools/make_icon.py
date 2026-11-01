"""Uygulama simgesini (PNG + çok boyutlu ICO) bağımlılıksız üretir.

Kullanım: python tools/make_icon.py <çıktı_klasörü> [stil]
stil: "nova" (elmas) veya "sentinel" (nabız çizgisi)
"""
from __future__ import annotations

import math
import os
import struct
import sys
import zlib

PURPLE = (139, 92, 246)
BLUE = (59, 130, 246)


def _png(width: int, height: int, rgba: bytes) -> bytes:
    raw = b"".join(b"\x00" + rgba[y * width * 4:(y + 1) * width * 4] for y in range(height))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def _inside_rounded(x: float, y: float, s: float, r: float) -> bool:
    cx = min(max(x, r), s - r)
    cy = min(max(y, r), s - r)
    return (x - cx) ** 2 + (y - cy) ** 2 <= r * r


def _dist_to_segment(px, py, ax, ay, bx, by) -> float:
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def _foreground(style: str, u: float, v: float) -> bool:
    """u, v ∈ [0,1] — beyaz ön plan şekli."""
    if style == "sentinel":
        pts = [(0.18, 0.55), (0.36, 0.55), (0.44, 0.33), (0.54, 0.74), (0.62, 0.48), (0.82, 0.48)]
        return any(_dist_to_segment(u, v, *pts[i], *pts[i + 1]) < 0.045 for i in range(len(pts) - 1))
    # nova: elmas + iç boşluk
    d = abs(u - 0.5) + abs(v - 0.5)
    return d < 0.30 and not (d < 0.13)


def render(size: int, style: str, ss: int = 4) -> bytes:
    out = bytearray()
    big = size * ss
    radius = big * 0.22
    for y in range(size):
        for x in range(size):
            acc = [0.0, 0.0, 0.0, 0.0]
            for sy in range(ss):
                for sx in range(ss):
                    px, py = x * ss + sx + 0.5, y * ss + sy + 0.5
                    if not _inside_rounded(px, py, big, radius):
                        continue
                    t = (px + py) / (2 * big)
                    col = [PURPLE[i] + (BLUE[i] - PURPLE[i]) * t for i in range(3)]
                    if _foreground(style, px / big, py / big):
                        col = [255, 255, 255]
                    acc[0] += col[0]
                    acc[1] += col[1]
                    acc[2] += col[2]
                    acc[3] += 255
            n = ss * ss
            covered = acc[3] / 255  # kapsanan örnek sayısı
            if covered > 0:
                out += bytes([int(acc[0] / covered), int(acc[1] / covered), int(acc[2] / covered),
                              int(acc[3] / n)])
            else:
                out += b"\x00\x00\x00\x00"
    return bytes(out)


def make(out_dir: str, style: str = "nova") -> None:
    os.makedirs(out_dir, exist_ok=True)
    sizes = [16, 24, 32, 48, 64, 128, 256]
    images = {s: _png(s, s, render(s, style, 4 if s <= 64 else 2)) for s in sizes}
    with open(os.path.join(out_dir, "icon.png"), "wb") as fh:
        fh.write(images[256])
    header = struct.pack("<HHH", 0, 1, len(sizes))
    offset = 6 + 16 * len(sizes)
    entries, blobs = b"", b""
    for s in sizes:
        data = images[s]
        entries += struct.pack("<BBBBHHII", s % 256, s % 256, 0, 0, 1, 32, len(data), offset + len(blobs))
        blobs += data
    with open(os.path.join(out_dir, "icon.ico"), "wb") as fh:
        fh.write(header + entries + blobs)


if __name__ == "__main__":
    make(sys.argv[1] if len(sys.argv) > 1 else "assets", sys.argv[2] if len(sys.argv) > 2 else "nova")
