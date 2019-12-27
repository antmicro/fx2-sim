# FX2 simulation

FX2 SoC simulation using Migen and Litex.
The 8051 CPU implementation uses Verilog sources from [turbo8051](https://github.com/freecores/turbo8051).

## Setup

To install required dependencies run the script `setup.sh`.
It should be run from withing a Python virtual environment (`python -m venv`).
All required git repositories are downloaded to `INSTALL_DIR`, defaults to `../fx2-sim-env`.
Some dependencies may not be installed automatically, `setup.sh` will list those at the end.

## Running

To run the simulation specify binary file to be loaded, e.g.

```
python fx2/sim.py test/simple.bin
```

To build all the example binaries, run `make -C test/`.

Results can be viewed using GTKWave `gtkwave build/dut.vcd`,
or starting from already prepared GTKWave save `gtkwave sim.gtkw`.
