.setcpu "65816"
.smart on

; ------------------------------------------------------------
; SNES PAL demo (LoROM):
; - Hardware-safe init sequence
; - Mode 5 (BG1 = 4bpp, BG2 = 2bpp), interlace on
; - BG2 only, configured with 16x16 tile size (BGMODE bit 5)
; - Shows four different 2bpp 16x16 characters at the four screen
;   corners (each nudged one tile inside the edge to stay outside the
;   overscan mask): cross, diagonal-X, filled square and checkerboard.
;   Mode 5's horizontal hi-res combined with interlace doubles both
;   axes, so each character appears at half the physical size of the
;   mode0 preview.
;
; Notes on Mode 5 specifics:
; - Mode 5 is inherently horizontal hi-res (512 px wide). Main-screen
;   pixels fill the odd columns, sub-screen pixels fill the even columns,
;   so a BG layer must be enabled on BOTH TM and TS to cover the full
;   width; otherwise only half the content (every other column) is visible.
; - Interlace (SETINI bit 0) doubles vertical resolution to 448 lines by
;   alternating odd/even scanlines per field.
; - BG2 is 2bpp in Mode 5, matching the mode0 asset pack bit-for-bit. The
;   palette goes to BG2 palette slot 0 (CGRAM $00..$07).
; - With BGMODE bit 5 set, the PPU reads 4 consecutive 8x8 tiles
;   (N, N+1, N+16, N+17) per tilemap entry to form a 16x16 BG tile.
;   Characters are dense-packed in 2-tile steps: cross at N=0, diagonal X
;   at N=2, filled square at N=4, checkerboard at N=6. One tilemap entry
;   per top-left index paints a whole 16x16 character. The blank tilemap
;   index is 8 (reserved transparent super-tile right after the four
;   characters).
;
; Known bsnes-plus debugger quirk (NOT a ROM bug):
;   The Tilemap Viewer renders each Mode 5 hires 16x16 cell as 32x16
;   pixels, reading eight VRAM tiles per entry:
;       c,    c+1,  c+1,  c+2
;       c+16, c+17, c+17, c+18
;   instead of the hardware's four (c, c+1, c+16, c+17). With the dense
;   layout, c+2 and c+18 are the next character's left column, so three
;   of the four corners show a ghost of their neighbour glued to the
;   right in the Viewer. Hardware and the emulator output window are
;   correct. See docs/AI-README.md for the full per-corner breakdown.
; ------------------------------------------------------------

INIDISP   = $2100
BGMODE    = $2105
BG2SC     = $2108
BG12NBA   = $210B
BG2HOFS   = $210F
BG2VOFS   = $2110
VMAIN     = $2115
VMADDL    = $2116
VMADDH    = $2117
VMDATAL   = $2118
VMDATAH   = $2119
CGADD     = $2121
CGDATA    = $2122
TM        = $212C
TS        = $212D
SETINI    = $2133
NMITIMEN  = $4200
WRIO      = $4201
MDMAEN    = $420B
HDMAEN    = $420C
MEMSEL    = $420D
APUIO0    = $2140
WMDATA    = $2180
WMADDL    = $2181
WMADDM    = $2182
WMADDH    = $2183

DMA0CTRL  = $4300
DMA0DEST  = $4301
DMA0SRC   = $4302
DMA0SRCB  = $4304
DMA0SIZE  = $4305

.segment "CODE"

