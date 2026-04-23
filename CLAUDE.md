# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SNES ROM development project producing five bootable 32 KiB LoROM PAL ROMs that demonstrate graphics display across multiple background modes. All ROMs run on real PAL hardware (via EverDrive/SD2SNES/FXPak Pro) and bsnes/bsnes-plus emulators.

## Build Commands

**Dependencies:** `ca65`/`ld65` (cc65 toolchain), Python 3, Pillow (`pip install Pillow`)

```bash
make              # Build all four standard ROMs → build/*.sfc
make clean        # Remove entire build/ directory

# Optional: full-screen Mode 1 ROM from a user-supplied image (not in `make all`)
make mode1_image_demo MODE1_IMAGE_SRC=path/to/image.jpg
```

The build pipeline for each ROM:
1. `python3 tools/gen_assets.py <target>` → `build/<target>/{palette.bin, tiles.*.chr, tilemap.bin, preview.png}`
2. `ca65 -t none` → `build/main_*.o`
3. `ld65 -C snes.cfg` → `build/*.sfc`
4. `python3 tools/fix_checksum.py build/*.sfc` → valid header checksum

## ROM Outputs

| ROM | BG Mode | BPP | Tile Size | Content |
|-----|---------|-----|-----------|---------|
| `mode1_pal_demo.sfc` | Mode 1 BG1 | 4bpp | 8×8 | 16-color centered pixel-art character |
| `mode0_pal_demo.sfc` | Mode 0 BG1 | 2bpp | 8×8 | 4-color centered pixel-art character |
| `mode5_pal_demo.sfc` | Mode 5 BG2 | 2bpp | 16×16 | 4-color characters at four screen corners, hi-res+interlace |
| `mode5_wallpaper_pal_demo.sfc` | Mode 5 BG1 | 4bpp | 16×16 | Full-screen wallpaper, hi-res+interlace |
| `mode1_image_pal_demo.sfc` | Mode 1 BG1 | 4bpp | 8×8 | Full-screen user-supplied image (opt-in) |

## Architecture

### Assembly Sources (`main_*.s`)

All five sources follow an identical structure and init sequence:
1. PPU register equates (`INIDISP`, `BGMODE`, `VMxxx`, `CGxxx`, etc.)
2. `Reset:` — native mode switch, 16-bit regs, stack setup
3. Force blank (`INIDISP = $80`) → DMA-clear WRAM (128 KiB, two 64 KiB passes) → DMA-clear VRAM (64 KiB) → DMA-clear CGRAM (512 B)
4. PPU configuration (`BGMODE`, `BGxSC`, `BGxNBA`, `BGxHOFS/VOFS`)
5. DMA uploads: palette → CGDATA, tiles → VRAM, tilemap → VRAM
6. Enable layers (`TM`, plus `TS` for Mode 5 hi-res sub-screen)
7. End force blank (`INIDISP = $0F`), `wai` loop forever
8. `RODATA` segment: `.incbin` directives pointing into `build/<target>/`
9. `HEADER` segment: 21-byte SNES internal header at `$7FC0`
10. `VECTORS` segment: reset/NMI/IRQ vectors at `$7FE0`

`snes.cfg` defines the ld65 linker memory layout: ZP (`$0000`–`$00FF`), RAM (`$0200`–`$1FFF`), ROM (`$8000`–`$FFBF`), HEADER (`$7FC0`–`$7FDF`), VECTORS (`$7FE0`–`$7FFF`).

### Asset Generator (`tools/gen_assets.py`)

Single script with four independent target modes:
- `mode0_2bpp`, `mode1_4bpp`, `mode5_2bpp` — hardcoded pixel-art, generates all assets from scratch
- `mode5_image` — arbitrary source image → Mode 5 full-screen (requires `--source`, `--bpp`, `--name`)
- `mode1_image` — arbitrary source image → Mode 1 full-screen (requires `--source`, `--bpp`, `--crop-align`, `--name`)

Image pipelines (via `tools/crop_image.py`): scale+crop to target resolution → median-cut palette quantization (2^bpp colors) + Floyd-Steinberg dithering → deduplicate tiles across H/V flips → dense-pack unique tiles → emit `.chr` + `tilemap.bin`.

`tools/fix_checksum.py` — post-link step: writes `checksum XOR complement = 0xFFFF` into the LoROM header at `$7FDC–$7FDF`.

## Critical Pitfalls (from docs/AI-README.md)

- **Blank tile index:** The character occupies VRAM indices `0,1,16,17` (8×8 modes) or dense-packed starting at 0 (16×16 modes). The blank tile sits at index 8. Index 0 is a character tile, not blank — placing blank at 0 corrupts the display.
- **BG1SC register encodes tilemap base as `addr >> 10` (i.e., word address `>> 9` then `>> 1`)** — off-by-one shifts corrupt the entire tilemap address.
- **VRAM/CGRAM writes must happen inside force blank** — writing outside force blank causes visual corruption on real hardware.
- **Mode 5 sub-screen:** BG layers used as hi-res source must be enabled on both main screen (`TM`) and sub-screen (`TS`); missing `TS` gives a blank display.
- **Mode 5 interlace:** Requires `SETINI |= $01` (interlace bit) as well as `BGMODE |= $04` (hi-res bit); setting only one gives 256×224 resolution, not 512×448.
- **16×16 BG tile auto-read:** A single tilemap entry N causes the PPU to read tiles `N, N+1, N+16, N+17` automatically — you do not explicitly reference the four sub-tiles in the tilemap.
- **Dense-packing Mode 5:** Characters are at VRAM indices 0, 2, 4, 6 (step of 2 to leave room for the `N+1` auto-read slot); sparse packing wastes VRAM and does not work for full-screen images.
- **LoROM header offset:** The internal header lives at byte `$7FC0` in the binary (not `$8000`); `fix_checksum.py` reads `$7FDC–$7FDF` within the 32 KiB file.
- **ROM size byte must be `$08`, not `$05`:** The SNES spec says `$05` for 32 KiB, but Everdrive firmware maps `$05` as "8 Mbit" and loads the ROM at the wrong address (black screen). `$08` selects the "512k" LoROM mapping that mirrors 32 KiB correctly. The S-CPU ignores this field entirely.
- **PPU registers undefined on real hardware:** bsnes initialises all PPU registers to 0; real hardware leaves them undefined. `TMW ($212E)`, `TSW ($212F)`, `CGWSEL ($2130)`, `CGADSUB ($2131)`, `W12SEL ($2123)`, `W34SEL ($2124)` must be explicitly zeroed after `TM`/`TS` setup. In Mode 5 with the same BG on both screens, `CGADSUB` bit 7 + BG bit = 1 cancels every pixel to black; do not remove the `stz` block.
- **DMA size 0 = 65536 bytes**, not zero bytes — used intentionally for the full WRAM/VRAM clear passes.
- **bsnes-plus Tilemap Viewer quirk:** Dense-packed Mode 5 BG2 shows ghost images for 3 of the 4 corners in the viewer; the actual screen output is correct. This is a debugger display bug, not a ROM bug.

## Documentation

- `README.md` — project overview, build instructions, technical deep-dives
- `docs/AI-README.md` — architecture overview and extended pitfall list for AI agents
- `docs/AI-MODE-5-README.md` — Mode 5 cookbook: overscan safe area, CGRAM sharing, tile packing
