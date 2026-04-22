# SNES Mode 1 Tile Test (PAL)

Minimal Super Nintendo demo written in cc65 assembly (`ca65` / `ld65`) that
shows how to:

- initialize the console in a hardware-safe way (force blank, IRQ/NMI off,
  DMA off, clear WRAM / VRAM / CGRAM),
- enable graphics **Mode 1**,
- on a **single background layer (BG1)**, using **4bpp tiles** and a
  **16-color 4bpp palette**,
- display one **16×16 character** made of 2×2 4bpp tiles.

> **Note:** Everything in this project is 4bpp only. `gen_assets.py` and the
> ROM assembly are hard-wired to the SNES 4bpp tile format (32 bytes per
> 8×8 tile) and to a single 16-color BGR555 palette. 2bpp (e.g. Mode 1 BG3)
> and 8bpp (Mode 3/4 BG1) are **not** supported here.

The output is a **LoROM** `.sfc` file for **PAL consoles** that runs in
`bsnes` / `bsnes-plus` and can also be booted on real hardware (e.g. via a
flash cart).

## Project layout

```
main.s                 # 65816 assembly: init, Mode 1, uploads, main loop
snes.cfg               # ld65 memory/segment config (LoROM)
Makefile               # build: assets -> ca65 -> ld65 -> checksum fix
tools/
  gen_assets.py        # generates palette.bin, tiles.4bpp.chr, tilemap.bin, preview.png
  fix_checksum.py      # writes correct SNES header checksum/complement
build/
  mode1_pal_demo.sfc   # final ROM (after make)
  preview.png          # expected picture
  palette.bin          # 4bpp palette: 16 colors, BGR555, 32 bytes
  tiles.4bpp.chr       # 4bpp tile data: 18 tiles x 32 bytes (character at 0,1,16,17)
  tilemap.bin          # 32x32 BG1 tilemap (2-byte entries)
```

## Requirements

- `cc65` (provides `ca65` and `ld65`) on PATH
- Python 3 with `Pillow` (for the asset generator and preview PNG)
- optional: `bsnes` / `bsnes-plus` for testing

## Build

```bash
make
```

The ROM is produced at `build/mode1_pal_demo.sfc`.

## Clean

```bash
make clean
```

## Technical details

### ROM header

- Map mode: `$20` (LoROM, SlowROM)
- Destination: `$02` (Europe / PAL)
- Title: `MODE1 16X16 PAL DEMO`
- Checksum and complement are written automatically by
  `tools/fix_checksum.py` after linking.

### Init sequence (summary)

1. `sei` / `clc` / `xce` — switch to 65816 native mode
2. 16-bit A/X/Y, stack set to `$1FFF`
3. `INIDISP = $80` — force blank
4. `NMITIMEN`, `HDMAEN`, `MDMAEN`, `WRIO`, APU ports cleared
5. WRAM (128 KiB), VRAM (64 KiB), CGRAM (512 B) cleared via DMA
6. BG mode 1, BG1 tilemap @ word `$1000`, BG1 char base @ word `$0000`
7. Palette, tiles and tilemap uploaded via DMA
8. `TM = $01` — only BG1 visible
9. `INIDISP = $0F` — force blank off, full brightness
10. Main loop: `wai` / `bra` (nothing to do)

### VRAM tile layout (4bpp)

Tiles as seen in the 4bpp tile viewer (16 tiles per row) — character
arranged as a true 2×2 block at the top-left:

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
layer's 2bpp/4bpp/8bpp setting. That is why `tilemap.bin` is named without
a `4bpp` qualifier while `tiles.4bpp.chr` and the 16-color palette are
explicitly labeled.

## License

Public Domain / MIT — do whatever you want.
