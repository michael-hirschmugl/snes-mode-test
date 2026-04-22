# SNES Tile Test Demos (PAL)

Four minimal Super Nintendo demos written in cc65 assembly (`ca65` / `ld65`)
that show how to:

- initialize the console in a hardware-safe way (force blank, IRQ/NMI off,
  DMA off, clear WRAM / VRAM / CGRAM),
- enable a specific BG mode,
- with **one single background layer**,
- display either one or more **16×16 characters** on screen (Mode 0 /
  Mode 1 show a single centered character; the `mode5_2bpp` demo shows
  four distinct characters, one nudged into each screen corner) **or**
  a full-screen 512×448 wallpaper generated from a PNG (the
  `mode5_4bpp` / wallpaper demo).

The project ships four complete builds that differ in BG mode, tile
format, tile size and screen resolution, plus one opt-in build that
turns an arbitrary user-supplied image into a full-screen Mode 1
background:

| ROM                                  | Mode   | BG used | Tile format | BG tile size  | Display    | Contents                       | Extras             |
| ------------------------------------ | ------ | ------- | ----------- | ------------- | ---------- | ------------------------------ | ------------------ |
| `build/mode1_pal_demo.sfc`           | Mode 1 | BG1     | 4bpp        | 8×8 (2×2 ch)  | 256×224    | 1 character (center)           | —                  |
| `build/mode0_pal_demo.sfc`           | Mode 0 | BG1     | 2bpp        | 8×8 (2×2 ch)  | 256×224    | 1 character (center)           | —                  |
| `build/mode5_pal_demo.sfc`           | Mode 5 | BG2     | 2bpp        | 16×16 (1 ch)  | 512×448    | 4 characters (corners)         | hi-res + interlace |
| `build/mode5_wallpaper_pal_demo.sfc` | Mode 5 | BG1     | 4bpp        | 16×16 (dense) | 512×448    | full-screen wallpaper (Tux)    | hi-res + interlace |
| `build/mode1_image_pal_demo.sfc` *(opt-in)* | Mode 1 | BG1 | 4bpp   | 8×8 (dense)   | 256×224    | full-screen user image         | —                  |

All ROMs target **LoROM / PAL** consoles, run in `bsnes` / `bsnes-plus` and
boot on real hardware (e.g. via a flash cart).

### ROM header / real hardware

Each `.sfc` is exactly **32 KiB** LoROM with no SRAM, no coprocessor, and a
PAL destination code. The internal header (bank 00, `$FFC0-$FFDF`) advertises:
map-mode `$20` (LoROM SlowROM), cart-type `$00` (ROM only), ROM-size `$05`
(2^5 KiB = 32 KiB), SRAM-size `$00`, destination `$02` (Europe), fixed-value
`$00` (old-style header), and a post-link checksum / complement written by
`tools/fix_checksum.py` such that `checksum XOR complement = $FFFF` and
`sum(ROM_bytes) mod $10000 = checksum`. The reset path is Emu-RESET at
`$FFFC` pointing to `$8000`; native RESET does not exist and is left zero.
No PAL-specific setup is needed — the PPU runs at 50 Hz on PAL hardware
regardless. Copy a `.sfc` to an EverDrive / SD2SNES / FXPak Pro on a PAL
SNES and it boots.

In bsnes-plus' manifest viewer these ROMs show the minimal LoROM descriptor
(`<cartridge region='PAL'><rom><map .../></rom></cartridge>` with two
`linear` maps for banks `$00-$7D` and `$80-$FF`). There is no `<ram>` block
because cart-type is `$00`; that is expected and complete.

## Project layout

