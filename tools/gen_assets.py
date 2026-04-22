#!/usr/bin/env python3
"""
SNES asset generator (supports 2bpp and 4bpp BG tile formats).

Three independent targets:

  mode0_2bpp/
    palette.bin       4-color 2bpp palette, 8 bytes (BGR555)
    tiles.2bpp.chr    2bpp tile data, 16 bytes per 8x8 tile
    tilemap.bin       32x32 BG1 tilemap (2-byte entries, format-agnostic)
    preview.png       expected screen preview (256x224, 3x upscaled)
    -> character uses palette indices 0..3 only (fits a 2bpp palette).

  mode1_4bpp/
    palette.bin       16-color 4bpp palette, 32 bytes (BGR555)
    tiles.4bpp.chr    4bpp tile data, 32 bytes per 8x8 tile
    tilemap.bin       32x32 BG1 tilemap (2-byte entries, format-agnostic)
    preview.png       expected screen preview (256x224, 3x upscaled)
    -> character uses ALL 16 palette indices (4x4 grid of 4x4 colored
       blocks) so the 4bpp path actually exercises 16 colors.

  mode5_2bpp/
    palette.bin       4-color 2bpp palette, 8 bytes (same art as mode0)
    tiles.2bpp.chr    2bpp tile data (same 18 tiles as mode0, layout 0,1,16,17)
    tilemap.bin       32x32 BG2 tilemap; ONE entry holds the whole character
                      because Mode 5 BG2 is configured with 16x16 tile size
                      (BGMODE bit 5) so the PPU auto-reads N, N+1, N+16, N+17.
    preview.png       expected screen preview (512x448, 2x upscaled)
    -> Mode 5 is horizontal hi-res (512 px) and this demo runs with
       interlace on, so the effective resolution is 512x448. The 16x16
       character therefore appears at half the physical size of the
       mode0 / mode1 previews; that is intentional.

Usage:
    python3 tools/gen_assets.py mode0_2bpp
    python3 tools/gen_assets.py mode1_4bpp
    python3 tools/gen_assets.py mode5_2bpp
    python3 tools/gen_assets.py all
"""
import argparse
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "build"

BYTES_PER_TILE = {2: 16, 4: 32}
PALETTE_COLORS = {2: 4, 4: 16}

CHAR_W, CHAR_H = 16, 16

# 4-color palette used by the 2bpp / Mode 0 target.
PALETTE_2BPP_BGR555 = [
    0x0000,  # 0 background (black)
    0x7FFF,  # 1 border     (white)
    0x03E0,  # 2 cross      (green)
    0x7C00,  # 3 center     (blue)
]

# 16-color palette used by the 4bpp / Mode 1 target. Each entry is a
# distinct BGR555 color so all 16 slots are visibly different on screen.
PALETTE_4BPP_BGR555 = [
    0x0000,  # 0  black (also tilemap background)
    0x7FFF,  # 1  white
    0x001F,  # 2  red
    0x01FF,  # 3  orange       (R=31, G=15)
    0x03FF,  # 4  yellow
    0x03E0,  # 5  green
    0x7FE0,  # 6  cyan
    0x7C00,  # 7  blue
    0x7C1F,  # 8  magenta
    0x7C0F,  # 9  purple       (R=15, B=31)
    0x000F,  # 10 dark red     (R=15)
    0x01E0,  # 11 dark green   (G=15)
    0x3C00,  # 12 dark blue    (B=15)
    0x4210,  # 13 dark grey    (R=G=B=16)
    0x6318,  # 14 light grey   (R=G=B=24)
    0x014F,  # 15 brown        (R=15, G=10)
]

# Default 2x2 tile character placement on the BG tilemap, expressed in
# tile-units. For 8x8-tile targets this is 8x8 pixel units, for 16x16-tile
# targets (Mode 5 BG2 with BGMODE bit 5 set) this is 16x16 pixel units.
CHAR_TILE_X_8 = 14
CHAR_TILE_Y_8 = 11
CHAR_TILE_X_16 = 15
CHAR_TILE_Y_16 = 13

# VRAM tile indices used by all modes (see README: 2x2 grid layout in VRAM).
# In 16x16-tile modes the PPU auto-assembles (N, N+1, N+16, N+17) from a
# single tilemap entry, which matches this exact layout so the same tile
# data works for both 8x8-tile and 16x16-tile BG modes.
CHAR_TL_INDEX = 0
CHAR_TR_INDEX = 1
BLANK_INDEX = 2
CHAR_BL_INDEX = 16
CHAR_BR_INDEX = 17
TILES_TO_UPLOAD = 18


def render_2bpp_character_pixels():
    """16x16 pixel art using only palette indices 0..3 (fits a 2bpp palette).

    - border of color 1
    - cross through the center in color 2
    - 4x4 center block in color 3
    """
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


def render_4bpp_character_pixels():
    """16x16 pixel art that uses ALL 16 palette indices (0..15).

    The tile is divided into a 4x4 grid of 4x4 colored blocks. Block
    (bx, by) paints palette index `by * 4 + bx`, so every 4bpp palette
    slot shows up as a visible 4x4 patch on screen.
    """
    pixels = [[0 for _ in range(CHAR_W)] for _ in range(CHAR_H)]
    for y in range(CHAR_H):
        for x in range(CHAR_W):
            block_y = y // 4
            block_x = x // 4
            pixels[y][x] = block_y * 4 + block_x
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


