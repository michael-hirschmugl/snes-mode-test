# AI-README

Internal orientation document for AI agents working on this repository.
Meant to be read **before** editing code. Keep it up to date when the
architecture, conventions or common pitfalls change.

> **Working on Mode 5?** Read
> [`AI-MODE-5-README.md`](AI-MODE-5-README.md) as well. It is a focused
> cookbook covering: the 512×448 overscan safe area, **dense packing**
> as the preferred 16×16 tileset layout, how BG2 (2bpp) is set up in
> this repo, what to do to add BG1 (4bpp) on top, CGRAM sharing rules,
> and a full PNG → 2bpp / 4bpp conversion pipeline.
>
> **Converting a photo / arbitrary image to Mode 5 assets?** The
> `mode5_image` target in `tools/gen_assets.py` takes any JPG/PNG as
> `--source`, internally reuses `tools/crop_image.py` to scale + crop +
> palette-quantise it to a 512×448 indexed image, then dedupes 16×16
> super-tiles (with H/V flip variants, since the tilemap word encodes
> those bits for free) and dense-packs them into VRAM. Output goes to
> `build/<--name>/` in the same `{palette.bin, tiles.<bpp>bpp.chr,
> tilemap.bin, preview.png}` format as the static demos. There is no
> matching `main_*.s` yet — the target produces data only, ready to
> `.incbin` into a future 4bpp Mode 5 ROM.

---

## High-level architecture

This repo produces three tiny SNES ROMs from the same build system:

- `build/mode1_pal_demo.sfc` — Mode 1, BG1 only, **4bpp** tiles, 16-color palette, 8×8 tile size, 256×224
- `build/mode0_pal_demo.sfc` — Mode 0, BG1 only, **2bpp** tiles,  4-color palette, 8×8 tile size, 256×224
- `build/mode5_pal_demo.sfc` — Mode 5, BG2 only, **2bpp** tiles,  4-color palette, **16×16** tile size, **512×448** (hi-res + interlace)

All ROMs share:

- a single LoROM / PAL header configuration (`snes.cfg`),
- the same init sequence (force blank → clear WRAM/VRAM/CGRAM via DMA → PPU
  setup → palette/tile/tilemap upload → end force blank),
- the same VRAM tile placement (character at indices `0,1,16,17`,
  blank/transparent tile at `8`), which is byte-compatible with both 8×8
  and 16×16 BG tile modes (the 16×16 mode auto-reads `N, N+1, N+16, N+17`),
- the same post-link checksum fixer.

They diverge on:

- Mode 1 / Mode 0 use BG1 with 8×8 tiles; the tilemap has four entries
  around tile position `14,11` pointing at indices `0, 1, 16, 17`.
- Mode 5 uses BG2 with 16×16 tiles (BGMODE bit 5); the tilemap has
  four non-blank entries, one near each screen corner (characters are
  dense-packed in 2-tile steps):
  - `(1,  1)`  -> index `0` (cross tile)
  - `(30, 1)`  -> index `2` (diagonal-X variant)
  - `(1,  26)` -> index `4` (filled-square variant)
  - `(30, 26)` -> index `6` (checkerboard variant)

  Each position is nudged one 16×16 cell inside the edge of the
  512×448 screen so it sits outside the emulator / TV overscan mask.
  The PPU assembles each whole character from its single tilemap entry
  via the 16×16 auto-read pattern.
- Mode 5 enables interlace via `SETINI` bit 0 and enables BG2 on **both**
  TM and TS, because Mode 5's horizontal hi-res only shows the full 512
  px wide image if main+sub are both populated.

Pipeline:

