# FX2 simulation

FX2 SoC simulation using Migen and Litex.
The 8051 CPU implementation uses Verilog sources from [turbo8051](https://github.com/freecores/turbo8051).

## Setup

To install required dependencies run the script `setup.sh`.
It should be run from withing a Python virtual environment (`python -m venv`).
All required git repositories are downloaded to `INSTALL_DIR`, defaults to `../fx2-sim-env`.
Some dependencies may not be installed automatically, `setup.sh` will list those at the end.

## Running

First build example binaries by invoking `make -C firmware`.

To run the simulation specify binary file to be loaded, e.g.

```
python -m fx2.sim firmware/8051/clkspd.bin
```

Results can be viewed using GTKWave `gtkwave build/dut.vcd`,
or starting from an already prepared GTKWave save `gtkwave gtkwave/sim.gtkw`.
