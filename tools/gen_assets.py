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
CHAR_TILE_POS_8 = (14, 11)            # mode0/mode1: near screen center
# Mode 5 screen is 512x448 = 32x28 cells of 16x16 BG tiles. The four
# corner positions are nudged one cell inside the edge so they stay in
# the safe display area (bsnes-plus and real PAL TVs hide a few pixels
# of overscan at every border).
CHAR1_TILE_POS_16 = (1, 1)            # mode5 top-left
CHAR2_TILE_POS_16 = (30, 1)           # mode5 top-right
CHAR3_TILE_POS_16 = (1, 26)           # mode5 bottom-left
CHAR4_TILE_POS_16 = (30, 26)          # mode5 bottom-right

# VRAM tile indices for the 2x2 layout. In 16x16-tile modes the PPU auto-
# assembles (N, N+1, N+16, N+17) from a single tilemap entry, so each
# character occupies four VRAM tile slots in that exact pattern. The
# indices are chosen so that 8x8-tile modes can reference all four slots
# explicitly and 16x16-tile modes can reference only the top-left slot.
# Base indices step by 4 (mod 16) to avoid collisions with the N..N+17
# auto-read pattern, so each character gets its own four-slot block.
CHAR1_INDICES = (0, 1, 16, 17)        # default character (first 2x2 block)
CHAR2_INDICES = (4, 5, 20, 21)        # mode5 only: top-right tile
CHAR3_INDICES = (8, 9, 24, 25)        # mode5 only: bottom-left tile
CHAR4_INDICES = (12, 13, 28, 29)      # mode5 only: bottom-right tile
BLANK_INDEX = 2

# How many tiles each target uploads to VRAM. Mode0/Mode1 only need the
# default character (indices 0,1,16,17) plus the blank tile at index 2,
# so 18 tiles (0..17) cover everything used. Mode5 uses four characters
# whose highest VRAM index is 29 (CHAR4_BR_INDEX), so it must upload
# 30 tiles (indices 0..29).
DEFAULT_TILES_TO_UPLOAD = 18
MODE5_TILES_TO_UPLOAD = 30


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


def render_2bpp_character2_pixels():
    """Second 16x16 pixel art, also constrained to palette indices 0..3.

    Visually distinct from `render_2bpp_character_pixels` so the Mode 5
    demo clearly shows two different tiles side by side:

    - border of color 1 (white)
    - diagonal X through the tile in color 2 (green)
    - 2x2 center block in color 3 (blue)
    """
    pixels = [[0 for _ in range(CHAR_W)] for _ in range(CHAR_H)]
    for y in range(CHAR_H):
        for x in range(CHAR_W):
            if x in (0, CHAR_W - 1) or y in (0, CHAR_H - 1):
                pixels[y][x] = 1
            if x == y or x == CHAR_W - 1 - y:
                pixels[y][x] = 2
    for y in range(7, 9):
        for x in range(7, 9):
            pixels[y][x] = 3
    return pixels


def render_2bpp_character3_pixels():
    """Third 16x16 pixel art, palette indices 0..3 only.

    Visually distinct from the other three Mode 5 tiles:

    - border of color 1 (white)
    - solid 12x12 filled interior in color 3 (blue)
    """
    pixels = [[0 for _ in range(CHAR_W)] for _ in range(CHAR_H)]
    for y in range(CHAR_H):
        for x in range(CHAR_W):
            if x in (0, CHAR_W - 1) or y in (0, CHAR_H - 1):
                pixels[y][x] = 1
            elif 2 <= x <= CHAR_W - 3 and 2 <= y <= CHAR_H - 3:
                pixels[y][x] = 3
    return pixels


