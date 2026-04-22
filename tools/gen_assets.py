#!/usr/bin/env python3
"""
SNES asset generator (supports 2bpp and 4bpp BG tile formats).

Produces two asset sets:

  build/mode1_4bpp/
    palette.bin       16-color 4bpp palette, 32 bytes (BGR555)
    tiles.4bpp.chr    4bpp tile data, 32 bytes per 8x8 tile
    tilemap.bin       32x32 BG1 tilemap (2-byte entries, format-agnostic)
    preview.png       expected screen preview (256x224, 3x upscaled)

  build/mode0_2bpp/
    palette.bin       4-color 2bpp palette, 8 bytes (BGR555)
    tiles.2bpp.chr    2bpp tile data, 16 bytes per 8x8 tile
    tilemap.bin       32x32 BG1 tilemap (2-byte entries, format-agnostic)
    preview.png       expected screen preview (256x224, 3x upscaled)

The pixel art source uses palette indices 0..3 only, so it fits both 2bpp
(indices 0..3) and 4bpp (indices 0..15) encoders without modification.
"""
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"

BYTES_PER_TILE = {2: 16, 4: 32}
PALETTE_COLORS = {2: 4, 4: 16}

# Shared character design (values 0..3).
CHAR_W, CHAR_H = 16, 16

# Shared palette: we keep it to 4 colors so the same data works for both bpp.
PALETTE_BGR555 = [
    0x0000,  # 0 background, black
    0x7FFF,  # 1 border, white
    0x03E0,  # 2 cross, green
    0x7C00,  # 3 center, red
]

# 2x2 tile character placement on the BG1 tilemap.
CHAR_TILE_X = 14
CHAR_TILE_Y = 11

# VRAM tile indices used by both modes (see README: 2x2 grid layout in VRAM).
CHAR_TL_INDEX = 0
CHAR_TR_INDEX = 1
BLANK_INDEX = 2
CHAR_BL_INDEX = 16
CHAR_BR_INDEX = 17
TILES_TO_UPLOAD = 18


def render_character_pixels():
    """Return a 16x16 pixel array using only palette indices 0..3."""
    pixels = [[0 for _ in range(CHAR_W)] for _ in range(CHAR_H)]
    for y in range(CHAR_H):
        for x in range(CHAR_W):
            if x in (0, CHAR_W - 1) or y in (0, CHAR_H - 1):
                pixels[y][x] = 1
            if x == CHAR_W // 2 or y == CHAR_H // 2:
                pixels[y][x] = 2
    for y in range(6, 10):
        for x in range(6, 10):
            pixels[y][x] = 3
    return pixels


def tile_to_bitplanes(tile_pixels, bpp):
    """Encode an 8x8 tile to the SNES 2bpp or 4bpp tile format.

    2bpp (16 bytes/tile):
      off 0x00..0x0F : 8 rows of (plane0, plane1)

    4bpp (32 bytes/tile):
      off 0x00..0x0F : 8 rows of (plane0, plane1)
      off 0x10..0x1F : 8 rows of (plane2, plane3)
    """
    assert bpp in BYTES_PER_TILE
    max_val = (1 << bpp) - 1
    assert len(tile_pixels) == 8 and all(len(r) == 8 for r in tile_pixels)
    for row in tile_pixels:
        assert all(0 <= v <= max_val for v in row), \
            f"pixel value out of range for {bpp}bpp"

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
    if bpp == 4:
        for row in tile_pixels:
            p2 = 0
            p3 = 0
            for x, val in enumerate(row):
                bit = 7 - x
                p2 |= ((val >> 2) & 1) << bit
                p3 |= ((val >> 3) & 1) << bit
            out.append(p2)
            out.append(p3)
    assert len(out) == BYTES_PER_TILE[bpp]
    return out


def encode_palette(colors_bgr555, bpp):
    expected = PALETTE_COLORS[bpp]
    colors = list(colors_bgr555)
    if len(colors) > expected:
        raise ValueError(
            f"palette has {len(colors)} colors, too many for {bpp}bpp "
            f"(max {expected})"
        )
    colors += [0x0000] * (expected - len(colors))
    out = bytearray()
    for c in colors:
        out.append(c & 0xFF)
        out.append((c >> 8) & 0xFF)
    assert len(out) == expected * 2
    return out


def split_character_tiles(pixels, bpp):
    quads = []
    for ty in range(2):
        for tx in range(2):
            tile = [
                [pixels[ty * 8 + y][tx * 8 + x] for x in range(8)]
                for y in range(8)
            ]
            quads.append(tile_to_bitplanes(tile, bpp))
    return quads


def build_vram_tiles(character_tiles, blank_tile):
    tiles = [blank_tile] * TILES_TO_UPLOAD
    tiles[CHAR_TL_INDEX] = character_tiles[0]
    tiles[CHAR_TR_INDEX] = character_tiles[1]
    tiles[CHAR_BL_INDEX] = character_tiles[2]
    tiles[CHAR_BR_INDEX] = character_tiles[3]
    return bytearray().join(tiles)


def build_tilemap():
    tm = [BLANK_INDEX] * (32 * 32)
    base = CHAR_TILE_Y * 32 + CHAR_TILE_X
    tm[base] = CHAR_TL_INDEX
    tm[base + 1] = CHAR_TR_INDEX
    tm[base + 32] = CHAR_BL_INDEX
    tm[base + 33] = CHAR_BR_INDEX
    out = bytearray()
    for entry in tm:
        out.append(entry & 0xFF)
        out.append((entry >> 8) & 0xFF)
    return out


def bgr555_to_rgb(c):
    r = (c & 0x1F) * 255 // 31
    g = ((c >> 5) & 0x1F) * 255 // 31
    b = ((c >> 10) & 0x1F) * 255 // 31
    return (r, g, b)


def build_preview(pixels, palette_bgr555):
    rgb = [bgr555_to_rgb(c) for c in palette_bgr555]
    while len(rgb) < 4:
        rgb.append((0, 0, 0))
    img = Image.new("RGB", (256, 224), rgb[0])
    origin_x = CHAR_TILE_X * 8
    origin_y = CHAR_TILE_Y * 8
    for y in range(CHAR_H):
        for x in range(CHAR_W):
            img.putpixel((origin_x + x, origin_y + y), rgb[pixels[y][x]])
    return img.resize((256 * 3, 224 * 3), Image.NEAREST)


def generate_target(name, bpp, chr_name):
    target_dir = BUILD / name
    target_dir.mkdir(parents=True, exist_ok=True)

    pixels = render_character_pixels()
    character_tiles = split_character_tiles(pixels, bpp)
    blank_tile = tile_to_bitplanes([[0] * 8 for _ in range(8)], bpp)

    (target_dir / "palette.bin").write_bytes(
        encode_palette(PALETTE_BGR555, bpp)
    )
    (target_dir / chr_name).write_bytes(
        build_vram_tiles(character_tiles, blank_tile)
    )
    (target_dir / "tilemap.bin").write_bytes(build_tilemap())
    build_preview(pixels, PALETTE_BGR555).save(target_dir / "preview.png")


def main():
    BUILD.mkdir(exist_ok=True)
    generate_target("mode1_4bpp", bpp=4, chr_name="tiles.4bpp.chr")
    generate_target("mode0_2bpp", bpp=2, chr_name="tiles.2bpp.chr")


if __name__ == "__main__":
    main()
