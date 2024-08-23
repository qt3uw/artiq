from migen import *
from collections import namedtuple


SPIParams = namedtuple("SPIParams", [
    "channels",     # amount of channels in use
    "data_width",   # width of one portion of data to be transferred
    "clk_width",    # clock half cycle width
])

class SPI2(Module):
    def __init__(self, pads, params):
        
        self.dataSPI = Signal(params.data_width, reset_less=True)

        sr_data = Signal.like(self.dataSPI)    # shift register with input data latched in it

        self.spi_start = Signal()           # triggers outputting data on dac
        self.spi_ready = Signal()           # when it's high, module is ready to accept new data


        clk_counter = Signal(max=params.clk_width)
        clk_cnt_done = Signal()
        
        bits = Signal(max = params.data_width)
        
        cnt_load = Signal()
        cnt_done = Signal()

        data_load = Signal()

        
        ###

        assert params.clk_width >= 1

        # counter to generate clock enable signal every 2*clk_width sys_clk cycles
        self.comb += clk_cnt_done.eq(clk_counter == 0)
        self.sync += [
            If(clk_cnt_done, 
                If(cnt_load,
                    clk_counter.eq(params.clk_width - 1),
                )
            ).Else(
                clk_counter.eq(clk_counter-1)
            )
        ]
        
        self.submodules.fsm = fsm = CEInserter()(FSM("IDLE"))
        self.comb += fsm.ce.eq(clk_cnt_done)
        
        # self.comb += pads.sdi.eq(sr_data[0])       # output data - LSB first
        self.comb += pads.sdi.eq(sr_data[-1])       # output data - MSB first
        
        fsm.act("IDLE",
            self.spi_ready.eq(1),       
            pads.syncr.eq(1),
            If(self.spi_start,
                NextState("SETUP"),
                data_load.eq(1),         # signalling to latch the input data in the shift register
                cnt_load.eq(1)                
            )
        )

        fsm.act("SETUP",
            cnt_load.eq(1),
            NextState("HOLD"),
         
            pads.syncr.eq(0),           # chip select driven low
            pads.sclk.eq(1),            # gives clock signal on the output pin; when it enters SETUP state the sclk is driven high
                                        # and when it enters HOLD, sclk is driven low - that's when the DAC reads the data - on the falling edge
        )

        fsm.act("HOLD",
            pads.syncr.eq(0),
            If(bits == 0,               # if the whole word (in this case 24 bits) has been transmitted, go to IDLE
                NextState("IDLE")
            ).Else(
                cnt_load.eq(1),
                NextState("SETUP")
            )
        )

        self.sync += [
            If(fsm.ce,
                # counts down how many bits are left to be transmitted 
                # and shifts output register by one bit to the left
                If(fsm.before_leaving("HOLD"),
                
                    If(bits == 0,
                        bits.eq(params.data_width-1),
                    ).Else(
                        bits.eq(bits - 1),
                        # sr_data.eq(Cat(sr_data[1:], 0))         # LSB first
                        sr_data.eq(Cat(0, sr_data[:-1])),         # MSB first
                    )
                ),
                # word counter is needed because DAC chip requires controller to set SYNC high after
                # every sent 24 bits. That's how it knows whether is there any word/bit left to be sent.
                # Word coutner is the number of channels used by ADC and IIR
                If(fsm.ongoing("IDLE"),
                    bits.eq(params.data_width-1)
                ),
                # Shiftin data is needed for multi-word transmissions
                If(fsm.ongoing("DELAY"),
                    bits.eq(params.data_width-1),
                    
                    # sr_data.eq(Cat(sr_data[1:], 0))         # LSB first
                    sr_data.eq(Cat(0, sr_data[:-1]))         # MSB first
                ),
                If(data_load,
                    sr_data.eq(self.dataSPI), 
                )
            )
        ]