```
tools/gen_assets.py mode1_4bpp   (Python, Pillow)
  └── writes: build/mode1_4bpp/{palette.bin, tiles.4bpp.chr, tilemap.bin, preview.png}
tools/gen_assets.py mode0_2bpp   (Python, Pillow)
  └── writes: build/mode0_2bpp/{palette.bin, tiles.2bpp.chr, tilemap.bin, preview.png}
tools/gen_assets.py mode5_2bpp   (Python, Pillow)
  └── writes: build/mode5_2bpp/{palette.bin, tiles.2bpp.chr, tilemap.bin, preview.png}
      (palette.bin + tiles.2bpp.chr are byte-identical to mode0_2bpp;
       only tilemap.bin and preview.png differ.)
tools/gen_assets.py mode5_image --source PATH [--crop-align …] [--bpp 2|4] [--name NAME]
  └── writes: build/<NAME>/{palette.bin, tiles.<bpp>bpp.chr, tilemap.bin, preview.png}
      (image-derived, dedup'd Mode 5 BG1/BG2 background; no ROM build yet.)

main_mode1_4bpp.s ──ca65──► build/main_mode1_4bpp.o ──ld65 (snes.cfg)──► build/mode1_pal_demo.sfc ──fix_checksum.py──► final
main_mode0_2bpp.s ──ca65──► build/main_mode0_2bpp.o ──ld65 (snes.cfg)──► build/mode0_pal_demo.sfc ──fix_checksum.py──► final
main_mode5_2bpp.s ──ca65──► build/main_mode5_2bpp.o ──ld65 (snes.cfg)──► build/mode5_pal_demo.sfc ──fix_checksum.py──► final
```

The asset generator takes the target name (`mode0_2bpp`, `mode1_4bpp`,
`mode5_2bpp`, `mode5_image`, or `all`) as a mandatory CLI argument. The
`Makefile` invokes the static targets once each so they rebuild
independently; `mode5_image` is a dynamic target that additionally needs
`--source` and is invoked manually (or by a separate make rule you add
when it drives a ROM build). `all` only generates the static targets.
Each static target has its own palette and pixel art (the 4bpp target
uses all 16 palette indices; the 2bpp targets use only indices 0..3).
Static targets also declare a `tile_pixels_size` (8 or 16) and a
`screen_size` (256×224 or 512×448) so the tilemap and preview renderers
know whether to emit 8×8-tile or 16×16-tile layouts.

### `mode5_image` pipeline

Separate from the hand-rolled pixel-art targets, `mode5_image` turns
arbitrary input images into a full-screen Mode 5 background:

1. **Load + normalise** via `tools/crop_image.py` (imported as a module):
   if the source isn't already 512×448 it is scaled to *cover* the
   frame (`max(512/w, 448/h)`) and cropped with the chosen horizontal
   anchor (`--crop-align left|center|right`; vertical is always
   centered). If the source has more than `2**bpp` colours it is
   palette-quantised (Median-Cut + Floyd-Steinberg dithering).
2. **Slice** the 512×448 indexed image into 32×28 super-tiles of
   16×16 px (four 8×8 tiles each, in `TL, TR, BL, BR` order).
3. **Dedupe with flips**: the tilemap word already has H/V-flip bits,
   so super-tiles that are mirrors of already-seen super-tiles reuse
   the same VRAM slots. Typical photographic content dedupes 4–5× even
   after quantisation.
4. **Dense-pack**: unique super-tile `k` lands at VRAM base index
   `(k // 8) * 32 + (k % 8) * 2`, giving 8 super-tiles per pair of
   tile-viewer rows (see `docs/AI-MODE-5-README.md` §3.2 / §9.4). A
   reserved blank super-tile immediately follows the last unique one;
   the four tilemap rows below the visible screen (`y = 28..31`) point
   at it, matching the `BLANK_INDEX` convention used by the static
   demos.
5. **Emit** `palette.bin` (BGR555), `tiles.<bpp>bpp.chr` (dense-packed),
   `tilemap.bin` (32×32 entries, palette-field `0`, flip bits set per
   dedup result) and a 2× upscaled `preview.png`.

Hard limits enforced in code:

- 10-bit tile index (`0..1023`): if the dedup pass leaves too many
  unique super-tiles to dense-pack inside that range, the tool aborts
  with a clear message pointing at the culprit. Options are to reduce
  colour count, use a less detail-heavy source, or split content
  across BG1 and BG2.
- `--bpp` defaults to 4 (BG1); `--bpp 2` is available for BG2 but
  rarely looks good on photographic input.

Entry points:

