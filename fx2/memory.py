from migen import *

from litex.soc.interconnect import csr, csr_bus, wishbone, wishbone2csr
from litex.soc.interconnect.csr import CSR, CSRField, CSRStorage, CSRAccess


def _data_bus():
    """Wishbone data bus used in FX2"""
    return wishbone.Interface(data_width=8, adr_width=16)


def _mem_decoder(start_address, size, block_size):
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


class FX2RAMArea(Module):
    """
    Base class for FX2 RAM areas.
    Implements address decoding and methods for wishbone to memory connection.
    """

    # maximum block size that we can use to simplify address decoding
    _ram_decoder_block_size = 64
    _ram_areas = {  # TRM 5.6
        'main_ram':       (0x0000, 16 * 2**10),
        'scratch_ram':    (0xe000, 512),
        'gpif_waveforms': (0xe400, 128),
        'ezusb_csrs':     (0xe500, 512),
        'ep0inout':       (0xe740, 64),
        'ep1out':         (0xe780, 64),
        'ep1in':          (0xe7c0, 64),
        'ep2468':         (0xf000, 4 * 2**10),
    }

    @property
    def _ram_area(self):
        raise NotImplementedError('Deriving class should set self._ram_area attribute')

    @property
    def base_address(self):
        return self._ram_areas[self._ram_area][0]

    @property
    def size(self):
        return self._ram_areas[self._ram_area][1]

    def mem_decoder(self):
        # decoding of main_ram is much simpler
        if self._ram_area == 'main_ram':
            # select main RAM only for address below area size (so all other bits are 0)
            adr_w = log2_int(self.size, need_pow2=True)
            return lambda adr: adr[adr_w:] == 0
        else:  # all other areas
            return _mem_decoder(self.base_address, self.size, self._ram_decoder_block_size)

    def local_adr(self, adr):
        # perform address translation so that memory has zero-based address
        local_adr = adr - self.base_address
        return local_adr

    def connect_wb_port(self, port, bus):
        self.comb += [
            # wishbone.InterconnectShared enables bus.cyc depending on bus.sel,
            # so we don't need to decode it, just use bus.cyc as selector
            port.we.eq(bus.cyc & bus.stb & bus.we),
            port.adr.eq(self.local_adr(bus.adr)[:len(port.adr)]),
            bus.dat_r.eq(port.dat_r),
            port.dat_w.eq(bus.dat_w),
        ]

    def add_wb_ack(self, bus):
        self.sync += [
            bus.ack.eq(0),
            If(bus.cyc & bus.stb & ~bus.ack, bus.ack.eq(1)),
        ]


class RAMBuffer(FX2RAMArea):
    """
    Simple RAM buffer used for basic data storage.
    """

    @property
    def _ram_area(self):
        return self._area

    def __init__(self, ram_area, init=None):
        self._area = ram_area
        self.bus = _data_bus()

        # create memory with regular 8-bit port
        mem = Memory(8, self.size, init=init or [0x00] * self.size, name='mem_%s' % ram_area)
        port = mem.get_port(write_capable=True)
        self.specials += [mem, port]

        self.connect_wb_port(port, self.bus)
        self.add_wb_ack(self.bus)


ScratchRAM          = lambda: RAMBuffer('scratch_ram')
GPIFWaveformsBuffer = lambda: RAMBuffer('gpif_waveforms')
EP0Buffer           = lambda: RAMBuffer('ep0inout')
EP1OutBuffer        = lambda: RAMBuffer('ep1out')
EP1InBuffer         = lambda: RAMBuffer('ep1in')
EP2468Buffer        = lambda: RAMBuffer('ep2468')


class MainRAM(FX2RAMArea):
    """
    Main FX2 RAM that is used for both program and data.
    It has 32-bit data interface but access does not have to be 32-bit aligned.
    This module performs address decoding. Main RAM is located starting at address
    0x0000, so decoding is fairly simple.
    """

    _ram_area = 'main_ram'

    def __init__(self, init):
        init = init + [0x00] * (self.size - len(init))
        self.mem = Memory(8, self.size, init=init, name='mem_main_ram')

        self.ibus = csr_bus.Interface(data_width=32, address_width=16, alignment=8)
        self.dbus = self.bus = _data_bus()

        self.add_ibus_port()
        self.add_dbus_port()

    def add_ibus_port(self):
        # construct 32-bit data bus from 4 ports
        p1, p2, p3, p4 = [self.mem.get_port(write_capable=False) for i in range(4)]
        self.specials += [self.mem, p1, p2, p3, p4]
        port_dat_r = Cat(p1.dat_r, p2.dat_r, p3.dat_r, p4.dat_r)

        self.comb += [
            # read 4 consecutive bytes
            p1.adr.eq(self.ibus.adr + 0),
            p2.adr.eq(self.ibus.adr + 1),
            p3.adr.eq(self.ibus.adr + 2),
            p4.adr.eq(self.ibus.adr + 3),
            self.ibus.dat_r.eq(port_dat_r),
        ]

    def add_dbus_port(self):
        port = self.mem.get_port(write_capable=True)
        self.specials += port
        self.connect_wb_port(port, self.dbus)
        self.add_wb_ack(self.dbus)


