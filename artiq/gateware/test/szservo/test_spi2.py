from migen import *
import unittest

from artiq.gateware.szservo.spi2 import SPI2, SPIParams
from artiq.language.units import us, ns


AD53XX_CMD_OFFSET = 2 << 22
AD53XX_SPECIAL_OFS0 = 2 << 16

start_delay = 4

class TB(Module):
    def __init__(self, params):
        self.sclk = Signal()
        self.sdi = Signal()

        self.syncr = Signal(reset=1)
        self.ldac = Signal()
        # self.busy = Signal(reset = 1)
        # self.clr = Signal(reset=1)

class SPISim(SPI2):
    def __init__(self):
        self.spi_p = spi_p = SPIParams(channels=2, data_width = 24, 
            clk_width = 2)

        # +3 in t_cycle is needed to delay driving SYNCR line low - it needs to be at least 20 ns wide
        # which with 8 ns of Kasli clock is 3 clock cycles. To ensure that IC accepts SYNCR, it is driven high
        # for 4 clock cycles - 32 ns
        t_cycle =  (spi_p.data_width*2*spi_p.clk_width + 1) + 3 
        print(t_cycle)
        print(t_cycle* 8*ns)
        self.submodules.spi_tb = TB(spi_p)
        
        self.submodules.spi = SPI2(self.spi_tb, spi_p)
        
        self.sim_start = Signal()

        cnt_done = Signal()
        cnt = Signal(max=t_cycle)
        load_cnt = Signal()
        
        assert start_delay <= 50
        start_cnt = Signal(max=50 + 1, reset = start_delay)
        start_done = Signal()

        # DZIALA z opoznianiem!!!!!
        # ---------------------------
        # # assert start_delay <= 50 - 3
        # # start_cnt = Signal(max=50 + 1, reset = start_delay + 3)
        # # start_done = Signal()

        # # self.comb += [
        # #      cnt_done.eq(cnt == 0), 
        # #      start_done.eq((start_cnt == 2) | (start_cnt == 1) | (start_cnt == 0))
        # # ]

        # # self.sync += [
        # #     If(start_done,
        # #         If(cnt_done,
        # #             If(load_cnt,
        # #                 cnt.eq(t_cycle - 1)
        # #             )
        # #         ).Else(
        # #             cnt.eq(cnt - 1)
        # #         ),
        # #     ).Else(
        # #         start_cnt.eq(start_cnt - 1)
        # #     ) 
        # # ]
        # # self.comb += self.spi.spi_start.eq(((cnt == 1) | (cnt_done)) & start_done), load_cnt.eq(self.spi.spi_start)
        
        self.comb += cnt_done.eq(cnt == 0), start_done.eq(start_cnt == 0)
        self.sync += [
            If(cnt_done,
                If(load_cnt,
                    cnt.eq(t_cycle - 1)
                )
            ).Else(
                cnt.eq(cnt - 1)
            ),
            If(~start_done,
                start_cnt.eq(start_cnt - 1)
            )
        ]
        self.comb += self.spi.spi_start.eq(cnt_done & start_done), load_cnt.eq(self.spi.spi_start)

    def test(self):
        dut = self.spi

        # yield dut.spi_start.eq(1)
        yield dut.dataSPI.eq(0xF009)
        for i in range(start_delay + 3):
            yield
        yield dut.dataSPI.eq(0xA79)
        # yield dut.spi_start.eq(0)

        while not (yield dut.spi_ready):
            yield
        for i in range(200):
           yield
        # while not (yield dut.spi_ready):
        #     yield
        yield
        # yield self.input1.eq(0x9)
        # yield self.input2.eq(0xA)
        # yield
        # yield
        # yield self.input1.eq(AD53XX_CMD_OFFSET | AD53XX_SPECIAL_OFS0 | 0x2000) #(0x822000)
        # yield self.begin.eq(1)
        # data = 0xEACB000000008FF1
        # yield self.input2.eq(data)      # data to assign for the next SPI iteration - it's gonna be latched in SPI module when it's ready

        # yield from self.busy(data)
        
        # for i in range(self.spi_p.channels):
        #     yield self.input2.eq(data + i + 1)      # data to assign for the next SPI iteration - it's gonna be latched in SPI module when it's ready
        #     yield from self.busy(data)
        #     if i == 2:
        #         yield self.begin.eq(0)

        # while not (yield self.done):
        #    yield

        # for i in range(60):
        #     yield
   

    def busy(self, data):
        dut = self.spi

        clk_cycles = 0
        while (yield self.spi_tb.syncr):
                yield        
        
        while not (yield self.spi_tb.syncr):
            yield
            clk_cycles +=1

        assert clk_cycles -1 == self.spi_p.data_width*2*self.spi_p.clk_width - 1
        
        # max waiting time between sync rising and busy falling is 42 ns ~ 5 cycles
        for i in range (5):
            yield
        yield dut.busy.eq(0)
        for i in range(t_busy):
            yield
        yield dut.busy.eq(1)

        while not (yield dut.spi_ready):
            yield       

def main():
    spi = SPISim()
    run_simulation(spi, spi.test(), vcd_name="spi.vcd")


class SPITest(unittest.TestCase):
    def test_run(self):
        main()
    
    
if __name__ == "__main__":
    main()