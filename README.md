# SNES Mode 1 Tile Test (PAL)

Minimal Super Nintendo demo written in cc65 assembly (`ca65` / `ld65`) that
shows how to:

- initialize the console in a hardware-safe way (force blank, IRQ/NMI off,
  DMA off, clear WRAM / VRAM / CGRAM),
- enable graphics **Mode 1**,
- on a **single background layer (BG1)**
- display one **16×16 character** made of 2×2 4bpp tiles.

The output is a **LoROM** `.sfc` file for **PAL consoles** that runs in
`bsnes` / `bsnes-plus` and can also be booted on real hardware (e.g. via a
flash cart).

## Project layout

```
main.s                 # 65816 assembly: init, Mode 1, uploads, main loop
snes.cfg               # ld65 memory/segment config (LoROM)
Makefile               # build: assets -> ca65 -> ld65 -> checksum fix
tools/
  gen_assets.py        # generates palette.bin, tiles.chr, tilemap.bin, preview.png
  fix_checksum.py      # writes correct SNES header checksum/complement
build/
  mode1_pal_demo.sfc   # final ROM (after make)
  preview.png          # expected picture
  palette.bin          # 16 colors, BGR555, 32 bytes
  tiles.chr            # 18 tiles (4bpp); character at indices 0,1,16,17
  tilemap.bin          # 32x32 BG1 tilemap
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

### VRAM tile layout

Tiles as seen in the tile viewer (16 tiles per row) — character arranged as a
true 2×2 block at the top-left:

```
index  0 = character top-left
index  1 = character top-right
index  2 = blank tile (used as tilemap background)
index 16 = character bottom-left
index 17 = character bottom-right
```

The tilemap is filled with index `2` everywhere; only the center (tile
position `14,11`) holds the four character indices.

## License

Public Domain / MIT — do whatever you want.
