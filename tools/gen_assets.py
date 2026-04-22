#!/usr/bin/env python3
"""
SNES asset generator (4bpp ONLY).

This script is hard-wired to the SNES 4bpp tile format used by BG1/BG2 in
Mode 1. It produces:

  - build/palette.bin  : 16 BGR555 colors (exactly one 4bpp palette)
  - build/tiles.4bpp.chr : 4bpp tile data, 32 bytes per 8x8 tile
  - build/tilemap.bin  : 32x32 BG tilemap (little-endian word entries)
  - build/preview.png  : expected screen preview

It does NOT support 2bpp (e.g. Mode 1 BG3), 8bpp (e.g. Mode 3/4 BG1) or
any Mode-7 formats. Add a dedicated encoder if you need those.
"""
from pathlib import Path
from PIL import Image

BPP = 4
BYTES_PER_TILE_4BPP = 32
PALETTE_COLORS_4BPP = 16

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"
BUILD.mkdir(exist_ok=True)

W, H = 16, 16
pixels = [[0 for _ in range(W)] for _ in range(H)]

# Simple 16x16 icon: border + plus sign + center square
for y in range(H):
    for x in range(W):
        if x in (0, W - 1) or y in (0, H - 1):
            pixels[y][x] = 1
        if x == W // 2 or y == H // 2:
            pixels[y][x] = 2
for y in range(6, 10):
    for x in range(6, 10):
        pixels[y][x] = 3

# SNES BGR555 palette for 4bpp tiles (exactly 16 little-endian word colors).
# index 0 background, 1 border, 2 cross, 3 center, rest unused.
palette_bgr555 = [
    0x0000,  # black
    0x7FFF,  # white
    0x03E0,  # green
    0x7C00,  # red
] + [0x0000] * (PALETTE_COLORS_4BPP - 4)
assert len(palette_bgr555) == PALETTE_COLORS_4BPP

palette_bytes = bytearray()
for c in palette_bgr555:
    palette_bytes.append(c & 0xFF)
    palette_bytes.append((c >> 8) & 0xFF)
(BUILD / "palette.bin").write_bytes(palette_bytes)


def tile_to_4bpp(tile_pixels):
    """Encode an 8x8 tile (pixel values 0..15) to the SNES 4bpp format.

    Layout (32 bytes total per tile):
      offset 0x00..0x0F : 8 rows of plane 0 + plane 1 (2 bytes per row)
      offset 0x10..0x1F : 8 rows of plane 2 + plane 3 (2 bytes per row)
    """
    assert len(tile_pixels) == 8 and all(len(r) == 8 for r in tile_pixels)
    out = bytearray()
    for row in tile_pixels:
        p0 = 0
        p1 = 0
        for x, val in enumerate(row):
            bit = 7 - x
            p0 |= ((val >> 0) & 1) << bit
            p1 |= ((val >> 1) & 1) << bit
        out.append(p0)
        out.append(p1)
    for row in tile_pixels:
        p2 = 0
        p3 = 0
        for x, val in enumerate(row):
            bit = 7 - x
            p2 |= ((val >> 2) & 1) << bit
            p3 |= ((val >> 3) & 1) << bit
        out.append(p2)
        out.append(p3)
    assert len(out) == BYTES_PER_TILE_4BPP
    return out


# VRAM tile grid layout (tile viewer shows 16 tiles per row):
#   index  0 = character top-left,  1 = character top-right
#   index 16 = character bottom-left, 17 = character bottom-right
# This gives the character a true 2x2 grid layout in VRAM.
# We reserve one other tile as an explicit "blank" tile used to clear the
# rest of the screen (tilemap background). Using tile index 2 for that.
BLANK_TILE_INDEX = 2
TILES_TO_UPLOAD = 18  # enough to cover indices 0..17

character_tiles = []
for ty in range(2):
    for tx in range(2):
        tile = []
        for y in range(8):
            row = []
            for x in range(8):
                row.append(pixels[ty * 8 + y][tx * 8 + x])
            tile.append(row)
        character_tiles.append(tile_to_4bpp(tile))

blank_tile = tile_to_4bpp([[0 for _ in range(8)] for _ in range(8)])

vram_tiles = [blank_tile] * TILES_TO_UPLOAD
vram_tiles[0] = character_tiles[0]   # top-left
vram_tiles[1] = character_tiles[1]   # top-right
vram_tiles[16] = character_tiles[2]  # bottom-left
vram_tiles[17] = character_tiles[3]  # bottom-right

chr_data = bytearray().join(vram_tiles)
(BUILD / "tiles.4bpp.chr").write_bytes(chr_data)

tilemap = [BLANK_TILE_INDEX] * (32 * 32)
base = 11 * 32 + 14
tilemap[base] = 0
tilemap[base + 1] = 1
tilemap[base + 32] = 16
tilemap[base + 33] = 17

tilemap_bytes = bytearray()
for entry in tilemap:
    tilemap_bytes.append(entry & 0xFF)
    tilemap_bytes.append((entry >> 8) & 0xFF)
(BUILD / "tilemap.bin").write_bytes(tilemap_bytes)

# Preview PNG in full SNES resolution (256x224)
rgb = [
    (0, 0, 0),
    (255, 255, 255),
    (0, 255, 0),
    (255, 0, 0),
] + [(0, 0, 0)] * 12

img = Image.new("RGB", (256, 224), rgb[0])
origin_x = 14 * 8
origin_y = 11 * 8
for y in range(H):
    for x in range(W):
        img.putpixel((origin_x + x, origin_y + y), rgb[pixels[y][x]])

# 3x upscale for easier viewing
img = img.resize((256 * 3, 224 * 3), Image.NEAREST)
img.save(BUILD / "preview.png")