```
main_mode1_4bpp.s      # 65816 asm: Mode 1, 4bpp BG1 demo
main_mode0_2bpp.s      # 65816 asm: Mode 0, 2bpp BG1 demo
main_mode5_2bpp.s      # 65816 asm: Mode 5, 2bpp BG2 demo (16x16 tiles, interlace)
main_mode5_4bpp.s      # 65816 asm: Mode 5, 4bpp BG1 full-screen wallpaper (16x16 tiles, interlace)
main_mode1_image_4bpp.s # 65816 asm: Mode 1, 4bpp BG1 full-screen image (opt-in; reads build/mode1_image/)
snes.cfg               # ld65 memory/segment config (LoROM, shared)
Makefile               # builds all four ROMs
assets/
  linux_wallpaper.jpg               # source wallpaper (any aspect)
  linux_wallpaper_512x448_right.png # cropped to 512x448 (right-anchored)
  linux_wallpaper_512x448_right_4bpp.png # pre-quantised 16-color version (used by mode5_4bpp)
  linux_wallpaper_512x448_right_2bpp.png # pre-quantised 4-color version
tools/
  gen_assets.py        # 2bpp + 4bpp encoder, palette / tilemap / preview generator;
                       # also hosts the mode5_image pipeline (PNG/JPG -> dense-packed Mode 5 assets)
  crop_image.py        # scale + crop + palette-reduce helper (standalone or imported)
  fix_checksum.py      # writes correct SNES header checksum/complement
build/
  mode1_pal_demo.sfc            # final Mode 1 ROM
  mode0_pal_demo.sfc            # final Mode 0 ROM
  mode5_pal_demo.sfc            # final Mode 5 ROM (BG2, 4 corner characters)
  mode5_wallpaper_pal_demo.sfc  # final Mode 5 ROM (BG1, full-screen wallpaper)
  mode1_4bpp/
    palette.bin        # 4bpp palette: 16 colors, BGR555, 32 bytes
    tiles.4bpp.chr     # 4bpp tile data: 18 tiles x 32 bytes
    tilemap.bin        # 32x32 BG1 tilemap (2-byte entries, format-agnostic)
    preview.png        # expected picture (3x upscaled)
  mode0_2bpp/
    palette.bin        # 2bpp palette:  4 colors, BGR555,  8 bytes
    tiles.2bpp.chr     # 2bpp tile data: 18 tiles x 16 bytes
    tilemap.bin        # 32x32 BG1 tilemap (2-byte entries, format-agnostic)
    preview.png        # expected picture (3x upscaled)
  mode5_2bpp/
    palette.bin        # same bytes as mode0_2bpp/palette.bin
    tiles.2bpp.chr     # 2bpp tile data: 24 tiles x 16 bytes = 384 bytes
                       # (four dense-packed 16x16 characters + blank slot)
    tilemap.bin        # 32x32 BG2 tilemap; FOUR entries (one per screen corner)
    preview.png        # expected picture for 512x448 (2x upscaled)
  mode5_wallpaper_4bpp/
    palette.bin        # 4bpp palette: 16 colors, BGR555, 32 bytes
    tiles.4bpp.chr     # 4bpp tile data: dense-packed flip-dedup'd super-tiles
                       # (currently 768 8x8 slots x 32 bytes = 24576 bytes)
    tilemap.bin        # 32x32 BG1 tilemap; 32x28 visible entries + blank padding
    preview.png        # expected picture for 512x448 (2x upscaled, after dedup)
  mode1_image/         # opt-in, produced by `make mode1_image_demo ...`
    palette.bin        # 4bpp palette derived from the user-supplied image
    tiles.4bpp.chr     # dense-packed 8x8 tiles after flip-dedup (variable size)
    tilemap.bin        # 32x32 BG1 tilemap, 32x28 visible entries
    preview.png        # 1:1 preview of the quantised 256x224 image
```

## Requirements

- `cc65` (provides `ca65` and `ld65`) on PATH
- Python 3 with `Pillow` (for the asset generator and preview PNG)
- optional: `bsnes` / `bsnes-plus` for testing

## Build

```bash
make
```

The four ROMs appear at `build/mode1_pal_demo.sfc`,
`build/mode0_pal_demo.sfc`, `build/mode5_pal_demo.sfc` and
`build/mode5_wallpaper_pal_demo.sfc`.

## Clean

```bash
make clean
```

## Technical details

### ROM headers

All ROMs share the same LoROM / PAL configuration:

- Map mode: `$20` (LoROM, SlowROM)
- Destination: `$02` (Europe / PAL)
- Titles: `MODE1 16X16 PAL DEMO` / `MODE0 16X16 PAL DEMO` /
  `MODE5 16X16 PAL DEMO` / `MODE5 4BPP PAL WALL`
- Checksum and complement are written automatically by
  `tools/fix_checksum.py` after linking.

### Init sequence (summary, shared by all demos)

