# SNES Tile Test Demos (PAL)

Three minimal Super Nintendo demos written in cc65 assembly (`ca65` / `ld65`)
that show how to:

- initialize the console in a hardware-safe way (force blank, IRQ/NMI off,
  DMA off, clear WRAM / VRAM / CGRAM),
- enable a specific BG mode,
- with **one single background layer**,
- display one or more **16×16 characters** on screen (Mode 0 / Mode 1
  show a single centered character; Mode 5 shows four distinct
  characters, one nudged into each screen corner).

The project ships three complete builds that differ in BG mode, tile
format, tile size and screen resolution:

| ROM                        | Mode   | BG used | Tile format | BG tile size | Display    | Characters | Extras             |
| -------------------------- | ------ | ------- | ----------- | ------------ | ---------- | ---------- | ------------------ |
| `build/mode1_pal_demo.sfc` | Mode 1 | BG1     | 4bpp        | 8×8 (2×2 ch) | 256×224    | 1 (center) | —                  |
| `build/mode0_pal_demo.sfc` | Mode 0 | BG1     | 2bpp        | 8×8 (2×2 ch) | 256×224    | 1 (center) | —                  |
| `build/mode5_pal_demo.sfc` | Mode 5 | BG2     | 2bpp        | 16×16 (1 ch) | 512×448    | 4 (corners) | hi-res + interlace |

All ROMs target **LoROM / PAL** consoles, run in `bsnes` / `bsnes-plus` and
boot on real hardware (e.g. via a flash cart).

## Project layout

```
main_mode1_4bpp.s      # 65816 asm: Mode 1, 4bpp BG1 demo
main_mode0_2bpp.s      # 65816 asm: Mode 0, 2bpp BG1 demo
main_mode5_2bpp.s      # 65816 asm: Mode 5, 2bpp BG2 demo (16x16 tiles, interlace)
snes.cfg               # ld65 memory/segment config (LoROM, shared)
Makefile               # builds all three ROMs
tools/
  gen_assets.py        # 2bpp + 4bpp encoder, palette / tilemap / preview generator
  fix_checksum.py      # writes correct SNES header checksum/complement
build/
  mode1_pal_demo.sfc   # final Mode 1 ROM
  mode0_pal_demo.sfc   # final Mode 0 ROM
  mode5_pal_demo.sfc   # final Mode 5 ROM
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
    tiles.2bpp.chr     # 2bpp tile data: 30 tiles x 16 bytes = 480 bytes
                       # (covers four distinct 16x16 characters)
    tilemap.bin        # 32x32 BG2 tilemap; FOUR entries (one per screen corner)
    preview.png        # expected picture for 512x448 (2x upscaled)
```

## Requirements

- `cc65` (provides `ca65` and `ld65`) on PATH
- Python 3 with `Pillow` (for the asset generator and preview PNG)
- optional: `bsnes` / `bsnes-plus` for testing

## Build

```bash
make
```

The three ROMs appear at `build/mode1_pal_demo.sfc`,
`build/mode0_pal_demo.sfc` and `build/mode5_pal_demo.sfc`.

## Clean

```bash
make clean
```

## Technical details

### ROM headers

All ROMs share the same LoROM / PAL configuration:

- Map mode: `$20` (LoROM, SlowROM)
- Destination: `$02` (Europe / PAL)
- Titles: `MODE1 16X16 PAL DEMO` / `MODE0 16X16 PAL DEMO` / `MODE5 16X16 PAL DEMO`
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

Differences between the three demos:

