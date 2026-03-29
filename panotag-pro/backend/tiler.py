"""Equirectangular tiling with overlap — tile boxes in original pixel space."""
from __future__ import annotations


def generate_tiles(
    img_w: int,
    img_h: int,
    tile_size: int = 1280,
    overlap: float = 0.20,
) -> list[tuple[int, int, int, int]]:
    """
    Returns (x0, y0, x2, y2) tile rectangles in full image coordinates.
    step = tile_size * (1 - overlap); covers image with standard panotag scan.
    """
    if img_w <= 0 or img_h <= 0:
        return []
    tw = min(tile_size, img_w)
    th = min(tile_size, img_h)
    step_x = max(1, int(tw * (1.0 - overlap)))
    step_y = max(1, int(th * (1.0 - overlap)))
    xs: list[int] = []
    x = 0
    while True:
        xs.append(x)
        if x + tw >= img_w:
            break
        x = min(x + step_x, img_w - tw)
    ys: list[int] = []
    y = 0
    while True:
        ys.append(y)
        if y + th >= img_h:
            break
        y = min(y + step_y, img_h - th)
    out: list[tuple[int, int, int, int]] = []
    for y0 in ys:
        for x0 in xs:
            x2 = min(x0 + tw, img_w)
            y2 = min(y0 + th, img_h)
            out.append((x0, y0, x2, y2))
    return out