1. `sei` / `clc` / `xce` — switch to 65816 native mode
2. 16-bit A/X/Y, stack set to `$1FFF`
3. `INIDISP = $80` — force blank
4. `NMITIMEN`, `HDMAEN`, `MDMAEN`, `WRIO`, APU ports cleared
5. WRAM (128 KiB), VRAM (64 KiB), CGRAM (512 B) cleared via DMA
6. `BGMODE` and per-BG tilemap/char base registers programmed for the target
   mode; BG tilemap @ word `$1000`, BG char base @ word `$0000`
7. Palette, tiles and tilemap uploaded via DMA
8. `TM` (and `TS` for Mode 5 hi-res) programmed to show exactly one BG
9. `INIDISP = $0F` — force blank off, full brightness
10. Main loop: `wai` / `bra` (nothing to do)

Differences between the four demos:

| Step            | Mode 1 (4bpp, BG1)  | Mode 0 (2bpp, BG1)  | Mode 5 (2bpp, BG2)                  | Mode 5 wallpaper (4bpp, BG1)             |
| --------------- | ------------------- | ------------------- | ----------------------------------- | ---------------------------------------- |
| `BGMODE`        | `$01`               | `$00`               | `$25` (mode 5 + BG2 16×16 tiles)    | `$15` (mode 5 + BG1 16×16 tiles)         |
| Palette upload  | 32 bytes, 16 colors | 8 bytes, 4 colors   | 8 bytes, 4 colors                   | 32 bytes, 16 colors                      |
| Tile upload     | 576 bytes (`$0240`) | 288 bytes (`$0120`) | 384 bytes (`$0180`)                 | 24576 bytes (`$6000`)                    |
| Tile count      | 18 tiles            | 18 tiles            | 24 tiles (covers four characters)   | 768 tiles (dense-packed super-tiles)     |
| Tile size       | 32 B (4 bitplanes)  | 16 B (2 bitplanes)  | 16 B (2 bitplanes)                  | 32 B (4 bitplanes)                       |
| Tilemap base    | word `$1000`        | word `$1000`        | word `$1000` (`BG2SC = $10`)        | word `$3000` (`BG1SC = $30`)             |
| `TM` / `TS`     | `$01` / `$00`       | `$01` / `$00`       | `$02` / `$02` (BG2 on main + sub)   | `$01` / `$01` (BG1 on main + sub)        |
| `SETINI`        | `$00`               | `$00`               | `$01` (interlace on)                | `$01` (interlace on)                     |

Note on Mode 5 BG2 16×16 tile mode: a single tilemap entry points at tile
index `N` and the PPU auto-reads `N, N+1, N+16, N+17` as the four 8×8
sub-tiles of a 16×16 screen block. The Mode 0 / Mode 1 VRAM layout
(character at indices `0, 1, 16, 17`) is byte-compatible with that
auto-read, so Mode 5's first character is the same cross tile used by
the other builds. Mode 5 dense-packs three further characters right
next to it at indices `(2,3,18,19)`, `(4,5,20,21)` and `(6,7,22,23)`
(step of two — each character sits in the next free `N, N+1, N+16, N+17`
block without gaps), so it needs `tiles.2bpp.chr` with 24 tiles /
384 bytes. Slot `8` is reserved as the transparent super-tile used by
all "empty" tilemap entries. The palette stays identical to Mode 0;
only `tiles.2bpp.chr` and `tilemap.bin` differ.

### VRAM tile layout

Tiles as seen in the tile viewer (16 tiles per row) — each character
is stored as a true 2×2 block so both 8×8 and 16×16 BG modes can
reference it with the same VRAM layout.

Mode 0 / Mode 1 (one character):

```
index  0 = character top-left
index  1 = character top-right
index  8 = blank tile (used as tilemap background)
index 16 = character bottom-left
index 17 = character bottom-right
```

Mode 5 (four characters, same N, N+1, N+16, N+17 pattern, dense-packed
with each 2×2 block only 2 indices apart):

```
indices  0, 1, 16, 17 = character 1 (cross)
indices  2, 3, 18, 19 = character 2 (diagonal X)
indices  4, 5, 20, 21 = character 3 (filled square)
indices  6, 7, 22, 23 = character 4 (checkerboard)
index            8    = blank tile (transparent 16x16 super-tile;
                         auto-reads 8, 9, 24, 25 — all zero)
```

