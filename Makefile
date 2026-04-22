.PHONY: all clean

MODE1_ASSETS := \
    build/mode1_4bpp/palette.bin \
    build/mode1_4bpp/tiles.4bpp.chr \
    build/mode1_4bpp/tilemap.bin \
    build/mode1_4bpp/preview.png

MODE0_ASSETS := \
    build/mode0_2bpp/palette.bin \
    build/mode0_2bpp/tiles.2bpp.chr \
    build/mode0_2bpp/tilemap.bin \
    build/mode0_2bpp/preview.png

MODE5_ASSETS := \
    build/mode5_2bpp/palette.bin \
    build/mode5_2bpp/tiles.2bpp.chr \
    build/mode5_2bpp/tilemap.bin \
    build/mode5_2bpp/preview.png

all: build/mode1_pal_demo.sfc build/mode0_pal_demo.sfc build/mode5_pal_demo.sfc

build:
	mkdir -p build

$(MODE1_ASSETS): tools/gen_assets.py | build
	python3 tools/gen_assets.py mode1_4bpp

$(MODE0_ASSETS): tools/gen_assets.py | build
	python3 tools/gen_assets.py mode0_2bpp

$(MODE5_ASSETS): tools/gen_assets.py | build
	python3 tools/gen_assets.py mode5_2bpp

build/main_mode1_4bpp.o: main_mode1_4bpp.s $(MODE1_ASSETS)
	ca65 -t none -o $@ main_mode1_4bpp.s

build/main_mode0_2bpp.o: main_mode0_2bpp.s $(MODE0_ASSETS)
	ca65 -t none -o $@ main_mode0_2bpp.s

build/main_mode5_2bpp.o: main_mode5_2bpp.s $(MODE5_ASSETS)
	ca65 -t none -o $@ main_mode5_2bpp.s

build/mode1_pal_demo.sfc: build/main_mode1_4bpp.o snes.cfg
	ld65 -C snes.cfg -o $@ $<
	python3 tools/fix_checksum.py $@

build/mode0_pal_demo.sfc: build/main_mode0_2bpp.o snes.cfg
	ld65 -C snes.cfg -o $@ $<
	python3 tools/fix_checksum.py $@

build/mode5_pal_demo.sfc: build/main_mode5_2bpp.o snes.cfg
	ld65 -C snes.cfg -o $@ $<
	python3 tools/fix_checksum.py $@

clean:
	rm -rf build
