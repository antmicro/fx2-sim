import os

from migen import *

from litex.soc.interconnect import csr_bus, wishbone


class MCS51(Module):
    """
    8051 CPU core. This is a wrapper around Verilog turbo8051 model.
    """

    def __init__(self, platform, ea=Constant(0)):
        self.platform = platform
        self.interrupt = Signal(2)
        self.ibus = i = csr_bus.Interface(data_width=32, address_width=16, alignment=8)
        self.dbus = d = wishbone.Interface(data_width=8, adr_width=16)

        i.we = Constant(0)
        #  iack = Signal()

        # connect to the verilog 8051 core
        cpu_connections = dict(
            # clock and reset
            i_wb_rst_i  = ResetSignal(),
            i_wb_clk_i  = ClockSignal(),
            # 2 interrupt pins
            i_int0_i    = self.interrupt[0],
            i_int1_i    = self.interrupt[1],
            # external access, EA=1 means that internal ROM is also used
            i_ea_in     = ea,
            # ROM interface, we do not use wishbone so some signals are not used
            o_wbi_adr_o = i.adr,
            i_wbi_dat_i = i.dat_r,  # slave to master
            i_wbi_ack_i = Constant(1),  # data is always valid
            #  i_wbi_err_i = Signal(),
            #  o_wbi_stb_o = Signal(),
            #  o_wbi_cyc_o = Signal(),
            # external data RAM interface
            o_wbd_adr_o = d.adr,
            o_wbd_dat_o = d.dat_w,
            i_wbd_dat_i = d.dat_r,
            o_wbd_we_o  = d.we,
            i_wbd_ack_i = d.ack,
            i_wbd_err_i = d.err,
            o_wbd_stb_o = d.stb,
            o_wbd_cyc_o = d.cyc,
        )
        self.specials += Instance("oc8051_top", **cpu_connections)

        vdir = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), "verilog")
        platform.add_sources(os.path.join(vdir, "rtl", "8051", "oc8051_top.v"))
        platform.add_verilog_include_path(os.path.join(vdir, "rtl", "8051"))
        platform.add_verilog_include_path(os.path.join(vdir, "rtl", "defs"))