- Source: `main_mode1_4bpp.s`, `main_mode0_2bpp.s`, `main_mode5_2bpp.s` (65816 assembly, ca65 syntax)
- Data: `build/<target>/*` (generated, gitignored)
- Linker config: `snes.cfg` (LoROM, HEADER at `$7FC0`, VECTORS at `$7FE0`)
- Build: `Makefile`
- Assets: `tools/gen_assets.py` (static + image-based targets)
- Image pre-processor: `tools/crop_image.py` (scale + crop + palette
  reduce; usable standalone or imported by `gen_assets.py`)
- Post-link: `tools/fix_checksum.py`

---

## Important patterns

### Data flow into the ROM

Assets are generated by Python, then embedded into the ROM at link time via
`.incbin` in the assembly sources:

```asm
PaletteData:  .incbin "build/mode1_4bpp/palette.bin"
TileData:     .incbin "build/mode1_4bpp/tiles.4bpp.chr"
TilemapData:  .incbin "build/mode1_4bpp/tilemap.bin"
```

If the asset paths, filenames or sizes change in `gen_assets.py`, the
`.incbin` lines **and** the DMA transfer sizes in the same `main_*.s`
must be updated together.

### DMA upload pattern

Every bulk upload (WRAM/VRAM/CGRAM clear, palette, tiles, tilemap) uses the
same DMA channel 0 setup:

1. Set destination PPU address (`VMADDL/H` or `CGADD`) before starting.
2. Configure `VMAIN` for VRAM transfers (usually `$80` = +1 word after high byte).
3. Write DMA control byte to `$4300` (mode + direction + source fixed/incrementing).
4. Write PPU register low byte to `$4301` (`$18` = VMDATAL, `$22` = CGDATA,
   `$80` = WMDATA).
5. Write 24-bit source address to `$4302..$4304` using `<`, `>`, `^` operators.
6. Write 16-bit transfer size to `$4305..$4306` (size `0` means 65536 bytes).
7. Kick the channel by writing `$01` to `$420B` (`MDMAEN`).

Transfer sizes are always expressed as bytes, not pixels or tiles. When you
change tile count or bit depth, recompute: `tiles × bytes_per_tile`.

### Force blank wrap

The ROM stays in force blank (`INIDISP = $80`) for the entire setup and
only releases it at the very end (`INIDISP = $0F`). Never attempt DMA to
VRAM/CGRAM outside of force blank or VBlank — it will silently corrupt.

### Shared init, divergent PPU config

The three demos have near-identical init code. The meaningful runtime
differences live in a small block around the PPU registers (`BGMODE`,
which BGxSC / BGxHOFS / BGxVOFS are programmed, palette size, tile
upload size, `TM`/`TS`, `SETINI`). If you add new features (e.g. input,
NMI), prefer touching all three files so they stay in sync, unless the
feature is genuinely mode-specific.

Mode 5 specifics that don't apply to Mode 0 / Mode 1:

- `BGMODE = $25` (mode 5 + BG2 16×16 tile size via bit 5).
- Programs `BG2SC` / `BG2HOFS` / `BG2VOFS` instead of the BG1 variants,
  and uses the upper nibble of `BG12NBA` for BG2's char base.
- Writes `SETINI = $01` to enable interlace (doubles vertical resolution
  to 448 lines).
- Sets `TM = TS = $02`: Mode 5's horizontal hi-res combines main-screen
  odd columns with sub-screen even columns. A BG layer that's only on
  `TM` shows up on every other column, which the user will perceive as
  "half the picture missing".

### Tilemap is format-agnostic (but NOT tile-size-agnostic)

`tilemap.bin` is **byte-identical** between the Mode 0 (2bpp) and Mode 1
(4bpp) builds. Tilemap entries (`vhopppcc cccccccc`) encode a 10-bit
tile index, 3-bit palette, flip/priority flags — they do **not** encode
bit depth. The PPU resolves the tile stride (16 / 32 / 64 bytes) from
`BGMODE` and `BGxNBA`.

