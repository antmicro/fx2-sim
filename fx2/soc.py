from migen import *

from litex.soc.interconnect import csr, csr_bus, wishbone, wishbone2csr
from litex.soc.interconnect.csr import CSRStatus, CSRAccess
import litex.soc.interconnect.csr
from litex.build.generic_platform import CRG

from .core import MCS51
from .memory import MainRAM, ScratchRAM, GPIFWaveformsBuffer, EP0Buffer, \
    EP1OutBuffer, EP1InBuffer, EP2468Buffer, FX2CSRBank


# fix error in CSRField as it assumes IntEnum has .values() method, which it does not
# adds clear-on-write attribute
class CSRField(litex.soc.interconnect.csr.CSRField):
    def __init__(self, name, size=1, offset=None, reset=0, description=None, pulse=False,
                 access=None, values=None, clear_on_write=False):
        assert access is None or (access in CSRAccess)
        self.name           = name
        self.size           = size
        self.offset         = offset
        self.reset_value    = reset
        self.description    = description
        self.access         = access
        self.pulse          = pulse
        self.values         = values
        self.clear_on_write = clear_on_write
        Signal.__init__(self, size, name=name, reset=reset)

class CSRStorage(litex.soc.interconnect.csr.CSRStorage):
    def __init__(self, *args, clear_on_write=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.clear_on_write = clear_on_write or []
        # copy clear_on_write from csr fields
        if hasattr(self, 'fields'):
            for f in self.fields.fields:
                if f.clear_on_write:
                    bits = range(f.offset, f.offset + f.size)
                    self.clear_on_write.extend(list(bits))
        assert len(set(self.clear_on_write)) == len(self.clear_on_write), \
            'Found duplicates: %s' % self.clear_on_write


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


class FX2USB(Module):
    def __init__(self, csr_bank, platform):
        self.csr_bank = csr_bank

        usbirq = self.csr_bank.add(0xe65d, CSRStorage(name='usbirq',fields=[
            CSRField(name='sudav',   size=1, offset=0, clear_on_write=True),
            CSRField(name='sof',     size=1, offset=1, clear_on_write=True),
            CSRField(name='sutok',   size=1, offset=2, clear_on_write=True),
            CSRField(name='susp',    size=1, offset=3, clear_on_write=True),
            CSRField(name='ures',    size=1, offset=4, clear_on_write=True),
            CSRField(name='hsgrant', size=1, offset=5, clear_on_write=True),
            CSRField(name='ep0ack',  size=1, offset=6, clear_on_write=True),
        ]))

        # TODO: implement possibility to add multibyte CSRS?
        setupdat = [self.csr_bank.add(0xe6b8 + i, CSRStorage(name='setupdat%d' % i, size=8)) for i in range(8)]

        # SOF frame number
        self.csr_bank.add(0xe684, CSRStorage(name='usbframeh', size=8))
        self.csr_bank.add(0xe685, CSRStorage(name='usbframel', size=8))

        self.csr_bank.add(0xe6a0, CSRStorage(name='ep0cs', fields=[
            CSRField(name='stall', offset=0),
            CSRField(name='busy',  offset=1, access=CSRAccess.ReadOnly),  # set by hardware
            CSRField(name='hsnak', offset=7, clear_on_write=True),
        ]))

        self.csr_bank.add(0xe68a, CSRStorage(name='ep0bch', size=8))
        self.csr_bank.add(0xe68b, CSRStorage(name='ep0bcl', size=8))



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
        ]
        slaves = [(slave.mem_decoder(), slave.bus) for slave in slaves] + (wb_slaves or [])
        self.submodules.wb_interconn = wishbone.InterconnectShared(masters, slaves, register=True)

        self.submodules.usb = FX2USB(self.csr_bank, self.platform)
