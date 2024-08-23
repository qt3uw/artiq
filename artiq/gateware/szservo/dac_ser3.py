from migen import *
from collections import namedtuple

from . import spi2

DACParams = spi2.SPIParams

# value needed for DAC's initialization - it sets the DAC constant offset value to the certain level
# to achieve the widest output voltage range
INIT_VAL = 0x22000

class DAC(spi2.SPI2):
    def __init__(self, pads, params):
        super().__init__(pads, params)
        self.clock_domains.cd_sys = ClockDomain()

        t_spi_cycle = (params.data_width*2*params.clk_width + 1) + 3        # amount of clock cycles needed for proper data
        # transmission to one channel - there are 3 cycles of delay needed by IC - it allows the SYNCR pin to be high for at least 
        # 4 clock cycles - 4*8ns = 32 ns

        self.profile =[Signal(32 + 16 + 16, reset_less=True)    # 64 bit wide data delivered to dac
            for i in range(params.channels)]

        self.dac_ready = Signal()           # output signal - it lets the controller know that it's transmitted all the data
        self.dac_start = Signal()           # input signal - when driven high, the module's operation is started
        self.dac_init = Signal()            # input signal - when driven high, the module performs the DAC's integrated circuit initailization

        self.initialized = Signal()

        temp = [Signal(16) for i in range (params.channels)]
        data = [Signal(16) 
            for i in range(params.channels)]        # 16-bit-wide data to be transferred to DAC

        mode = Signal (2)           # 2-bit-wide mode signal - hardcoded to "11" - it means that what is being transferred is data
        group = Signal(3)           # hardcoded group to which data is being transferred - in this case "001" which means group 0
        channel =  Signal(3)        # channel number where the data is being trasnferred to (regular number from 0 to 7 in binary)
        address = [Signal(6) for ch in range(params.channels)]
        dataOut = [Signal(2+6+16) for i in range(params.channels)]      # data width + group width + channel width + mode width

        # signals needed to control the behaviour of data sent to DAC
        words = Signal(max = params.channels)       # all words to dac concatenated

        sr_words = Signal(params.data_width*params.channels)          # shift register for words sent to dac; it shifts its content every time data is sent do SPI
        single_word = Signal(params.data_width)                       # single word to send to dac - it's equal to 'params.data_width's' LSB        
        words_shift = Signal()                                        # when asserted in "DATA" state, words inside the shift register are shifted

        # signals used to counting clock cycles - it allows to start transmission of next word to DAC precisely when desired;
        # waiting for SPI response is not needed
        cycle_cnt = Signal(max = t_spi_cycle + 1)
        cycle_done = Signal()
        cycle_load = Signal.like(cycle_cnt)

        init_latch = Signal()       # when asserted, //self.initialized// pin is driven high and lets the controller know that DAC has been already initialized

        ###

        self.submodules.fsm_dac = fsm_dac = FSM("IDLE")

        fsm_dac.act("IDLE",
            self.dac_ready.eq(1),       # when in IDLE, device is ready to accept new data
            
            # when initialization is began, LDAC pad is driven high and a number of Kasli clock cycles required to
            # initialize the device is loaded into the counter.
            If(self.dac_init,
                pads.ldac.eq(1),
                cycle_load.eq(t_spi_cycle - 1),
                NextState("INIT"),
            
            # when starte event is issued, LDAC is driven low
            ).Elif(self.dac_start,
                pads.ldac.eq(0),
                cycle_load.eq(t_spi_cycle - 1),
                NextState("DATA")
            )
        )       

        fsm_dac.act("INIT",
            pads.ldac.eq(1),
            
            # after data has been sent do the IC, it is assumed that IC has been initialized as well
            If(cycle_done,
                NextState("IDLE"),
                init_latch.eq(1)
            )
        )

        fsm_dac.act("DATA",
            pads.ldac.eq(0),
            # if there are no words left to be transmitted and of the previous words has been finished, change state to IDLE
            If((words == 0) & cycle_done,
                NextState("IDLE"),
            # otherwise, shift words inside the words' shift register
            ).Elif(cycle_done,
                words_shift.eq(1),
                cycle_load.eq(t_spi_cycle - 1)
            )
        )

        self.sync += [
            # counting the number of clock cycles left to end transmission of one word - DAC's one channel will be programmed
            If(cycle_done,
                If(cycle_load,
                    cycle_cnt.eq(cycle_load)
                )
            ).Else(
                cycle_cnt.eq(cycle_cnt - 1)
            ),
            # assignig to self.initialized value for good after initialization is finished
            If(init_latch,
                self.initialized.eq(1)
            ),
            # always when new value is loaded into the cycle counter, start spi submodule
            If(cycle_load,
                self.spi_start.eq(1)
            ).Else(
                self.spi_start.eq(0)
            ),
            # during IDLE state, always keep number of words that are needed to be sent and keep values of input data ports
            If(fsm_dac.ongoing("IDLE"),
                words.eq(params.channels - 1),
                sr_words.eq(Cat([dataOut[ch] for ch in range(params.channels)])),
            ),
            # when words_shift is asserted, shift words inside words' shift register by the width of one channel's data
            If(fsm_dac.ongoing("DATA"),
                If(words_shift,
                    words.eq(words - 1),
                    sr_words.eq(Cat(sr_words[params.data_width:], Replicate(0, params.data_width))),
                )
            )
        ]

        self.comb += [
            # SPI module is always supplied with the data from the //single_word//
            self.dataSPI.eq(single_word),

            # value assigned to single_word is muxed in accordance to the self.initialized pin's state
            single_word.eq(Mux(self.initialized, sr_words[:params.data_width], INIT_VAL)),
            cycle_done.eq(cycle_cnt == 0)
        ]

        self.comb += mode.eq(3), group.eq(1)        # group and mode are hard-coded - only first group may be used and only data registers may be updated
        
        # concatanation of latched data + group + channel + mode;
        # adding to 0x8000 to the received values, shifts them by the half of the signal width's 
        # and converts the data from the two's comlement to the binary representation
        for ch in range (params.channels):
            self.comb += [
                address[ch][:3].eq(ch), address[ch][3:].eq(group),
                temp[ch].eq((self.profile[ch][48:]) + 0x8000),        
                data[ch].eq((temp[ch])),
                dataOut[ch].eq(Cat(data[ch], address[ch], mode))            
                ]