def build_tilemap(tile_pixels_size):
    """Build a 32x32 BG tilemap that places the character near center.

    tile_pixels_size = 8  -> four 8x8 entries (0,1,16,17) at (14,11)
    tile_pixels_size = 16 -> one 16x16 entry (index 0) at (15,13); in this
                             mode the PPU auto-reads N, N+1, N+16, N+17
                             per tilemap entry, so a single entry covers
                             the whole 2x2 VRAM tile block.
    """
    tm = [BLANK_INDEX] * (32 * 32)
    if tile_pixels_size == 8:
        base = CHAR_TILE_Y_8 * 32 + CHAR_TILE_X_8
        tm[base] = CHAR_TL_INDEX
        tm[base + 1] = CHAR_TR_INDEX
        tm[base + 32] = CHAR_BL_INDEX
        tm[base + 33] = CHAR_BR_INDEX
    elif tile_pixels_size == 16:
        tm[CHAR_TILE_Y_16 * 32 + CHAR_TILE_X_16] = CHAR_TL_INDEX
    else:
        raise ValueError(f"unsupported tile_pixels_size {tile_pixels_size}")
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


def build_preview(pixels, palette_bgr555, bpp, tile_pixels_size, screen_size):
    """Render a 1:1 preview of what the ROM should show, then upscale.

    screen_size = (256, 224) for standard modes, (512, 448) for Mode 5
                  + interlace hi-res. The character's pixel origin is
                  derived from the same tile-units as build_tilemap().
    """
    slots = PALETTE_COLORS[bpp]
    rgb = [bgr555_to_rgb(c) for c in palette_bgr555]
    while len(rgb) < slots:
        rgb.append((0, 0, 0))
    screen_w, screen_h = screen_size
    img = Image.new("RGB", (screen_w, screen_h), rgb[0])
    if tile_pixels_size == 8:
        origin_x = CHAR_TILE_X_8 * 8
        origin_y = CHAR_TILE_Y_8 * 8
    else:
        origin_x = CHAR_TILE_X_16 * 16
        origin_y = CHAR_TILE_Y_16 * 16
    for y in range(CHAR_H):
        for x in range(CHAR_W):
            img.putpixel((origin_x + x, origin_y + y), rgb[pixels[y][x]])
    # Smaller screens get 3x upscale; the 512x448 hi-res preview stays at
    # 2x so the PNG doesn't explode in size while still being inspectable.
    upscale = 3 if screen_w <= 256 else 2
    return img.resize((screen_w * upscale, screen_h * upscale), Image.NEAREST)


# ---------------------------------------------------------------------------
# Target registry
# ---------------------------------------------------------------------------

TARGETS = {
    "mode0_2bpp": {
        "bpp": 2,
        "chr_name": "tiles.2bpp.chr",
        "palette": PALETTE_2BPP_BGR555,
        "render_pixels": render_2bpp_character_pixels,
        "tile_pixels_size": 8,
        "screen_size": (256, 224),
    },
    "mode1_4bpp": {
        "bpp": 4,
        "chr_name": "tiles.4bpp.chr",
        "palette": PALETTE_4BPP_BGR555,
        "render_pixels": render_4bpp_character_pixels,
        "tile_pixels_size": 8,
        "screen_size": (256, 224),
    },
    "mode5_2bpp": {
        "bpp": 2,
        "chr_name": "tiles.2bpp.chr",
        "palette": PALETTE_2BPP_BGR555,
        "render_pixels": render_2bpp_character_pixels,
        # Mode 5 BG2 with BGMODE bit 5 set uses 16x16 BG tiles assembled
        # from the same N, N+1, N+16, N+17 VRAM layout as mode0.
        "tile_pixels_size": 16,
        # Mode 5 is horizontal hi-res; with interlace on, the effective
        # display is 512x448, so previews are rendered at that size.
        "screen_size": (512, 448),
    },
}


def generate_target(name):
    spec = TARGETS[name]
    bpp = spec["bpp"]
    chr_name = spec["chr_name"]
    palette = spec["palette"]
    pixels = spec["render_pixels"]()
    tile_pixels_size = spec["tile_pixels_size"]
    screen_size = spec["screen_size"]

    target_dir = BUILD / name
    target_dir.mkdir(parents=True, exist_ok=True)

    character_tiles = split_character_tiles(pixels, bpp)
    blank_tile = tile_to_bitplanes([[0] * 8 for _ in range(8)], bpp)

    (target_dir / "palette.bin").write_bytes(encode_palette(palette, bpp))
    (target_dir / chr_name).write_bytes(
        build_vram_tiles(character_tiles, blank_tile)
    )
    (target_dir / "tilemap.bin").write_bytes(build_tilemap(tile_pixels_size))
    build_preview(pixels, palette, bpp, tile_pixels_size, screen_size).save(
        target_dir / "preview.png"
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    parser.add_argument(
        "target",
        choices=list(TARGETS.keys()) + ["all"],
        help="which asset set to generate",
    )
    args = parser.parse_args()

    BUILD.mkdir(exist_ok=True)
    if args.target == "all":
        for name in TARGETS:
            generate_target(name)
    else:
        generate_target(args.target)


if __name__ == "__main__":
    main()
