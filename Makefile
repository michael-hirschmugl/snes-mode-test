TARGET := mode1_pal_demo

.PHONY: all clean

all: build/$(TARGET).sfc build/preview.png

build:
	mkdir -p build

build/palette.bin build/tiles.4bpp.chr build/tilemap.bin build/preview.png: tools/gen_assets.py | build
	python3 tools/gen_assets.py

build/main.o: main.s build/palette.bin build/tiles.4bpp.chr build/tilemap.bin
	ca65 -t none -o $@ main.s

build/$(TARGET).sfc: build/main.o snes.cfg
	ld65 -C snes.cfg -o $@ $<
	python3 tools/fix_checksum.py $@

clean:
	rm -rf build
