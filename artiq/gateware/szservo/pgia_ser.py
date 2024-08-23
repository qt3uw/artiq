from migen import *
from collections import namedtuple

from artiq.gateware.szservo.spi2 import SPIParams

PGIAParams = namedtuple("PGIAParams", [
    "data_width",   # width of one portion of data to be transferred
    "clk_width",    # clock half cycle width
])

class PGIA(Module):
    def __init__(self, pads, params, gain_vector):
        # self.clock_domains.cd_sys = ClockDomain()


        # gain_vector - to set PGIA registers appropriately:
        # 00 - gain of 1 (with Sammpler +/- 10V)
        # 01 - gain of 10 (with Sampler +/- 1V)
        # 10 - gain of 100
        # 11 - gain of 1000
        # gain_vector is a 16 bit long vector of 8 concatenated gains
        
        self.start = Signal()
        self.ready = Signal()
        
        # needed to show to servo module that initialization has ended
        # it's needed because of lack of latches in Migen
        self.initialized = Signal() 
        
        data = Signal(params.data_width)

        # counter to output clock and data synchronously via SPI to shift register - 
        # it demands at least more or less 2 times slower clock than available on Kasli board
        clk_counter = Signal(max = params.clk_width)
        clk_cnt_done = Signal()
        cnt_load = Signal()

        data_load = Signal()
        sr_data = Signal.like(data)
        bits_left = Signal(max=params.data_width+1)

        ###
        
        assert params.clk_width >= 1
        
        self.comb += data.eq(gain_vector)
        self.comb += clk_cnt_done.eq(clk_counter == 0)
        self.sync += [
            If(clk_cnt_done,
                If(cnt_load,
                    clk_counter.eq(params.clk_width - 1)
                )
            ).Else(
                clk_counter.eq(clk_counter - 1)
            )
        ]

        self.submodules.fsm = fsm = CEInserter()(FSM("IDLE"))
        self.comb += fsm.ce.eq(clk_cnt_done)

        # self.comb += pads.sdi.eq(sr_data[0])        # LSB first
        self.comb += pads.sdi.eq(sr_data[-1])        # MSB first


        fsm.act("IDLE",
            self.ready.eq(1),
            If(self.start,
                cnt_load.eq(1),
                data_load.eq(1),
                NextState("SETUP")
            )
        )

        fsm.act("SETUP",
            If(bits_left == 0,
                cnt_load.eq(1),
                NextState("RCLK")       # to provide one RCLK cyles more to shift all the necessary data
            ).Else(
                cnt_load.eq(1),
                NextState("HOLD")
            )
        )

        fsm.act("HOLD",
            pads.srclk.eq(1),
            pads.rclk.eq(1),
            cnt_load.eq(1),
            NextState("SETUP")
        )

        fsm.act("RCLK",
            pads.rclk.eq(1),
            pads.srclk.eq(1),
            NextState("END")
        )

        # PGIA is needed only once during servo operation - to initalize the PGIA registers with 
        # given values, it is therefore allowed to not being able to use this module again
        fsm.act("END",
            # pads.rclk.eq(1),
            self.initialized.eq(1)
        )

        self.sync += [
            If(fsm.ce,
                If(fsm.ongoing("IDLE"),
                    bits_left.eq(params.data_width)
                ),
                If(fsm.before_leaving("HOLD"),
                    bits_left.eq(bits_left - 1),
                    # sr_data.eq(Cat(sr_data[1:], 0)),     #LSB
                    sr_data.eq(Cat(0, sr_data[:-1]))        #MSB

                ),
                If(data_load,
                    sr_data.eq(data)
                )
            )
        ]