However, the tilemap **layout** does depend on the configured BG tile
size (8×8 vs. 16×16, per `BGMODE` bits 4..7). Mode 5's `tilemap.bin` is
not the same as Mode 0's because BG2 runs in 16×16-tile mode in that
demo: the PPU reads one entry per 16×16 screen region and auto-fetches
tiles `N, N+1, N+16, N+17` from VRAM. The Mode 5 tilemap therefore has
exactly one non-blank entry (tile `0` at 16×16-position `15,13`)
whereas Mode 0/1 have four non-blank entries per character. The Mode 5
demo uses **four** distinct characters, one near each corner of the
512×448 screen:

- cross tile at `(1,  1)`  with VRAM indices `0,1,16,17`
- diagonal-X at `(30, 1)`  with VRAM indices `2,3,18,19`
- filled square at `(1,  26)` with VRAM indices `4,5,20,21`
- checkerboard at `(30, 26)` with VRAM indices `6,7,22,23`

Each position is nudged one 16×16 cell inside the edge because a flush
`(0/31, *)` or `(*, 0/27)` position would put the tile inside the
overscan mask that bsnes-plus and real PAL TVs hide at the screen
borders. Mode 0/1 place their single character near the center of the
256×224 screen.

### Blank tile at index 8

Tile index `0` is reserved for `character-top-left`. To avoid the common
"whole screen filled with one tile" bug, the tilemap is explicitly filled
with a dedicated blank super-tile at index `8`: this slot sits just after
the four dense-packed Mode-5 characters (`0,2,4,6`) and is fully inside
the empty VRAM column `8..15 / 24..31`. Hardware auto-reads `8,9,24,25`
(all zero) and the bsnes-plus Mode-5 hires Tilemap Viewer additionally
pulls in `10,26` (also zero), so empty cells render as true black in
every viewer. If you add new tiles, keep index `8` (and its 16×16
auto-read partners `9, 24, 25`) empty unless you also change the tilemap
fill code.

### bsnes-plus Tilemap Viewer quirk in Mode 5 hires + 16x16

