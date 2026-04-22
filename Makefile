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

MODE5_WALLPAPER_ASSETS := \
    build/mode5_wallpaper_4bpp/palette.bin \
    build/mode5_wallpaper_4bpp/tiles.4bpp.chr \
    build/mode5_wallpaper_4bpp/tilemap.bin \
    build/mode5_wallpaper_4bpp/preview.png

MODE5_WALLPAPER_SRC := assets/linux_wallpaper_512x448_right_4bpp.png

all: build/mode1_pal_demo.sfc build/mode0_pal_demo.sfc build/mode5_pal_demo.sfc build/mode5_wallpaper_pal_demo.sfc

build:
	mkdir -p build

$(MODE1_ASSETS): tools/gen_assets.py | build
	python3 tools/gen_assets.py mode1_4bpp

$(MODE0_ASSETS): tools/gen_assets.py | build
	python3 tools/gen_assets.py mode0_2bpp

$(MODE5_ASSETS): tools/gen_assets.py | build
	python3 tools/gen_assets.py mode5_2bpp

$(MODE5_WALLPAPER_ASSETS): tools/gen_assets.py tools/crop_image.py $(MODE5_WALLPAPER_SRC) | build
	python3 tools/gen_assets.py mode5_image \
	    --source $(MODE5_WALLPAPER_SRC) \
	    --bpp 4 \
	    --name mode5_wallpaper_4bpp

build/main_mode1_4bpp.o: main_mode1_4bpp.s $(MODE1_ASSETS)
	ca65 -t none -o $@ main_mode1_4bpp.s

build/main_mode0_2bpp.o: main_mode0_2bpp.s $(MODE0_ASSETS)
	ca65 -t none -o $@ main_mode0_2bpp.s

build/main_mode5_2bpp.o: main_mode5_2bpp.s $(MODE5_ASSETS)
	ca65 -t none -o $@ main_mode5_2bpp.s

build/main_mode5_4bpp.o: main_mode5_4bpp.s $(MODE5_WALLPAPER_ASSETS)
	ca65 -t none -o $@ main_mode5_4bpp.s

build/mode1_pal_demo.sfc: build/main_mode1_4bpp.o snes.cfg
	ld65 -C snes.cfg -o $@ $<
	python3 tools/fix_checksum.py $@

build/mode0_pal_demo.sfc: build/main_mode0_2bpp.o snes.cfg
	ld65 -C snes.cfg -o $@ $<
	python3 tools/fix_checksum.py $@

build/mode5_pal_demo.sfc: build/main_mode5_2bpp.o snes.cfg
	ld65 -C snes.cfg -o $@ $<
	python3 tools/fix_checksum.py $@

build/mode5_wallpaper_pal_demo.sfc: build/main_mode5_4bpp.o snes.cfg
	ld65 -C snes.cfg -o $@ $<
	python3 tools/fix_checksum.py $@

# ---------------------------------------------------------------------------
# Optional: full-screen Mode 1 background from a user-supplied image.
# Not part of `make all` because the image is a user asset that must not
# be committed (see .gitignore). Usage:
#
#     make mode1_image_demo MODE1_IMAGE_SRC=path/to/your_image.jpg
#
# Writes build/mode1_image/{palette.bin,tiles.4bpp.chr,tilemap.bin,preview.png}
# and build/mode1_image_pal_demo.sfc.
# ---------------------------------------------------------------------------

MODE1_IMAGE_ASSETS := \
    build/mode1_image/palette.bin \
    build/mode1_image/tiles.4bpp.chr \
    build/mode1_image/tilemap.bin \
    build/mode1_image/preview.png

.PHONY: mode1_image_demo

mode1_image_demo: build/mode1_image_pal_demo.sfc

$(MODE1_IMAGE_ASSETS): tools/gen_assets.py tools/crop_image.py | build
	@if [ -z "$(MODE1_IMAGE_SRC)" ]; then \
	    echo "error: set MODE1_IMAGE_SRC=path/to/image.{jpg,png}" >&2; \
	    exit 2; \
	fi
	python3 tools/gen_assets.py mode1_image \
	    --source $(MODE1_IMAGE_SRC) \
	    --crop-align center \
	    --bpp 4 \
	    --name mode1_image

build/main_mode1_image_4bpp.o: main_mode1_image_4bpp.s $(MODE1_IMAGE_ASSETS)
	ca65 -t none -o $@ main_mode1_image_4bpp.s

build/mode1_image_pal_demo.sfc: build/main_mode1_image_4bpp.o snes.cfg
	ld65 -C snes.cfg -o $@ $<
	python3 tools/fix_checksum.py $@

clean:
	rm -rf build
