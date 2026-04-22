.setcpu "65816"
.smart on

; ------------------------------------------------------------
; SNES PAL demo (LoROM):
; - Hardware-safe init sequence
; - Mode 1
; - BG1 only (4bpp tiles, 16-color palette)
; - Shows one 16x16 character made from four 4bpp 8x8 tiles
;
; NOTE: This demo uses 4bpp assets only (16-color palette, indices 0..15).
; In Mode 1, BG1 and BG2 are 4bpp, BG3 would be 2bpp. The mode 0 demo in
; this project ships its own separate 2bpp asset set under build/mode0_2bpp/.
; ------------------------------------------------------------

INIDISP   = $2100
BGMODE    = $2105
BG1SC     = $2107
BG12NBA   = $210B
BG1HOFS   = $210D
BG1VOFS   = $210E
VMAIN     = $2115
VMADDL    = $2116
VMADDH    = $2117
VMDATAL   = $2118
VMDATAH   = $2119
CGADD     = $2121
CGDATA    = $2122
TM        = $212C
TS        = $212D
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

BG_CHAR_X = 14
BG_CHAR_Y = 11
BG_POS    = BG_CHAR_Y * 32 + BG_CHAR_X

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

    ; PPU setup for Mode 1 (BG1/BG2 = 4bpp, BG3 = 2bpp), BG1 only.
    lda #$01
    sta BGMODE
    ; BG1SC: top 6 bits = tilemap VRAM base (in 1K-word steps), low 2 bits = size.
    ; Tilemap is uploaded at word $1000 => base index 4 => register value $10.
    lda #$10            ; BG1 tilemap @ word $1000, 32x32
    sta BG1SC
    stz BG12NBA         ; BG1 4bpp tile base @ VRAM word $0000
    stz BG1HOFS
    stz BG1HOFS
    stz BG1VOFS
    stz BG1VOFS

    ; Upload BG1 palette (one 4bpp palette = 16 BGR555 colors = 32 bytes)
    stz CGADD
    lda #$00
    sta DMA0CTRL
    lda #$22
    sta DMA0DEST
    lda #<PaletteData
    sta DMA0SRC
    lda #>PaletteData
    sta DMA0SRC+1
    lda #^PaletteData
    sta DMA0SRCB
    lda #$20            ; 32 bytes
    sta DMA0SIZE
    stz DMA0SIZE+1
    lda #$01
    sta MDMAEN

    ; Upload 18 BG1 tiles in 4bpp format (32 bytes per tile).
    ; Character tiles sit at indices 0,1,16,17; the rest are blank padding
    ; so the character forms a real 2x2 grid in the VRAM tile viewer.
    ; 18 * 32 = 576 bytes ($0240).
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
    lda #$40            ; 576 bytes = $0240
    sta DMA0SIZE
    lda #$02
    sta DMA0SIZE+1
    lda #$01
    sta MDMAEN

    ; Upload full 32x32 tilemap (2048 bytes) at VRAM $1000 (word address)
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

    lda #$01            ; enable BG1 only
    sta TM
    stz TS

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
    .incbin "build/mode1_4bpp/palette.bin"

TileData:
    .incbin "build/mode1_4bpp/tiles.4bpp.chr"

TilemapData:
    .incbin "build/mode1_4bpp/tilemap.bin"

.segment "HEADER"
    ; 21-byte internal title
    .byte "MODE1 16X16 PAL DEMO "
    ; map mode, cart type, ROM size, SRAM size
    ; ROM size byte = ceil(log2(size_in_KiB)); 2^5 KiB = 32 KiB matches the
    ; 32768-byte .sfc produced by snes.cfg.
    .byte $20, $00, $05, $00
    ; destination code: $02 = Europe (PAL)
    .byte $02
    ; fixed value + version. $00 = old-style header (no extended header at
    ; $FFB0-$FFBF). $33 would claim an extended header, which we do not ship.
    .byte $00, $00
    ; complement and checksum (fix_checksum.py rewrites these post-link)
    .word $0000
    .word $0000

.segment "VECTORS"
    ; $FFE0-$FFFF vector table layout. Only $FFFC (Emu RESET) is actually
    ; fetched by the CPU on power-on; native RESET does not exist.
    .word $0000          ; $FFE0 Native reserved
    .word $0000          ; $FFE2 Native reserved
    .word $0000          ; $FFE4 Native COP
    .word $0000          ; $FFE6 Native BRK
    .word $0000          ; $FFE8 Native ABORT
    .word Nmi            ; $FFEA Native NMI
    .word $0000          ; $FFEC Native reserved (no native RESET)
    .word Irq            ; $FFEE Native IRQ
    .word $0000          ; $FFF0 Emu reserved
    .word $0000          ; $FFF2 Emu reserved
    .word $0000          ; $FFF4 Emu COP
    .word $0000          ; $FFF6 Emu reserved
    .word $0000          ; $FFF8 Emu ABORT
    .word $0000          ; $FFFA Emu NMI
    .word Reset          ; $FFFC Emu RESET
    .word $0000          ; $FFFE Emu IRQ/BRK