class CSRField8(CSRField):
    """
    CSRField modifications that adds clear_on_write argument and fixes error in original
    CSRField, which assumes that IntEnum has .values() method.
    """
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


class CSRStorage8(CSRStorage):
    """
    CSRStorage modification that only supports 8-bit registers, but implements
    clear-on-write and read-only features, either passed as CSRField8 arguments
    or directly to CSRStorage8 constructor.
    """
    def __init__(self, *args, clear_on_write=None, field_access=None, **kwargs):
        super().__init__(*args, **kwargs)

        # bit-related attributes important during generation
        self.clear_on_write = clear_on_write or []
        self.field_access = field_access or {} # {bit: CSRAccess}

        # copy attributes from csr fields
        if hasattr(self, 'fields'):
            for f in self.fields.fields:
                bits = range(f.offset, f.offset + f.size)
                if f.clear_on_write:
                    self.clear_on_write.extend(list(bits))
                for bit in bits:
                    assert bit not in self.field_access, 'Bit %d access set more than once' % bit
                    self.field_access[bit] = f.access

        assert len(set(self.clear_on_write)) == len(self.clear_on_write), \
            'Found duplicates: %s' % self.clear_on_write

    def do_finalize(self, busword):
        nwords = (self.size + busword - 1)//busword
        # construct storage
        assert busword == 8 and nwords == 1, 'Only 1-byte CSRStorage is supposed'
        sc = CSR(self.size, self.name)
        self.simple_csrs.append(sc)
        #
        for bit in range(self.size):
            access = self.field_access.get(bit, CSRAccess.ReadWrite)
            if access == CSRAccess.WriteOnly:
                raise NotADirectoryError()
            # write only if the register is not read-only
            if access != CSRAccess.ReadOnly:
                if bit in self.clear_on_write:
                    # write 0 only if there is write and it is writing 1
                    self.sync += If(sc.re & sc.r[bit], self.storage[bit].eq(0))
                else:
                    self.sync += If(sc.re, self.storage[bit].eq(sc.r[bit]))
        self.sync += self.re.eq(sc.re)
        # read
        self.comb += sc.w.eq(self.storage)


class FX2CSRBank(FX2RAMArea):
    """
    Bank of CSRs in memory.
    This should be the central object for registering and retreiving CSRs (add/get methods).
    """

    _ram_area = 'ezusb_csrs'

    def __init__(self):
        self.bus = _data_bus()
        self._csrs = {}
        self._csrs_by_name = {}

    def do_finalize(self):
        # bus assignments delayed to do_finalize so that all the csrs have already been added

        # override csr storage names (defaults to something like csrstorageN_storageM)
        for csr in self._csrs.values():
            csr.storage.name_override = self.csr_storage_name(csr)

        # finalize compound csrs to get simple csrs, we only support simple csrs
        self.simple_csrs = {}
        for adr, csr in self._csrs.items():
            if isinstance(csr, CSR):
                self.simple_csrs[adr] = csr
            else:
                csr.finalize(8)
                simple = csr.get_simple_csrs()
                if len(simple) == 1:
                    self.simple_csrs[adr] = simple[0]
                else:
                    assert not isinstance(csr, CSRStorage8), 'CSRStorage8 does not support multi-word CSRs'
                    for s, a in zip(simple, range(adr, adr + len(simple))):
                        self.simple_csrs[a] = s
                self.submodules += csr

        # connect all simple csrs to bus with address decoding logic
        read_cases = {}
        for adr, csr in self.simple_csrs.items():
            for bit in range(csr.size):
                wr_val = self.bus.dat_w[bit]
                self.comb += csr.r[bit].eq(wr_val)
            self.comb += [
                csr.re.eq(self.bus.we & (self.bus.adr == adr)),
                csr.we.eq(~self.bus.we & (self.bus.adr == adr)),
            ]
            read_cases[adr] = self.bus.dat_r.eq(csr.w)

        # add data reads
        self.sync += [
            self.bus.dat_r.eq(0),
            Case(self.bus.adr, read_cases),
        ]

        self.add_wb_ack(self.bus)

    def csr_storage_name(self, csr):
        return 'fx2csr_' + csr.name

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