def render_2bpp_character4_pixels():
    """Fourth 16x16 pixel art, palette indices 0..3 only.

    Visually distinct from the other three Mode 5 tiles:

    - border of color 1 (white)
    - 2x2-block checkerboard of colors 2 (green) and 3 (blue) filling
      the 14x14 interior
    """
    pixels = [[0 for _ in range(CHAR_W)] for _ in range(CHAR_H)]
    for y in range(CHAR_H):
        for x in range(CHAR_W):
            if x in (0, CHAR_W - 1) or y in (0, CHAR_H - 1):
                pixels[y][x] = 1
            else:
                block_x = (x - 1) // 2
                block_y = (y - 1) // 2
                pixels[y][x] = 2 if (block_x + block_y) % 2 == 0 else 3
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


def build_vram_tiles(character_tile_sets, blank_tile, tiles_to_upload):
    """Lay out VRAM tile data for upload.

    character_tile_sets is a list of (quads, indices) pairs where:
      - quads is the 4-tile character produced by split_character_tiles
      - indices is a (tl, tr, bl, br) tuple giving VRAM tile slots

    Slots not populated by any character are filled with `blank_tile`.
    """
    tiles = [blank_tile] * tiles_to_upload
    for quads, (tl, tr, bl, br) in character_tile_sets:
        tiles[tl] = quads[0]
        tiles[tr] = quads[1]
        tiles[bl] = quads[2]
        tiles[br] = quads[3]
    return bytearray().join(tiles)


def build_tilemap(tile_pixels_size, placements):
    """Build a 32x32 BG tilemap that places one or more characters.

    `placements` is a list of (tile_pos, vram_indices) pairs, where:
      - tile_pos = (x, y) in tile units (8x8 or 16x16 pixels depending
        on the BG's configured tile size).
      - vram_indices = (tl, tr, bl, br) — the VRAM tile indices making
        up the character's 2x2 layout.

    tile_pixels_size = 8  -> each character writes four entries
                             (tl, tr, bl, br) into the tilemap.
    tile_pixels_size = 16 -> each character writes a single entry (the
                             top-left index); the PPU auto-reads
                             N, N+1, N+16, N+17 per tilemap entry, so
                             a single entry covers the whole 2x2 VRAM
                             tile block.
    """
    tm = [BLANK_INDEX] * (32 * 32)
    for (tile_x, tile_y), (tl, tr, bl, br) in placements:
        if tile_pixels_size == 8:
            base = tile_y * 32 + tile_x
            tm[base] = tl
            tm[base + 1] = tr
            tm[base + 32] = bl
            tm[base + 33] = br
        elif tile_pixels_size == 16:
            tm[tile_y * 32 + tile_x] = tl
        else:
            raise ValueError(
                f"unsupported tile_pixels_size {tile_pixels_size}"
            )
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


