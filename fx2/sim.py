import sys
import argparse

from migen import *

from litex.soc.interconnect import csr, csr_bus

from litex.build.generic_platform import Pins
from litex.build.sim.platform import SimPlatform
from litex.build.sim.config import SimConfig

from soc import FX2


class SimPins(Pins):
    def __init__(self, n=1):
        Pins.__init__(self, "s "*n)


_io = [
    ("sys_clk", 0, SimPins(1)),
    ("sys_rst", 0, SimPins(1)),
]


def parse_args():
    desc = 'Run FX2 simulation'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('binary', nargs='?',
                        help='Path to binary file with FX2 program')
    return parser.parse_args()


def main():
    args = parse_args()

    code = None
    if args.binary:
        with open(args.binary, 'rb') as f:
            code = list(f.read())

    platform = SimPlatform("sim", _io, toolchain="verilator")
    soc = FX2(platform, clk_freq=48e6, code=code)
    config = SimConfig(default_clk='sys_clk')
    platform.build(soc, sim_config=config, build=True, run=True, trace=True)


if __name__ == "__main__":
    main()
