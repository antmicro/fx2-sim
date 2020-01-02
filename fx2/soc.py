from migen import *

from litex.soc.interconnect import csr, csr_bus, wishbone, wishbone2csr
from litex.soc.interconnect.csr import CSRField, CSRStatus, CSRStorage
from litex.build.generic_platform import CRG

from .core import MCS51
from .memory import MainRAM, ScratchRAM, GPIFWaveformsBuffer, EP0Buffer, \
    EP1OutBuffer, EP1InBuffer, EP2468Buffer, FX2CSRBank


class FX2CRG(Module):
    """
    Clock and reset generator with clock divider depending on FX2 registers.
    """
    def __init__(self, csr_bank, clk, rst=0):
        self.clock_domains.cd_sys = ClockDomain()
        self.clock_domains.cd_por = ClockDomain(reset_less=True)

        # Power on Reset (vendor agnostic)
        int_rst = Signal(reset=1)
        self.sync.por += int_rst.eq(0)

        # implements CLKSPD divider from CPUCS register
        cpucs = csr_bank.add(0xe600, CSRStorage(name='cpucs', fields=[
            CSRField(name='clkspd', size=2, offset=3),
        ]))

        reload = Signal(2)
        counter = Signal(2)
        divider = {
                0b00: 4,
                0b01: 2,
                0b10: 1,
                0b11: 4, # reserved, just use default?
        }
        self.sync.por += [
            # set reload register value based on CLKSPD
            Case(cpucs.fields.clkspd,
                 {val: reload.eq(div - 1) for val, div in divider.items()}),
            If(counter == 0,
               counter.eq(reload),  # reload counter
               self.cd_sys.clk.eq(~self.cd_sys.clk),  # tick on our clock
            ).Else(
                counter.eq(counter - 1)
            )
        ]

        self.comb += [
            self.cd_sys.rst.eq(int_rst | rst),
            self.cd_por.clk.eq(clk),
        ]

    def get_csrs(self):
        return {0xe600: self.cpucs}


class FX2(Module):
    """
    FX2LP SoC with MCS51 core.

    Originally 8051 has:
      * 256 bytes of internal RAM:
        0x00 - 0x2f - register banks, bit addressable registers
        0x2f - 0x7f - free memory used for stack (80 bytes of stack)
        0x80 - 0xff - SFRs, so pin registers, timer registers, etc.
      * ROM:
        it can have up to 64K of external ROM
        ROM usage depends on EA pin
        EA=1: 4K internal (0x0000 - 0x3fff) and 0x4000 - 0xffff external
        EA=0: 64K external 0x0000 - 0xffff
    EZ-UZB FX2LP has a little different memory model -
    it has one address space, with both code and data:
        0x0000-0x3fff - main RAM (16KB)
        0xe000-0xe1ff - scratch RAM (512B)
        0xe200-0xffff - CSRs and endpoint buffers (7.5KB)

    Out CPU core has CSR bus for innstructions and wishbone for data.
    CSR bus is connected directly to Main RAM and is read-only.
    Wishbone data bus is connected to all slaves. This is safe, as
    the CPU will set mem_wait=1 when any master uses the data bus.
    """
    def __init__(self, platform, clk_freq, code, wb_masters=None, wb_slaves=None):
        self.platform = platform

        self.submodules.cpu = MCS51(self.platform)

        # memories
        self.submodules.main_ram = MainRAM(init=code)
        self.submodules.scratch_ram = ScratchRAM()
        self.submodules.gpif_waveforms = GPIFWaveformsBuffer()
        self.submodules.csr_bank = FX2CSRBank()
        self.submodules.ep0 = EP0Buffer()
        self.submodules.ep1_out = EP1OutBuffer()
        self.submodules.ep1_in = EP1InBuffer()
        self.submodules.ep2468 = EP2468Buffer()

        # connect instruction memory directly using csr bus
        self.submodules.csr_interconn = csr_bus.Interconnect(self.cpu.ibus, [self.main_ram.ibus])

        # connect all wishbone masters and slaves
        masters = [self.cpu.dbus] + (wb_masters or [])
        slaves = [
            self.main_ram,
            self.scratch_ram,
            self.gpif_waveforms,
            self.csr_bank,
            self.ep0,
            self.ep1_out,
            self.ep1_in,
            self.ep2468,
        ] + (wb_slaves or [])
        _slaves = [(slave.mem_decoder(), slave.bus) for slave in slaves]
        self.submodules.wb_interconn = wishbone.InterconnectShared(masters, _slaves, register=True)