Reset:
    sei
    clc
    xce                 ; native mode
    rep #$38            ; 16-bit A/X/Y
    ldx #$1FFF
    txs

    ; Force blank, full brightness later after setup
    sep #$20
    lda #$80
    sta INIDISP

    stz NMITIMEN
    stz HDMAEN
    stz MDMAEN
    stz WRIO
    stz APUIO0
    stz APUIO0+1
    stz APUIO0+2
    stz APUIO0+3

    ; SlowROM timing (compatible baseline)
    stz MEMSEL

    ; Clear WRAM (128 KiB) through $2180 data port via DMA fixed destination
    stz WMADDL
    stz WMADDM
    stz WMADDH

    lda #$08            ; CPU->PPU, fixed destination
    sta DMA0CTRL
    lda #$80            ; WMDATA
    sta DMA0DEST
    lda #<ZeroByte
    sta DMA0SRC
    lda #>ZeroByte
    sta DMA0SRC+1
    lda #^ZeroByte
    sta DMA0SRCB
    lda #$00            ; 0 means 65536 bytes
    sta DMA0SIZE
    sta DMA0SIZE+1
    lda #$01
    sta MDMAEN
    lda #$01
    sta MDMAEN          ; second 64 KiB

    ; Clear VRAM (64 KiB) with zero through $2118/$2119
    stz VMADDL
    stz VMADDH
    lda #$80            ; increment after writing high byte, +1 word
    sta VMAIN
    lda #$09            ; CPU->PPU, 2 regs write once ($2118 then $2119), fixed source
    sta DMA0CTRL
    lda #$18            ; VMDATAL
    sta DMA0DEST
    lda #<ZeroWord
    sta DMA0SRC
    lda #>ZeroWord
    sta DMA0SRC+1
    lda #^ZeroWord
    sta DMA0SRCB
    lda #$00
    sta DMA0SIZE
    sta DMA0SIZE+1
    lda #$01
    sta MDMAEN

    ; Clear CGRAM (512 bytes)
    stz CGADD
    lda #$08            ; CPU->PPU fixed destination
    sta DMA0CTRL
    lda #$22            ; CGDATA
    sta DMA0DEST
    lda #<ZeroByte
    sta DMA0SRC
    lda #>ZeroByte
    sta DMA0SRC+1
    lda #^ZeroByte
    sta DMA0SRCB
    lda #$00
    sta DMA0SIZE
    lda #$02
    sta DMA0SIZE+1
    lda #$01
    sta MDMAEN

    ; PPU setup for Mode 5. BGMODE layout:
    ;   bits 0..2 = mode    -> $05 (mode 5: BG1 4bpp, BG2 2bpp, hi-res)
    ;   bit 5     = BG2 tile size 16x16 (0=8x8, 1=16x16)
    ; => $05 | $20 = $25. Other tile-size bits stay 0 (we only use BG2).
    lda #$25
    sta BGMODE

    ; BG2SC: top 6 bits = tilemap VRAM base (in 1K-word steps), low 2 bits = size.
    ; Tilemap is uploaded at word $1000 => base index 4 => register value $10.
    lda #$10            ; BG2 tilemap @ word $1000, 32x32
    sta BG2SC

    ; BG12NBA: low nibble = BG1 char base, high nibble = BG2 char base.
    ; We only use BG2; tiles live at VRAM word $0000 => both nibbles 0.
    stz BG12NBA
    stz BG2HOFS
    stz BG2HOFS
    stz BG2VOFS
    stz BG2VOFS

    ; Enable interlace (SETINI bit 0). Vertical resolution doubles from
    ; 224 to 448 lines; the PPU alternates odd/even scanline fields.
    lda #$01
    sta SETINI

    ; Upload BG2 palette 0 (2bpp = one 4-color palette = 8 bytes) to CGRAM
    ; $00..$07. In Mode 5 BG2's 2bpp palettes share CGRAM with BG1's 4bpp
    ; palettes, but BG2 palette 0 lives exactly at CGRAM $00..$07 either way.
    stz CGADD
    lda #$00
    sta DMA0CTRL
    lda #$22            ; CGDATA
    sta DMA0DEST
    lda #<PaletteData
    sta DMA0SRC
    lda #>PaletteData
    sta DMA0SRC+1
    lda #^PaletteData
    sta DMA0SRCB
    lda #$08            ; 8 bytes = 4 colors
    sta DMA0SIZE
    stz DMA0SIZE+1
    lda #$01
    sta MDMAEN

    ; Upload 24 BG2 tiles in 2bpp format (16 bytes per tile). Mode 5
    ; uses four dense-packed 16x16 characters:
    ;   indices 0,1,16,17   -> cross         (top-left on screen)
    ;   indices 2,3,18,19   -> diagonal X    (top-right on screen)
    ;   indices 4,5,20,21   -> filled square (bottom-left on screen)
    ;   indices 6,7,22,23   -> checkerboard  (bottom-right on screen)
    ; Slots 8..15 sit between the character's top row (0..7) and bottom
    ; row (16..23) in VRAM and are uploaded as blank padding; tilemap
    ; entry 8 therefore references a transparent 16x16 super-tile. The
    ; PPU still reads all four sub-tiles (N, N+1, N+16, N+17) from a
    ; single tilemap entry in 16x16 mode.
    ; 24 * 16 = 384 bytes ($0180).
    stz VMADDL
    stz VMADDH
    lda #$80
    sta VMAIN
    lda #$01            ; CPU->PPU, destination increments
    sta DMA0CTRL
    lda #$18            ; VMDATAL
    sta DMA0DEST
    lda #<TileData
    sta DMA0SRC
    lda #>TileData
    sta DMA0SRC+1
    lda #^TileData
    sta DMA0SRCB
    lda #$80            ; 384 bytes = $0180
    sta DMA0SIZE
    lda #$01
    sta DMA0SIZE+1
    lda #$01
    sta MDMAEN

    ; Upload full 32x32 tilemap (2048 bytes) at VRAM word $1000. With
    ; 16x16 tile size each entry spans a 16x16 screen region; Mode 5's
    ; tilemap contains exactly four non-blank entries (the four
    ; character top-left indices placed by gen_assets.py's mode5_2bpp
    ; target, one near each screen corner).
    lda #$00
    sta VMADDL
    lda #$10
    sta VMADDH
    lda #$80
    sta VMAIN
    lda #$01
    sta DMA0CTRL
    lda #$18
    sta DMA0DEST
    lda #<TilemapData
    sta DMA0SRC
    lda #>TilemapData
    sta DMA0SRC+1
    lda #^TilemapData
    sta DMA0SRCB
    lda #$00
    sta DMA0SIZE
    lda #$08            ; 2048 bytes
    sta DMA0SIZE+1
    lda #$01
    sta MDMAEN

    ; In Mode 5 hi-res the main screen supplies odd columns and the sub
    ; screen supplies even columns. Enable BG2 on BOTH layers, otherwise
    ; only every second column of the character is visible.
    lda #$02            ; BG2 on main screen
    sta TM
    lda #$02            ; BG2 on sub screen
    sta TS

    ; End force blank, brightness max
    lda #$0F
    sta INIDISP

