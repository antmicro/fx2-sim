from migen import *

from litex.soc.interconnect import csr, csr_bus, wishbone, wishbone2csr
from litex.soc.interconnect.csr import CSRField, CSRStatus, CSRStorage
from litex.build.generic_platform import CRG

from core import MCS51
from memory import MainRAM, ScratchRAM, FX2CSRBank


class FX2CRG(Module):
    """ Clock and Reset Generator """

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
            self.cd_sys.rst.eq(int_rst),
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
    """

    def __init__(self, platform, clk_freq, code):
        self.platform = platform

        self.submodules.cpu = MCS51(platform)
        self.submodules.csr_bank = FX2CSRBank()

        self.submodules.crg = FX2CRG(self.csr_bank, clk=platform.request("sys_clk"))

        self.submodules.main_ram = MainRAM(16 * 2**10, init=code, read_only=False)
        self.submodules.scratch_ram = ScratchRAM()

        # construct data interface wrapper as cpu model uses wishbone
        dbus_csr = csr_bus.Interface(data_width=8, address_width=16, alignment=8)
        self.submodules.dbus = wishbone2csr.WB2CSR(bus_wishbone=self.cpu.dbus, bus_csr=dbus_csr)

        # create an arbiter that will choose master depending on wishbone dbus strobe,
        # as whenever core wants to read/write data, it will stop fetching instructions
        self.bus_master = csr_bus.Interface.like(self.cpu.ibus)  # ibus is wider
        dbus_active = self.dbus.wishbone.stb
        m, i, d = self.bus_master, self.cpu.ibus, self.dbus.csr
        self.comb += [
            If(dbus_active, m.adr  .eq(d.adr  )).Else(m.adr  .eq(i.adr  )),
            If(dbus_active, m.we   .eq(d.we   )).Else(m.we   .eq(i.we   )),
            If(dbus_active, m.dat_w.eq(d.dat_w)).Else(m.dat_w.eq(i.dat_w)),
            If(dbus_active, d.dat_r.eq(m.dat_r)).Else(i.dat_r.eq(m.dat_r)),
        ]

        # interconnect slaves
        self.submodules.csr_interconn = csr_bus.Interconnect(self.bus_master, [
            self.main_ram.bus,
            self.scratch_ram.bus,
            self.csr_bank.bus,
        ])