def build_preview(
    rendered_characters, palette_bgr555, bpp, tile_pixels_size, screen_size
):
    """Render a 1:1 preview of what the ROM should show, then upscale.

    rendered_characters is a list of (pixels, tile_pos) pairs giving
    each character's 16x16 pixel bitmap and its tilemap position.

    screen_size = (256, 224) for standard modes, (512, 448) for Mode 5
                  + interlace hi-res. The tile-unit-to-pixel origin is
                  derived from the same tile_pixels_size as
                  build_tilemap().
    """
    slots = PALETTE_COLORS[bpp]
    rgb = [bgr555_to_rgb(c) for c in palette_bgr555]
    while len(rgb) < slots:
        rgb.append((0, 0, 0))
    screen_w, screen_h = screen_size
    img = Image.new("RGB", (screen_w, screen_h), rgb[0])
    for pixels, (tile_x, tile_y) in rendered_characters:
        origin_x = tile_x * tile_pixels_size
        origin_y = tile_y * tile_pixels_size
        for y in range(CHAR_H):
            for x in range(CHAR_W):
                img.putpixel(
                    (origin_x + x, origin_y + y), rgb[pixels[y][x]]
                )
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
        "tile_pixels_size": 8,
        "screen_size": (256, 224),
        "tiles_to_upload": DEFAULT_TILES_TO_UPLOAD,
        "characters": [
            {
                "render_pixels": render_2bpp_character_pixels,
                "tile_pos": CHAR_TILE_POS_8,
                "vram_indices": CHAR1_INDICES,
            },
        ],
    },
    "mode1_4bpp": {
        "bpp": 4,
        "chr_name": "tiles.4bpp.chr",
        "palette": PALETTE_4BPP_BGR555,
        "tile_pixels_size": 8,
        "screen_size": (256, 224),
        "tiles_to_upload": DEFAULT_TILES_TO_UPLOAD,
        "characters": [
            {
                "render_pixels": render_4bpp_character_pixels,
                "tile_pos": CHAR_TILE_POS_8,
                "vram_indices": CHAR1_INDICES,
            },
        ],
    },
    "mode5_2bpp": {
        "bpp": 2,
        "chr_name": "tiles.2bpp.chr",
        "palette": PALETTE_2BPP_BGR555,
        # Mode 5 BG2 with BGMODE bit 5 set uses 16x16 BG tiles assembled
        # from the same N, N+1, N+16, N+17 VRAM layout as mode0.
        "tile_pixels_size": 16,
        # Mode 5 is horizontal hi-res; with interlace on, the effective
        # display is 512x448, so previews are rendered at that size.
        "screen_size": (512, 448),
        # Mode 5 uploads four characters (cross, X, filled square,
        # checkerboard) arranged at all four screen corners, so Mode 5's
        # VRAM must cover tile indices up to 29 inclusive.
        "tiles_to_upload": MODE5_TILES_TO_UPLOAD,
        "characters": [
            {
                "render_pixels": render_2bpp_character_pixels,
                "tile_pos": CHAR1_TILE_POS_16,
                "vram_indices": CHAR1_INDICES,
            },
            {
                "render_pixels": render_2bpp_character2_pixels,
                "tile_pos": CHAR2_TILE_POS_16,
                "vram_indices": CHAR2_INDICES,
            },
            {
                "render_pixels": render_2bpp_character3_pixels,
                "tile_pos": CHAR3_TILE_POS_16,
                "vram_indices": CHAR3_INDICES,
            },
            {
                "render_pixels": render_2bpp_character4_pixels,
                "tile_pos": CHAR4_TILE_POS_16,
                "vram_indices": CHAR4_INDICES,
            },
        ],
    },
}


def generate_target(name):
    spec = TARGETS[name]
    bpp = spec["bpp"]
    chr_name = spec["chr_name"]
    palette = spec["palette"]
    tile_pixels_size = spec["tile_pixels_size"]
    screen_size = spec["screen_size"]
    tiles_to_upload = spec["tiles_to_upload"]

    target_dir = BUILD / name
    target_dir.mkdir(parents=True, exist_ok=True)

    rendered = [
        (c["render_pixels"](), c["tile_pos"], c["vram_indices"])
        for c in spec["characters"]
    ]
    character_tile_sets = [
        (split_character_tiles(pixels, bpp), vram_indices)
        for pixels, _, vram_indices in rendered
    ]
    blank_tile = tile_to_bitplanes([[0] * 8 for _ in range(8)], bpp)

    placements = [
        (tile_pos, vram_indices) for _, tile_pos, vram_indices in rendered
    ]
    preview_characters = [
        (pixels, tile_pos) for pixels, tile_pos, _ in rendered
    ]

    (target_dir / "palette.bin").write_bytes(encode_palette(palette, bpp))
    (target_dir / chr_name).write_bytes(
        build_vram_tiles(character_tile_sets, blank_tile, tiles_to_upload)
    )
    (target_dir / "tilemap.bin").write_bytes(
        build_tilemap(tile_pixels_size, placements)
    )
    build_preview(
        preview_characters, palette, bpp, tile_pixels_size, screen_size
    ).save(target_dir / "preview.png")


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
