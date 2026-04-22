# SNES Tile Test Demos (PAL)

Two minimal Super Nintendo demos written in cc65 assembly (`ca65` / `ld65`)
that show how to:

- initialize the console in a hardware-safe way (force blank, IRQ/NMI off,
  DMA off, clear WRAM / VRAM / CGRAM),
- enable a specific BG mode,
- with **one single background layer (BG1)**
- display one **16×16 character** built from 2×2 BG tiles.

The project ships two complete builds that only differ in bit depth / mode:

| ROM                          | Mode   | BG1 tile format | Palette size |
| ---------------------------- | ------ | --------------- | ------------ |
| `build/mode1_pal_demo.sfc`   | Mode 1 | 4bpp            | 16 colors    |
| `build/mode0_pal_demo.sfc`   | Mode 0 | 2bpp            |  4 colors    |

Both ROMs target **LoROM / PAL** consoles, run in `bsnes` / `bsnes-plus` and
boot on real hardware (e.g. via a flash cart).

## Project layout

```
main_mode1_4bpp.s      # 65816 asm: Mode 1, 4bpp BG1 demo
main_mode0_2bpp.s      # 65816 asm: Mode 0, 2bpp BG1 demo
snes.cfg               # ld65 memory/segment config (LoROM, shared)
Makefile               # builds both ROMs
tools/
  gen_assets.py        # 2bpp + 4bpp encoder, palette / tilemap / preview generator
  fix_checksum.py      # writes correct SNES header checksum/complement
build/
  mode1_pal_demo.sfc   # final Mode 1 ROM
  mode0_pal_demo.sfc   # final Mode 0 ROM
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
```

## Requirements

- `cc65` (provides `ca65` and `ld65`) on PATH
- Python 3 with `Pillow` (for the asset generator and preview PNG)
- optional: `bsnes` / `bsnes-plus` for testing

## Build

```bash
make
```

The two ROMs appear at `build/mode1_pal_demo.sfc` and
`build/mode0_pal_demo.sfc`.

## Clean

```bash
make clean
```

## Technical details

### ROM headers

Both ROMs share the same LoROM / PAL configuration:

- Map mode: `$20` (LoROM, SlowROM)
- Destination: `$02` (Europe / PAL)
- Titles: `MODE1 16X16 PAL DEMO` / `MODE0 16X16 PAL DEMO`
- Checksum and complement are written automatically by
  `tools/fix_checksum.py` after linking.

### Init sequence (summary, shared by both demos)

1. `sei` / `clc` / `xce` — switch to 65816 native mode
2. 16-bit A/X/Y, stack set to `$1FFF`
3. `INIDISP = $80` — force blank
4. `NMITIMEN`, `HDMAEN`, `MDMAEN`, `WRIO`, APU ports cleared
5. WRAM (128 KiB), VRAM (64 KiB), CGRAM (512 B) cleared via DMA
6. BG mode set (`$01` for Mode 1, `$00` for Mode 0),
   BG1 tilemap @ word `$1000`, BG1 char base @ word `$0000`
7. Palette, tiles and tilemap uploaded via DMA
8. `TM = $01` — only BG1 visible
9. `INIDISP = $0F` — force blank off, full brightness
10. Main loop: `wai` / `bra` (nothing to do)

Differences between the two demos:

| Step           | Mode 1 (4bpp)       | Mode 0 (2bpp)       |
| -------------- | ------------------- | ------------------- |
| `BGMODE`       | `$01`               | `$00`               |
| Palette upload | 32 bytes, 16 colors | 8 bytes, 4 colors   |
| Tile upload    | 576 bytes (`$0240`) | 288 bytes (`$0120`) |
| Tile size      | 32 B (4 bitplanes)  | 16 B (2 bitplanes)  |

### VRAM tile layout (both demos)

Tiles as seen in the tile viewer (16 tiles per row) — character arranged
as a true 2×2 block at the top-left of VRAM:

```
index  0 = character top-left
index  1 = character top-right
index  2 = blank tile (used as tilemap background)
index 16 = character bottom-left
index 17 = character bottom-right
```

The tilemap is filled with index `2` everywhere; only the center (tile
position `14,11`) holds the four character indices.

### Why `tilemap.bin` has no bit-depth suffix

The SNES tilemap entry format is bit-depth **agnostic** — every entry is a
16-bit word with the same layout (`vhopppcc cccccccc`: flip flags, priority,
3-bit palette, 10-bit tile index). The actual bit depth comes from the
`BGMODE` register and the per-layer char base (`BGxNBA`). The PPU
multiplies the tile index internally by 16/32/64 bytes depending on the
layer's 2bpp/4bpp/8bpp setting. That is why the tilemap file is the same
byte-for-byte in both the Mode 1 / 4bpp and Mode 0 / 2bpp builds, and is
named without a bit-depth qualifier.

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
python3 tools/gen_assets.py all          # regenerate both
```

Each target has its **own** palette and pixel art, so the 2bpp build
stays within its 4 palette slots while the 4bpp build actually exercises
all 16 slots (the character is rendered as a 4×4 grid of 4×4 colored
blocks, one per palette index). The `Makefile` invokes the script once
per target, so `make` only regenerates the asset set that is out of date.

8bpp (Mode 3/4 BG1) is **not** supported; add a new branch in
`tile_to_bitplanes` if you need it.

## License

Public Domain / MIT — do whatever you want.
