from migen import *
from artiq.gateware.rtio import rtlink

class Output(Module):

    def __init__(self, pad0, pad1):
        self.rtlink = rtlink.Interface(rtlink.OInterface(2))
        reg = Signal()
        pad0_o = Signal()

        ###
        self.sync.rtio += [
            If(self.rtlink.o.stb,
                reg.eq(self.rtlink.o.data[0]),
                pad0_o.eq(self.rtlink.o.data[1])
            )
        ]

        self.comb += [
            pad0.eq(pad0_o),
            If(reg,
                pad1.eq(pad0_o)
            )
        ]