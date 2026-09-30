"""Create the project's original multi-size ICO from its simple vector mark."""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "assets" / "statguard-desktop.ico"
PACKAGE_OUTPUT = ROOT / "src" / "statguard_desktop" / "assets" / "statguard-desktop.ico"


def _inside_polygon(x: float, y: float, points: tuple[tuple[float, float], ...]) -> bool:
    inside = False
    previous = points[-1]
    for current in points:
        x1, y1 = previous
        x2, y2 = current
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
        previous = current
    return inside


def _png(size: int) -> bytes:
    scale = 4
    pixels = bytearray(size * size * 4)
    shield = (
        (32, 3),
        (56, 12),
        (56, 29),
        (52, 42),
        (43, 52),
        (32, 61),
        (21, 52),
        (12, 42),
        (8, 29),
        (8, 12),
    )
    lines = (
        (18, 22, 46, 22, 2.0, (220, 236, 255, 255)),
        (18, 30, 36, 30, 2.0, (220, 236, 255, 255)),
        (18, 38, 29, 38, 2.0, (220, 236, 255, 255)),
        (34, 43, 39, 48, 2.5, (85, 214, 160, 255)),
        (39, 48, 49, 36, 2.5, (85, 214, 160, 255)),
    )
    for py in range(size):
        for px in range(size):
            rgb = [0, 0, 0]
            alpha = 0
            for sy in range(scale):
                for sx in range(scale):
                    x = (px + (sx + 0.5) / scale) * 64 / size
                    y = (py + (sy + 0.5) / scale) * 64 / size
                    color = (23, 59, 103, 255) if _inside_polygon(x, y, shield) else (0, 0, 0, 0)
                    for x1, y1, x2, y2, width, line_color in lines:
                        dx, dy = x2 - x1, y2 - y1
                        length_sq = dx * dx + dy * dy
                        t = max(0.0, min(1.0, ((x - x1) * dx + (y - y1) * dy) / length_sq))
                        if math.hypot(x - (x1 + t * dx), y - (y1 + t * dy)) <= width:
                            color = line_color
                    for channel in range(3):
                        rgb[channel] += color[channel]
                    alpha += color[3]
            i = (py * size + px) * 4
            samples = scale * scale
            pixels[i : i + 4] = bytes((*[channel // samples for channel in rgb], alpha // samples))

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    rows = b"".join(b"\x00" + pixels[y * size * 4 : (y + 1) * size * 4] for y in range(size))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(rows, 9))
        + chunk(b"IEND", b"")
    )


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    images = [(size, _png(size)) for size in (16, 32, 48, 256)]
    offset = 6 + 16 * len(images)
    entries = []
    payload = bytearray()
    for size, data in images:
        entries.append(
            struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        )
        payload.extend(data)
        offset += len(data)
    icon = struct.pack("<HHH", 0, 1, len(images)) + b"".join(entries) + payload
    OUTPUT.write_bytes(icon)
    PACKAGE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    PACKAGE_OUTPUT.write_bytes(icon)


if __name__ == "__main__":
    main()
