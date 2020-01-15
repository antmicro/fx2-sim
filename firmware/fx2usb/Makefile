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

$(TARGET).bin: $(TARGET).ihex
	hex2bin.py $< $@

all: $(TARGET).bin

clean: clean-libfx2 clean-bin

clean-libfx2:
	$(MAKE) -C $(LIBFX2) clean

clean-bin:
	rm -f main.bin

.PHONY: all clean clean-libfx2 clean-bin
