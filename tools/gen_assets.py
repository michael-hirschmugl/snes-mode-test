#!/usr/bin/env python3
from pathlib import Path
from PIL import Image

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

# SNES BGR555 palette (16 colors), little-endian words
# index 0 background, 1 border, 2 cross, 3 center, rest unused
palette_bgr555 = [
    0x0000,  # black
    0x7FFF,  # white
    0x03E0,  # green
    0x7C00,  # red
] + [0x0000] * 12

palette_bytes = bytearray()
for c in palette_bgr555:
    palette_bytes.append(c & 0xFF)
    palette_bytes.append((c >> 8) & 0xFF)
(BUILD / "palette.bin").write_bytes(palette_bytes)


def tile_to_4bpp(tile_pixels):
    out = bytearray()
    for row in tile_pixels:
        p0 = 0
        p1 = 0
        p2 = 0
        p3 = 0
        for x, val in enumerate(row):
            bit = 7 - x
            p0 |= ((val >> 0) & 1) << bit
            p1 |= ((val >> 1) & 1) << bit
            p2 |= ((val >> 2) & 1) << bit
            p3 |= ((val >> 3) & 1) << bit
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
(BUILD / "tiles.chr").write_bytes(chr_data)

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
