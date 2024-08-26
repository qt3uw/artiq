import logging
import unittest

from migen import *

from artiq.gateware.szservo.dac_ser3 import DAC, DACParams
from artiq.language.units import us, ns


start_delay = 14
dac_p = DACParams(channels=8, data_width = 24, 
    clk_width = 2)

t_spi_cycle = (dac_p.data_width*2*dac_p.clk_width + 1) + 3
t_cycle =  (t_spi_cycle)*dac_p.channels + 1 


class TB(Module):
    def __init__(self, dac_p):
        self.sdi = Signal()
        self.sclk = Signal()

        self.ldac = Signal(reset = 1)
        # self.busy = Signal(reset = 1)
        self.syncr = Signal(reset = 1)
        self.clr = Signal()



class DACSim(DAC):
    def __init__(self):
    
        self.submodules.dac_tb = TB(dac_p)
    
        self.submodules.dac = DAC(self.dac_tb, dac_p)

        cnt_done = Signal()
        cnt = Signal(max=t_cycle)
        load_cnt = Signal(max = t_cycle)

        assert start_delay <= 50
        start_cnt = Signal(max=50 + 1, reset = start_delay)
        start_done = Signal()

        self.comb += [
             cnt_done.eq(cnt == 0), 

             start_done.eq(start_cnt == 0)
        ]

        self.sync += [
            If(cnt_done,
                If(load_cnt,
                    cnt.eq(load_cnt - 1)
                )
            ).Else(
                cnt.eq(cnt - 1)
            ),
            If(~start_done,
                start_cnt.eq(start_cnt - 1)
            )
        ]

        self.comb += [
            self.dac.dac_init.eq(~self.dac.initialized & start_done),
            self.dac.dac_start.eq(self.dac.initialized & cnt_done),
            If(self.dac.dac_start,
                load_cnt.eq(t_cycle)
            ).Elif(self.dac.dac_init,
                load_cnt.eq(t_spi_cycle + 1)
            )
        ]

    def test(self):
        dut = self.dac
        prof0 =0x90CB000000008FF1
        prof1 = 0xA011000000008FF1
        

        for i in range (dac_p.channels):
            yield dut.profile[i].eq(prof0 + 0x2000000000000000*i)
            # yield dut.profile[i].eq(0xA + i)

        for i in range(start_delay + 3):
            yield

        while not (yield dut.initialized):
            yield
        yield
        yield
        yield
        while not (yield dut.dac_ready):
            yield
        yield

        for i in range(100):
            yield        

def main():
    dac = DACSim()
    run_simulation(dac, dac.test(), vcd_name = "dac_ser3.vcd")

    
if __name__ == "__main__":
    print(t_spi_cycle)
    print(t_spi_cycle*8*ns)

    logging.basicConfig(level=logging.DEBUG)
    main()