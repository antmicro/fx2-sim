SOURCES = loop.c withstack.c xram.c clkspd.c
ASM_SOURCES = simple.asm

all: all_c all_asm

all_c: $(SOURCES:.c=.bin) $(SOURCES:.c=.ihx) # create ihex files too, prevent "removing intermediate files"

all_asm: $(ASM_SOURCES:.asm=.bin)


# general riles
%.ihx: %.c
	sdcc -mmcs51 $<

%.bin: %.ihx
	hex2bin.py $< $@



# special rules for simple program
simple.rel: simple.asm
	sdas8051 -plo $@ $<

simple.ihx: simple.rel
	sdld -ni $@ $<


# some ugly rules for printing
DISASSEBLE_N_LINES = 65

disassemble-%: %.ihx
	@echo
	echo 'dis 0 0 $(DISASSEBLE_N_LINES)' | s51 -t 8051 $<

hexdump-%: %.bin
	@echo
	hexdump -C $<


clean:
	rm -f *.lk *.bin *.ihx *.rel *.rst *.rst *.sym *.map *.mem *.lst $(SOURCES:.c=.asm)

.PHONY: all all_c all_asm clean