**This is a debugger bug, not a ROM bug.** Hardware and the regular
emulator output window render the screen correctly; only the bsnes-plus
*Tilemap Viewer* shows ghosts of neighbouring characters on three of the
four corners. The cause is in
[`tilemap-renderer.cpp`](https://github.com/devinacker/bsnes-plus/blob/master/bsnes/ui-qt/debugger/ppu/tilemap-renderer.cpp)
(functions `drawMapTile` + `drawMap8pxTile`): for each 16x16 tilemap
entry the viewer reads the hardware-correct four sub-tiles
`c, c+1, c+16, c+17`, but in hires mode every sub-tile draw call also
fetches `t+1` and draws it 8 px to the right. A single Mode 5 hires
16x16 cell therefore renders as **32 px wide** composed of eight VRAM
tiles:

```
top row    : tile c     tile c+1   tile c+1   tile c+2
bottom row : tile c+16  tile c+17  tile c+17  tile c+18
```

Real SNES hardware only reads the four auto-read tiles — the extra
`c+1` (doubled) and `c+2`/`c+18` on the right are a Viewer artefact.

With the dense-packed tileset (characters at `0, 2, 4, 6`, step of two),
`c+2` and `c+18` are exactly the left half of the *next* character, so
the three non-last corners appear with a ghost of their neighbour
glued to their right edge:

- `(1,  1)` cross `c = 0`: ghost tiles `2, 18` = X top-left / X bottom-left.
- `(30, 1)` X     `c = 2`: ghost tiles `4, 20` = filled-square top-left / bottom-left.
- `(1, 26)` block `c = 4`: ghost tiles `6, 22` = checkerboard top-left / bottom-left.
- `(30,26)` checker `c = 6`: ghost tiles `8, 24` — both blank, so this
  single corner renders cleanly in the viewer.

Empty cells (`BLANK_INDEX = 8`) are unaffected: the viewer's extended
read (`8, 9, 10, 24, 25, 26`) is entirely inside the blank VRAM column,
so all tilemap background stays true black.

Any real Mode 5 hires game that dense-packs its 16x16 BG2 tileset would
trigger the same quirk in this Viewer — it is not worth reverting to a
sparse step-4 layout just to please the debugger.

### Checksum is written post-link, not assembled

`main_*.s` writes four zero bytes in the header for complement/checksum.
`tools/fix_checksum.py` recomputes both **after** `ld65` and patches the
binary in place. If the ROM size, header layout or fill value changes, the
checksum fixer may need updating too.

---

## Naming conventions

### Files

- `main_<mode>_<bpp>.s` — one assembly source per ROM target (`main_mode1_4bpp.s`, `main_mode0_2bpp.s`, `main_mode5_2bpp.s`).
- `build/<mode>_<bpp>/…` — one output subdirectory per target.
- `tiles.<bpp>.chr` — tile data files carry an explicit bit-depth suffix
  (`tiles.4bpp.chr`, `tiles.2bpp.chr`). The suffix matters because the
  data format is bit-depth-specific.
- `palette.bin` and `tilemap.bin` — no bit-depth suffix. Palettes differ
  only in length (embedded in the filename's containing directory), and
  the tilemap format is genuinely format-agnostic.
- `build/<target>_pal_demo.sfc` — final ROMs carry the region (`pal`) in
  the filename; update the destination byte in the header if you ever
  produce NTSC variants (`$01`).

### Assembly

- Labels: PascalCase for entry points and data (`Reset`, `Nmi`, `Irq`,
  `PaletteData`, `TileData`, `TilemapData`), UPPER_SNAKE for register
  equates (`INIDISP`, `BGMODE`, `DMA0CTRL`), plain numeric constants in
  hex with `$` prefix.
- Segments: `CODE`, `RODATA`, `HEADER`, `VECTORS`, `ZEROPAGE`, `BSS` — do
  not introduce new segment names without also adding them to `snes.cfg`.

### Python

- Constants in UPPER_SNAKE (`BYTES_PER_TILE`, `PALETTE_COLORS`,
  `CHAR_TILE_X`).
- Functions in `snake_case`, usually verb-first (`tile_to_bitplanes`,
  `build_tilemap`, `generate_target`).
- The encoder is **one** function `tile_to_bitplanes(pixels, bpp)` — do
  not split it per bpp unless you also have non-trivial per-bpp logic.
- Per-target data (palette + pixel art + output filename) lives in the
  `TARGETS` dict in `gen_assets.py`. Adding a new *static* target means
  adding a new entry there, plus matching wiring in the `Makefile` and
  a new `main_*.s` if it produces a new ROM.
- `mode5_image` lives outside `TARGETS` because it is parameterised on
  a `--source` path; its code path is separate (see
  `generate_mode5_image` / `load_image_as_indexed` /
  `dedupe_super_tiles` / `build_mode5_image_vram` /
  `build_mode5_image_tilemap`) and reuses the shared primitives
  (`tile_to_bitplanes`, `encode_palette`).

### Git

- Commits: imperative, English subject under ~72 chars, brief body
  explaining *why* when non-obvious. Current history follows this style.
- Prefer `git mv` for renames so rename detection works.

---

## Typical pitfalls

### 1. Tilemap base address vs. `BG1SC`

`BG1SC`'s top 6 bits × `$400` words = tilemap base VRAM address.
A common mistake is to upload the tilemap to word `$1000` but leave
`BG1SC = $04` (which points at word `$0400`) — BG1 then reads zeros and
the screen stays black. Correct value for word `$1000` is `BG1SC = $10`.

### 2. Tile index 0 used by character

If tile index `0` is used by a character tile, every unset tilemap entry
(which defaults to `0`) will render as that character across the whole
screen. Always ensure either (a) tile `0` is blank, or (b) the tilemap is
pre-filled with a known blank index and every position is explicitly set.

### 3. Wrong vector layout

The SNES 65816 vector table lives at `$FFE0..$FFFF` with 8 native and 8
emulation slots (some reserved/unused). Placing only 6+6 vectors shifts
everything wrong and the CPU resets to garbage. The full 8+8 layout with
reserved slots is required.

### 4. LoROM header at the wrong offset

LoROM places the internal header at `$7FC0..$7FDF` and the vector table
at `$7FE0..$7FFF` (inside bank 0). Using `$FFC0/$FFE0` (HiROM layout) by
mistake causes silent boot failure on real hardware and most emulators.
`snes.cfg` MEMORY areas must stay at `$7FC0` / `$7FE0` for this project.

### 5. Changing tile count without updating DMA size

`main_mode1_4bpp.s` uploads `18 × 32 = 576` bytes (`$0240`).
`main_mode0_2bpp.s` uploads `18 × 16 = 288` bytes (`$0120`).
`main_mode5_2bpp.s` uploads `30 × 16 = 480` bytes (`$01E0`) because it
covers four characters using VRAM indices up to `29` inclusive. Each
target has its own `tiles_to_upload` value in the `TARGETS` dict of
`gen_assets.py`; if you change it, the matching DMA0SIZE constant in
the corresponding `main_*.s` must change in lockstep. There is no
runtime check.

### 6. Palette size mismatch

Mode 1 4bpp demo uploads 32 bytes (16 colors). Mode 0 2bpp demo uploads
only 8 bytes (4 colors). Using the 4bpp palette size for a 2bpp palette
overwrites the neighbouring palette slots in CGRAM, which is usually
invisible here but dangerous once a second BG or sprites are added.

### 7. Writing to VRAM/CGRAM outside force blank

Skipping the force blank wrap around DMA uploads will corrupt VRAM/CGRAM
in subtle, mode-dependent ways. Always wrap bulk uploads with
`INIDISP = $80` … `INIDISP = $0F`.

### 8. Pixel value out of range for bpp

2bpp allows values `0..3`, 4bpp allows `0..15`. `tile_to_bitplanes`
asserts the range — if you add pixel art with higher color indices and
forget to bump the palette, the asset build crashes with an assertion.
Do not disable the assertion; fix the source pixels or palette instead.

### 9. Non-ASCII in ROM title

The header title field is exactly 21 bytes (ASCII/JIS X 0201 in real
carts). Do not insert Unicode; `ca65` would silently emit UTF-8 and
confuse emulators that parse the header.

### 10. Forgetting to rerun the checksum fixer

`ld65` writes the link output with the header checksum fields left at
zero. Only `tools/fix_checksum.py` makes the ROM header consistent. The
`Makefile` always calls it; any alternative build path must do the same.

### 11. Mode 5 without enabling BG on the sub screen

Mode 5 is inherently horizontal hi-res (512 px). The main screen
supplies the odd columns and the sub screen supplies the even columns.
If the BG layer is only enabled on `TM`, half the columns come from the
sub screen's fixed colour / backdrop and the content appears as
vertical stripes ("only half the picture visible"). `main_mode5_2bpp.s`
therefore writes `TM = TS = $02`.

### 12. Mode 5 without interlace but expecting 448 lines

Mode 5's hi-res only doubles the **horizontal** resolution. Vertical
doubling to 448 lines requires `SETINI` bit 0 (interlace) to be set.
Without interlace, Mode 5 still runs at 224 visible lines and the
16×16 BG2 tile covers twice as many scanlines vertically as expected.
If you change interlace behaviour, update both `main_mode5_2bpp.s` and
the `screen_size` of the `mode5_2bpp` target in `tools/gen_assets.py`
(which drives `preview.png`).

### 13. 16×16 BG tile size expects tile indices in a specific pattern

When `BGMODE` has the per-BG 16×16 tile-size bit set, the PPU reads
`N, N+1, N+16, N+17` from VRAM for each tilemap entry. The Mode 0/1
layout (character at indices `0, 1, 16, 17`) is byte-compatible with
this, which is why Mode 5 can reuse the Mode 0 `tiles.2bpp.chr` file
unchanged. If you ever reorganise the VRAM tile layout, double-check
that this property still holds or Mode 5 will display garbage.

---

## When in doubt

- Read the three `main_*.s` side by side to see which fields vary per
  mode (`BGMODE`, BGxSC / BGxNBA / BGxHOFS, `TM`/`TS`, `SETINI`).
- Load the ROM in `bsnes-plus` and open Tools → VRAM viewer / Tile viewer
  to verify tile and palette uploads before blaming logic.
- If the screen is black, first check `BGxSC` vs. tilemap upload
  address, then `TM` (and `TS` for Mode 5), then force blank.
- If Mode 5 shows a striped character, `TS` isn't set. If Mode 5 shows
  a stretched character, interlace is off.
