from migen import *

from litex.soc.interconnect import csr, csr_bus, wishbone, wishbone2csr
from litex.soc.interconnect.csr import CSR


class MainRAM(Module):
    """
    Main FX2 RAM that is used for both program and data.
    It has 32-bit data interface but access does not have to be 32-bit aligned.
    This module performs address decoding. Main RAM is located starting at address
    0x0000, so decoding is fairly simple.
    """

    def __init__(self, size, init, read_only=False):
        self.bus = csr_bus.Interface(data_width=32, address_width=16, alignment=8)
        mem = Memory(8, size, init=init)

        # select main RAM only for address below size
        adr_w = log2_int(size, need_pow2=True)
        sel = Signal()
        self.comb += sel.eq(self.bus.adr[adr_w:] == 0)
        # delay sel signal so that it is used during read/write, 1 cycle after address is on line
        sel_r = Signal()
        self.sync += sel_r.eq(sel)

        # construct 32-bit data bus from 4 ports
        p1, p2, p3, p4 = [mem.get_port(write_capable=not read_only) for i in range(4)]
        self.specials += [mem, p1, p2, p3, p4]
        port_dat_r = Cat(p1.dat_r, p2.dat_r, p3.dat_r, p4.dat_r)
        port_dat_w = Cat(p1.dat_w, p2.dat_w, p3.dat_w, p4.dat_w)

        self.comb += [
            # read 4 consecutive bytes
            p1.adr.eq(self.bus.adr + 0),
            p2.adr.eq(self.bus.adr + 1),
            p3.adr.eq(self.bus.adr + 2),
            p4.adr.eq(self.bus.adr + 3),
            # only when selected, else there is 0 on line so it can be ORed with other signals
            If(sel_r, self.bus.dat_r.eq(port_dat_r)),
        ]

        if not read_only:
            self.comb += [
                p1.we.eq(self.bus.we & sel),
                p2.we.eq(self.bus.we & sel),
                p3.we.eq(self.bus.we & sel),
                p4.we.eq(self.bus.we & sel),
                port_dat_w.eq(self.bus.dat_w),
            ]


class RAMAreaInterface(Module):
    """
    Common interface for FX2 RAM areas. Performs address translation and decoding.
    Memory area modules should use `ram_bus` to connect memory/csrs, and the area
    should be connected to csr bus through `cpu_bus`.
    """

    # maximum block size that we can use to simplify address decoding
    block_size = 64
    # TRM 5.6
    mem_areas = {
        'scratch_ram':    (0xe000, 512),
        'gpif_waveforms': (0xe400, 128),
        'ezusb_csrs':     (0xe500, 512),
        'ep0inout':       (0xe740, 64),
        'ep1out':         (0xe780, 64),
        'ep1in':          (0xe7c0, 64),
        'ep2468':         (0xf000, 4 * 2**10),
    }

    @classmethod
    def get(cls, name):
        start, size = cls.mem_areas[name]
        return RAMAreaInterface(start, size, cls.block_size)

    @staticmethod
    def mem_decoder(start_address, size, block_size):
        """
        Create a memory decoder for a region of given size and starting address.
        Decoding is simplified by assuming that memory is divided into blocks of
        `block_size`. The blocks occupied by the region are calculated and selection
        is performed by testing if the address belongs to one of the blocks.
        """
        n = bits_for(block_size - 1)

        def decoder(adr):
            # find out blocks occupied by given memory area
            blocks = list(range(start_address >> n, (start_address + size) >> n))
            # select peripheral if address is in any of the blocks
            _or = lambda a, b: a | b
            return reduce(_or, [(adr >> n) == block for block in blocks])

        return decoder

    def __init__(self, start_address, size, block_size):
        self.cpu_bus = csr_bus.Interface(data_width=8, address_width=16, alignment=8)
        self.ram_bus = csr_bus.Interface.like(self.cpu_bus)

        # memory region selection
        sel = Signal()
        decoder = self.mem_decoder(start_address, size, block_size)
        self.comb += sel.eq(decoder(self.cpu_bus.adr))
        # delay sel signal so that it is used during read/write, 1 cycle after address is on line
        sel_r = Signal()
        self.sync += sel_r.eq(sel)

        self.comb += [
            self.ram_bus.we.eq(self.cpu_bus.we & sel),
            self.ram_bus.adr.eq(self.cpu_bus.adr - start_address),  # translate the address by area's offset
            If(sel_r, self.cpu_bus.dat_r.eq(self.ram_bus.dat_r)),
            self.ram_bus.dat_w.eq(self.cpu_bus.dat_w),
        ]


class ScratchRAM(Module):
    """512 bytes of data-only RAM"""

    def __init__(self):
        self.submodules.interface = RAMAreaInterface.get('scratch_ram')
        self.bus = self.interface.cpu_bus

        # create memory with regular 8-bit port
        mem = Memory(8, 512)
        port = mem.get_port(write_capable=True)
        self.specials += [mem, port]

        self.comb += self.interface.ram_bus.connect(port)


class FX2CSRBank(Module):
    """
    Bank of CSRs in memory.
    This is a central object for registering and retreiving CSRs (add/get methods).
    """

    def __init__(self):
        self.submodules.interface = RAMAreaInterface.get('ezusb_csrs')
        self._base_adr = RAMAreaInterface.mem_areas['ezusb_csrs'][0]
        self.bus = self.interface.cpu_bus
        self._csrs = {}
        self._csrs_by_name = {}

    def do_finalize(self):
        # bus assignments delayed to do_finalize so that all the csrs have already been added

        # finalize compound csrs to get simple csrs, we only support simple csrs
        self.simple_csrs = {}
        for adr, csr in self._csrs.items():
            if isinstance(csr, CSR):
                self.simple_csrs[adr] = csr
            else:
                csr.finalize(8)
                simple = csr.get_simple_csrs()
                assert len(simple) == 1, 'Found compound CSR - not implemented'
                self.simple_csrs[adr] = simple[0]
                self.submodules += csr

        # connect all simple csrs to bus with address decoding logic
        bus = self.interface.ram_bus
        read_cases = {}
        for adr, csr in self.simple_csrs.items():
            local_adr = adr - self._base_adr
            self.comb += [
                csr.r.eq(bus.dat_w[:csr.size]),
                csr.re.eq(bus.we & (bus.adr == local_adr)),
                csr.we.eq(~bus.we & (bus.adr == local_adr)),
            ]
            read_cases[local_adr] = bus.dat_r.eq(csr.w)

        # add data reads
        self.sync += [
            bus.dat_r.eq(0),
            Case(bus.adr, read_cases),
        ]

    def add(self, address, csr):
        if not csr.name:
            raise ValueError('CSR must have a name: %s' % (csr))
        if address in self._csrs:
            raise ValueError('CSR at address 0x%04x already exists: ' % (address, self._csrs[address].name))
        self._csrs[address] = csr
        self._csrs_by_name[csr.name] = csr
        return csr

    def get(self, name_or_address):
        if isinstance(name_or_address, int):
            return self._csrs[name_or_address]
        else:
            return self._csrs_by_name[name_or_address]