For the 8×8-tile modes (Mode 0 / Mode 1), the tilemap is filled with
index `8` everywhere and the center (tile position `14,11`) holds the
four character indices as four separate tilemap entries. For Mode 5
(BG2 16×16-tile mode), the tilemap is still filled with index `8`
everywhere, but **four** entries at tile positions `(1,1)`, `(30,1)`,
`(1,26)` and `(30,26)` (in 16×16-tile units) hold the top-left index
of each character, and the PPU auto-assembles the four 8×8 sub-tiles
into the on-screen 16×16 block. The corner positions are nudged one
16×16 cell inside the edge of the 512×448 screen so they stay outside
the overscan mask that bsnes-plus and real PAL TVs hide at the screen
borders.

### bsnes-plus Tilemap Viewer quirk (Mode 5 hires + 16×16)

On hardware and in the emulator output window everything is correct.
The bsnes-plus *Tilemap Viewer* however renders each Mode 5 hires 16×16
tilemap cell as **32×16 px** by reading eight VRAM tiles per entry
(`c, c+1, c+1, c+2 / c+16, c+17, c+17, c+18`) instead of the hardware's
four. See
[`tilemap-renderer.cpp`](https://github.com/devinacker/bsnes-plus/blob/master/bsnes/ui-qt/debugger/ppu/tilemap-renderer.cpp)
(`drawMapTile` + `drawMap8pxTile`). With the dense-packed tileset the
extra `c+2 / c+18` read lands on the next character's left column, so
three of the four corners appear in the Viewer with a ghost of their
neighbour glued to the right. Empty cells (`BLANK_INDEX = 8`) stay
clean because tiles 8–10 and 24–26 are all zero. Real Mode 5 hires
games that dense-pack their BG2 tileset would trigger the same quirk in
this Viewer; `docs/AI-README.md` has the full per-corner breakdown.

### Why `tilemap.bin` has no bit-depth suffix

The SNES tilemap entry format is bit-depth **agnostic** — every entry is a
16-bit word with the same layout (`vhopppcc cccccccc`: flip flags, priority,
3-bit palette, 10-bit tile index). The actual bit depth comes from the
`BGMODE` register and the per-layer char base (`BGxNBA`). The PPU
multiplies the tile index internally by 16/32/64 bytes depending on the
layer's 2bpp/4bpp/8bpp setting. That is why the tilemap file is the same
byte-for-byte in the Mode 1 / 4bpp and Mode 0 / 2bpp builds, and is
named without a bit-depth qualifier. Mode 5 has a different
`tilemap.bin` not because of the bit depth but because BG2 is configured
with 16×16 tile size, which changes the *layout* of entries (one entry
per 16×16 block instead of four per 2×2 group of 8×8 tiles).

### Asset generator (`tools/gen_assets.py`)

`gen_assets.py` is generic over bit depth: a single
`tile_to_bitplanes(pixels, bpp)` encoder handles both the 2bpp
(16 bytes/tile, planes 0..1) and 4bpp (32 bytes/tile, planes 0..3)
SNES tile formats.

The script takes the target as a CLI argument and writes exactly one
asset set per invocation:

```bash
python3 tools/gen_assets.py mode0_2bpp   # 4-color palette, indices 0..3
python3 tools/gen_assets.py mode1_4bpp   # 16-color palette, indices 0..15
python3 tools/gen_assets.py mode5_2bpp   # 4 dense-packed 16x16 characters + blank
python3 tools/gen_assets.py all          # regenerate all three static targets
```

Each static target has its **own** palette and pixel art (the 2bpp
builds stay within 4 palette slots while the 4bpp build actually
exercises all 16 slots, rendered as a 4×4 grid of 4×4 colored blocks,
one per palette index). Every target declares a list of characters
(render function + tilemap position + VRAM indices) plus its own
`tiles_to_upload` count, so Mode 0 and Mode 1 carry one character each
while Mode 5 carries four. The `mode5_2bpp` target shares its palette
bytes with `mode0_2bpp` but generates a bigger `tiles.2bpp.chr` and a
different `tilemap.bin` (plus a 512×448 preview). The `Makefile`
invokes the script once per target, so `make` only regenerates the
asset set that is out of date.

## Full-screen image pipelines

`gen_assets.py` has two **dynamic** pipelines that turn arbitrary
JPG/PNG images into ready-to-play SNES assets. Both produce the same
`{palette.bin, tiles.<bpp>bpp.chr, tilemap.bin, preview.png}` quartet
under `build/<name>/`; the difference is the BG layout they target and
therefore which kinds of images they can represent.

Pick the pipeline by answering one question: **how unique is the
image?**

- If the image has lots of repetition or is low-detail (tile-art
  wallpaper, pixel art, UI screens, logos), use `mode5_image` — you
  get the full 512×448 hi-res canvas.
- If every 16×16 region is different (photos, realistic artwork),
  use `mode1_image` — you trade the hi-res canvas for 256×224 but
  can display fully-unique content.

### Why Mode 5 has a hard limit for "every region different"

This is a hardware constraint, not a tool limitation. Two SNES budgets
apply to every BG layer:

1. **Tilemap index width is 10 bits per entry (`0..1023`)**. A BG can
   reference at most 1024 distinct 8×8 VRAM tiles via its tilemap,
   regardless of VRAM size.
2. **VRAM is 64 KiB total** and must hold tile data + tilemap(s) +
   anything else the PPU reads. At 4bpp a tile is 32 bytes, so
   1024 unique tiles = 32 KiB.

Apply this to a **fully unique** full-screen background:

|                        | Mode 1 (256×224, BG1 8×8, 4bpp) | Mode 5 hi-res + interlace (512×448, BG1 4bpp) |
| ---------------------- | ------------------------------: | --------------------------------------------: |
| screen in 8×8 tiles    | 32 × 28 = **896** tiles         | 64 × 56 = **3584** tiles                      |
| screen in 16×16 blocks | — (Mode 1 uses 8×8)             | 32 × 28 = 896 super-tiles × 4 = 3584 8×8 tiles |
| 10-bit index limit     | 896 ≤ 1024 ✅                    | 3584 ≫ 1024 ❌                                 |
| 4bpp VRAM needed       | 896 × 32 B = 28 KiB ✅           | 3584 × 32 B = 112 KiB ❌ (> 64 KiB VRAM)      |

Consequence: **a fully unique 512×448 image cannot be shown on a
single Mode 5 BG layer.** Real Mode 5 backgrounds always rely on
visual repetition (patterns, symmetry, tile reuse) plus the
flip-dedup bits in the tilemap word; they don't try to store every
region independently. `mode5_image` reflects this — it aborts with
a clear message when the deduped super-tile count overflows the
10-bit index budget.

A fully unique **256×224** image, on the other hand, fits comfortably
on Mode 1 BG1 with room to spare: 896 tiles is below the 1024-index
limit and 28 KiB of tile data leaves ~36 KiB of VRAM free for the
tilemap and other state. That's what `mode1_image` exploits.

### `mode5_image` — full-screen Mode 5 background from a PNG / JPG

The `mode5_image` target (`gen_assets.py mode5_image`) targets **BG1
in Mode 5** with 16×16 tile size (BGMODE bit 4) at 512×448 hi-res +
interlace. It is the pipeline that feeds `mode5_wallpaper_pal_demo.sfc`.

```bash
python3 tools/gen_assets.py mode5_image \
    --source assets/linux_wallpaper_512x448_right_4bpp.png \
    --bpp 4 \
    --name mode5_wallpaper_4bpp
```

Steps:

1. Scale + crop + palette-quantise the source to a 512×448 indexed
   image with `2**bpp` colours (via `tools/crop_image.py`,
   Median-Cut + Floyd–Steinberg dithering).
2. Slice into 32 × 28 = 896 **16×16 super-tiles** (each super-tile
   is 4 × 8×8 tiles in `TL, TR, BL, BR` order).
3. Dedupe across identity / H / V / HV flips — the tilemap word
   already encodes H/V flip bits, so mirrored regions reuse the same
   VRAM slot "for free".
4. Dense-pack unique super-tile `k` at VRAM base index
   `(k // 8) * 32 + (k % 8) * 2`, so 8 super-tiles share every pair
   of tile-viewer rows. A reserved blank super-tile follows the last
   unique one and is referenced by the 4 off-screen tilemap rows
   (`y = 28..31`).
5. Emit `palette.bin` (BGR555), `tiles.<bpp>bpp.chr`, `tilemap.bin`
   (flip bits set per dedup result) and a 2× upscaled `preview.png`.

If the dedupe still leaves more unique super-tiles than the 10-bit
index budget allows, the tool aborts with a diagnostic that prints
the actually needed index vs. the 1023 limit. In that case either
reduce colour count, use a less detail-heavy source, switch to
`mode1_image`, or split the image across multiple BG layers.

The Makefile's `MODE5_WALLPAPER_ASSETS` rule wires
`assets/linux_wallpaper_512x448_right_4bpp.png` through this pipeline
automatically and embeds the result into `main_mode5_4bpp.s`.

### `mode1_image` — full-screen Mode 1 background from a PNG / JPG

The `mode1_image` target (`gen_assets.py mode1_image`) targets
**BG1 in Mode 1** with 8×8 tile size at 256×224 standard resolution.
Because each tilemap entry is one 8×8 tile (no 16×16 auto-read
grouping) and the screen fits in 896 tiles, a fully unique photo or
painting is representable as long as the flip-dedup + quantise stage
stays below the 1024-index budget.

```bash
python3 tools/gen_assets.py mode1_image \
    --source path/to/your_image.jpg \
    --bpp 4 \
    --crop-align center \
    --name mode1_image
```

Steps:

1. Scale + crop + palette-quantise to a 256×224 indexed image.
2. Slice into 32 × 28 = 896 plain **8×8 tiles**.
3. Dedupe across identity / H / V / HV flips.
4. Dense-pack (no `N, N+1, N+16, N+17` grouping — in 8×8-tile mode
   each tilemap entry is one 8×8 tile index).
5. Emit `palette.bin`, `tiles.<bpp>bpp.chr` (dense, no padding),
   `tilemap.bin` and a 1:1 `preview.png`.

Typical photographic input quantised to 16 colours keeps ~700–900
unique tiles out of 896 — well inside the 1024-index / 32 KiB 4bpp
VRAM budget.

The ASM wrapper `main_mode1_image_4bpp.s` embeds these files via
`.incbin` and computes the tile DMA size dynamically from a pair of
labels (`TileDataEnd - TileData`), so the same source works for any
resulting tile count. It places tile data at VRAM word `$0000` and
the tilemap at word `$3000` (`BG1SC = $30`), specifically so the two
regions stay disjoint even with the maximum ~24 KiB of tile data
that a fully-packed BG1 4bpp Mode 1 image can produce.

Because the source image is a user asset (photo, personal artwork,
etc.) and generally shouldn't be committed, this ROM is **opt-in**
and not built by `make` / `make all`. To build it against your own
image:

```bash
# one-shot build
make mode1_image_demo MODE1_IMAGE_SRC=path/to/your_image.jpg

# or manually:
python3 tools/gen_assets.py mode1_image \
    --source path/to/your_image.jpg \
    --bpp 4 \
    --crop-align center \
    --name mode1_image
ca65 -t none -o build/main_mode1_image_4bpp.o main_mode1_image_4bpp.s
ld65 -C snes.cfg -o build/mode1_image_pal_demo.sfc build/main_mode1_image_4bpp.o
python3 tools/fix_checksum.py build/mode1_image_pal_demo.sfc
```

Source images are expected to live outside the repo or under an
ignored path (the top-level `.gitignore` already excludes
`assets/DSC*` so imported photos don't sneak in via `git add .`).

8bpp (Mode 3/4 BG1) is **not** supported by either pipeline; add a
new branch in `tile_to_bitplanes` if you need it.

## Further reading

- [`docs/AI-README.md`](docs/AI-README.md) — project-wide reference
  for AI agents and new contributors (conventions, init sequence,
  per-target asset pipeline, bsnes-plus viewer quirks).
- [`docs/AI-MODE-5-README.md`](docs/AI-MODE-5-README.md) — focused
  **Mode 5 cookbook**: how tilesets and tilemaps must be laid out so
  BG2 (2bpp) and BG1 (4bpp) render correctly, why **dense packing** is
  the preferred VRAM layout, what the overscan-safe area is, and how
  to turn a full-screen 512×448 PNG into 2bpp / 4bpp assets.

## License

Public Domain / MIT — do whatever you want.