| Step           | Mode 1 (4bpp, BG1)  | Mode 0 (2bpp, BG1)  | Mode 5 (2bpp, BG2)                |
| -------------- | ------------------- | ------------------- | --------------------------------- |
| `BGMODE`       | `$01`               | `$00`               | `$25` (mode 5 + BG2 16×16 tiles)  |
| Palette upload | 32 bytes, 16 colors | 8 bytes, 4 colors   | 8 bytes, 4 colors                 |
| Tile upload    | 576 bytes (`$0240`) | 288 bytes (`$0120`) | 480 bytes (`$01E0`)               |
| Tile count     | 18 tiles            | 18 tiles            | 30 tiles (covers four characters) |
| Tile size      | 32 B (4 bitplanes)  | 16 B (2 bitplanes)  | 16 B (2 bitplanes)                |
| `TM` / `TS`    | `$01` / `$00`       | `$01` / `$00`       | `$02` / `$02` (BG2 on main + sub) |
| `SETINI`       | `$00`               | `$00`               | `$01` (interlace on)              |

Note on Mode 5 BG2 16×16 tile mode: a single tilemap entry points at tile
index `N` and the PPU auto-reads `N, N+1, N+16, N+17` as the four 8×8
sub-tiles of a 16×16 screen block. The Mode 0 / Mode 1 VRAM layout
(character at indices `0, 1, 16, 17`) is byte-compatible with that
auto-read, so Mode 5's first character is the same cross tile used by
the other builds. Mode 5 then additionally stores **three** further
characters at indices `(4,5,20,21)`, `(8,9,24,25)` and `(12,13,28,29)`
— same pattern, next free 2×2 blocks — so it needs a larger
`tiles.2bpp.chr` (30 tiles / 480 bytes). The palette stays identical
to Mode 0; only `tiles.2bpp.chr` and `tilemap.bin` differ.

### VRAM tile layout

Tiles as seen in the tile viewer (16 tiles per row) — each character
is stored as a true 2×2 block so both 8×8 and 16×16 BG modes can
reference it with the same VRAM layout.

Mode 0 / Mode 1 (one character):

```
index  0 = character top-left
index  1 = character top-right
index  2 = blank tile (used as tilemap background)
index 16 = character bottom-left
index 17 = character bottom-right
```

Mode 5 (four characters, same N, N+1, N+16, N+17 pattern, each 2×2
block 4 indices apart):

```
indices  0, 1, 16, 17 = character 1 (cross)
indices  4, 5, 20, 21 = character 2 (diagonal X)
indices  8, 9, 24, 25 = character 3 (filled square)
indices 12,13, 28, 29 = character 4 (checkerboard)
index            2    = blank tile (tilemap background)
```

For the 8×8-tile modes (Mode 0 / Mode 1), the tilemap is filled with
index `2` everywhere and the center (tile position `14,11`) holds the
four character indices as four separate tilemap entries. For Mode 5
(BG2 16×16-tile mode), the tilemap is still filled with index `2`
everywhere, but **four** entries at tile positions `(1,1)`, `(30,1)`,
`(1,26)` and `(30,26)` (in 16×16-tile units) hold the top-left index
of each character, and the PPU auto-assembles the four 8×8 sub-tiles
into the on-screen 16×16 block. The corner positions are nudged one
16×16 cell inside the edge of the 512×448 screen so they stay outside
the overscan mask that bsnes-plus and real PAL TVs hide at the screen
borders.

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
python3 tools/gen_assets.py mode5_2bpp   # mode0 cross tile + 3 extra 16x16 tiles
python3 tools/gen_assets.py all          # regenerate all three
```

Each target has its **own** palette and pixel art (the 2bpp builds stay
within 4 palette slots while the 4bpp build actually exercises all 16
slots, rendered as a 4×4 grid of 4×4 colored blocks, one per palette
index). Every target declares a list of characters (render function +
tilemap position + VRAM indices) plus its own `tiles_to_upload` count,
so Mode 0 and Mode 1 carry one character each while Mode 5 carries
four. The `mode5_2bpp` target shares its palette bytes with
`mode0_2bpp` but generates a bigger `tiles.2bpp.chr` and a different
`tilemap.bin` (plus a 512×448 preview). The `Makefile` invokes the
script once per target, so `make` only regenerates the asset set that
is out of date.

8bpp (Mode 3/4 BG1) is **not** supported; add a new branch in
`tile_to_bitplanes` if you need it.

## License

Public Domain / MIT — do whatever you want.