Forever:
    wai
    bra Forever

Nmi:
    rti

Irq:
    rti

.segment "RODATA"

ZeroByte:
    .byte $00
ZeroWord:
    .word $0000

PaletteData:
    .incbin "build/mode5_2bpp/palette.bin"

TileData:
    .incbin "build/mode5_2bpp/tiles.2bpp.chr"

TilemapData:
    .incbin "build/mode5_2bpp/tilemap.bin"

.segment "HEADER"
    ; 21-byte internal title
    .byte "MODE5 16X16 PAL DEMO "
    ; map mode, cart type, ROM size, SRAM size
    .byte $20, $00, $08, $00
    ; destination code: $02 = Europe (PAL)
    .byte $02
    ; fixed value + version
    .byte $33, $00
    ; complement and checksum (fix_checksum.py rewrites these post-link)
    .word $0000
    .word $0000

.segment "VECTORS"
    ; $FFE0-$FFFF vector table layout
    .word $0000          ; Native reserved
    .word $0000          ; Native reserved
    .word $0000          ; Native COP
    .word $0000          ; Native BRK
    .word $0000          ; Native ABORT
    .word Nmi            ; Native NMI
    .word Reset          ; Native RESET
    .word Irq            ; Native IRQ
    .word $0000          ; Emu reserved
    .word $0000          ; Emu reserved
    .word $0000          ; Emu COP
    .word $0000          ; Emu BRK
    .word $0000          ; Emu ABORT
    .word $0000          ; Emu NMI
    .word Reset          ; Emu RESET
    .word $0000          ; Emu IRQ/BRK
