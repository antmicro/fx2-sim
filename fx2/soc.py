from migen import *

from litex.soc.interconnect import csr, csr_bus, wishbone, wishbone2csr
from litex.soc.interconnect.csr import CSRAccess, CSRStorage
from litex.build.generic_platform import CRG

from .core import MCS51
from .memory import MainRAM, ScratchRAM, GPIFWaveformsBuffer, EP0Buffer, \
    EP1OutBuffer, EP1InBuffer, EP2468Buffer, FX2CSRBank, CSRStorage8, CSRField8


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
        cpucs = csr_bank.add(0xe600, CSRStorage8(name='cpucs', fields=[
            CSRField8(name='clkspd', size=2, offset=3),
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
    def __init__(self, fx2):
        self.fx2 = fx2 # backreference
        csr_bank = self.fx2.csr_bank

        usbirq = csr_bank.add(0xe65d, CSRStorage8(name='usbirq',fields=[
            CSRField8(name='sudav',   size=1, offset=0, clear_on_write=True),
            CSRField8(name='sof',     size=1, offset=1, clear_on_write=True),
            CSRField8(name='sutok',   size=1, offset=2, clear_on_write=True),
            CSRField8(name='susp',    size=1, offset=3, clear_on_write=True),
            CSRField8(name='ures',    size=1, offset=4, clear_on_write=True),
            CSRField8(name='hsgrant', size=1, offset=5, clear_on_write=True),
            CSRField8(name='ep0ack',  size=1, offset=6, clear_on_write=True),
        ]))

        csr_bank.add(0xe6b8, CSRStorage(name='setupdat', size=8 * 8))

        # SOF frame number
        csr_bank.add(0xe684, CSRStorage8(name='usbframeh', size=8))
        csr_bank.add(0xe685, CSRStorage8(name='usbframel', size=8))

        csr_bank.add(0xe6a0, CSRStorage8(name='ep0cs', fields=[
            CSRField8(name='stall', offset=0),
            CSRField8(name='busy',  offset=1, access=CSRAccess.ReadOnly),  # set by hardware
            CSRField8(name='hsnak', offset=7, clear_on_write=True, reset=1),
        ]))

        csr_bank.add(0xe68a, CSRStorage8(name='ep0bch', size=8))
        csr_bank.add(0xe68b, CSRStorage8(name='ep0bcl', size=8))

        togctl = csr_bank.add(0xe683, CSRStorage8(name='togctl', fields=[
            CSRField8(name='ep', offset=0, size=4),
            CSRField8(name='io', offset=4),
            CSRField8(name='r',  offset=5, pulse=True),
            CSRField8(name='s',  offset=6, pulse=True),
            CSRField8(name='q',  offset=7, access=CSRAccess.ReadOnly),
        ]))
        # USB requires data toggle synchronisation (DATA0/DATA1, see USB 2.0 Specification 8.6)
        # each endpoint has one toggle bit, except for EP1, we store them as:
        # [ EP0, _, EP1OUT, EP1IN, EP2, _, EP4, _, EP6, _, EP8, _ ]
        # [ EP0, EP1OUT, EP1IN, EP2, EP4, EP6, EP8 ]
        #  ep2toggle_index = lambda ep, io: 2 * ep + (io if ep == 1 else 0)
        ep_numbers = [0, 1, 2, 4, 6, 8]
        def ep2toggle_index(ep, io):
            assert ep in ep_numbers and io in [0, 1], 'ep: %s, io: %s' % (ep, io)
            if ep == 0:
                return 0
            elif ep == 1:
                return 1 + io
            else:
                return ep // 2 + 2  # 3-6
        n_toggles = ep2toggle_index(ep_numbers[-1], 1) + 1
        togctl_toggles = Signal(n_toggles, name_override='togctl_toggles')

        def generate_ep_io_cases(assignment):
            ep_cases = {}
            for ep in ep_numbers:
                toggle = lambda ep, io: togctl_toggles[ep2toggle_index(ep, io)]
                io_cases = {io: assignment(toggle(ep, io)) for io in [0, 1]}
                ep_cases[ep] = Case(togctl.fields.io, io_cases)
            return Case(togctl.fields.ep, ep_cases)

        # assign to Q based on EP and IO
        q = togctl.storage[togctl.fields.q.offset]
        self.comb += generate_ep_io_cases(lambda toggle: q.eq(toggle))

        # set/reset toggles based on EP and IO, S sets DATA1 (bit = 1), R sets DATA0
        DATA1, DATA0 = 1, 0
        self.sync += [
            If(togctl.fields.s, generate_ep_io_cases(lambda toggle: toggle.eq(DATA1)))
            .Elif(togctl.fields.r, generate_ep_io_cases(lambda toggle: toggle.eq(DATA0)))
        ]

        # storage for autopointer data
        csr_bank.add(0xe67b, CSRStorage8(name='xautodat1', size=8))
        csr_bank.add(0xe67c, CSRStorage8(name='xautodat2', size=8))




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

        self.submodules.usb = FX2USB(self)
