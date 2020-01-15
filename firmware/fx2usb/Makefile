TARGET    = main
LIBRARIES = fx2 fx2usb fx2isrs
MODEL     = small

FLAGS += --std-sdcc99
FLAGS += -Wa"-p"
FLAGS += -DSYNCDELAYLEN=4

LIBFX2  = libfx2/firmware/library
include $(LIBFX2)/fx2rules.mk

# force proper dependecy to automatically build libfx2
$(LIBFX2)/lib/$(MODEL)/fx2.lib: $(LIBFX2)/.stamp

%.bin: %.ihex
	hex2bin.py $< $@
