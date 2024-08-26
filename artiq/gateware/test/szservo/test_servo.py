import logging
import unittest

from math import log2, ceil


from migen import *
from migen.genlib import io

from artiq.gateware.szservo.testing import test_adc, test_dac3, test_pgia
from artiq.gateware.szservo import servo

channels_no = 8

Kps = [1 for i in range(channels_no)]
Kis = [0 for i in range(channels_no)]


class ServoSim(servo.Servo):
    def __init__(self):
        adc_p = servo.ADCParams(width=16, channels=channels_no, lanes=int(channels_no/2),
                t_cnvh=4, t_conv=57 - 4, t_rtt=4 + 4)
        iir_p = servo.IIRWidths(state=25, coeff=18, adc=16, asf=14, word=16,
                accu=48, shift=11, channel=ceil(log2(adc_p.channels)), profile=1)
        self.dac_p = servo.DACParams(data_width = 24, clk_width = 2,
                channels=adc_p.channels)

        pgia_p = servo.PGIAParams(data_width = 16, clk_width = 2)
        self.submodules.adc_tb = test_adc.TB(adc_p)
        self.submodules.dac_tb = test_dac3.TB(self.dac_p)

        self.submodules.pgia_tb = test_pgia.TB(pgia_p)

        servo.Servo.__init__(self, self.adc_tb, self.pgia_tb, self.dac_tb,
                adc_p, pgia_p, iir_p, self.dac_p, 0x5555, Kps, Kis)
        
        # self.channel = channel = 0
        # self.adc = adc = 0
        # self.profile = profile = 0


        # # if ch_no is None:
        # self.channel = channel = 0
        # # else:
        # #     self.channel = channel = ch_no
        # self.adc = adc = 0
        # self.profile = profile = 0
        
        # self.sync +=[
        #     If(~self.iir.loading,
        #         self.iir.adc[channel].eq(adc)                     # assinging adc number to iir and in result to dac channel
        #     ),
        #     self.iir.ctrl[channel].en_iir.eq(1),
        #     self.iir.ctrl[channel].en_out.eq(1),
        #     self.iir.ctrl[channel].profile.eq(profile),
        # ]

        # a1, b0, b1 = servo.coeff_to_mu(Kp = 1, Ki = 0)
        
        # # pow - phase offset word
        # # offset - iir offset
        # # ftw - frequency tuning word
        # self.coeff = coeff = dict(pow=0x0000, offset=0x8000, ftw0=0x1727, ftw1=0x1929,
        #         a1=a1, b0=b0, b1=b1, cfg=self.adc | (0 << 3))
        
        # for ks in "pow offset ftw0 ftw1", "a1 b0 b1 cfg":
        #     for k in ks.split():
        #         self.set_coeff(self.channel, value=coeff[k],
        #                 profile=self.profile, coeff=k)
                        
    def test(self):

        
        x0 = 0x0141
        # x0 = 0x7FFF
        x1 = 0x0743
        y1 = 0x1145
        yield from self.set_states(x0, x1, y1, 0, 0, 0)

        # x2 = 0x7FFF
        # x2 = 0x0141
        x3 = 0x0743
        y3 = 0x1145
        
        # yield from self.test_iter(x0, x1, y1, self.adc, self.channel, self.profile)
        # assert (yield self.done)
        for i in range(1, self.dac_p.channels - 1):
            x0 = x0#+0x0020 + i*i*0x00A0
            x3 = 0x0743
            y3 = 0x1145

            yield from self.set_states(x0, x3, y3, i, i, 0)

        x0 = 0x7FFF
        yield from self.set_states(x0, x3, y3, self.dac_p.channels - 1, self.dac_p.channels - 1, 0)
        

        yield self.start.eq(1)
        for i in range(1000):
            yield
        # yield from self.init_seq()
       
        
        # # # # yield self.start.eq(0)
        

        # # yield from self.servo_iter()

        # # # # yield from self.check_iter(x0, x1, y1)
    

        # # # for i in range(1000):
        # # #     yield
        # # yield from self.servo_iter()

        # # # yield from self.check_iter(x0, x1, y1)


        
    
    def set_states(self, x0, x1, y1, adc, channel, profile):
        
        yield self.adc_tb.data[-adc-1].eq(x0)
        yield from self.iir.set_state(adc, x1, coeff="x1")      # assigning x1 as a previous value of input
        yield from self.iir.set_state(channel, y1,              # assigning y1 as previous value of output
                profile=profile, coeff="y1")

    def servo_iter(self):
        while not (yield self.dac.dac_start):
            yield
        yield
        while not (yield self.done):
        # for i in range(self.dac_p.channels):
            while (yield self.dac_tb.syncr):
                    yield        
            
            while not (yield self.dac_tb.syncr):
                yield

            while not (yield self.dac.dac_ready):
                yield      


        # while not (yield self.dac.start_dac):
        #         yield
        # for ch in range (self.dac_p.channels):
        #     for i in range (self.dac_p.data_width*self.dac_p.clk_width*2-1):
        #         yield
        #     yield
        #     yield self.dac.busy.eq(0)
        #     for i in range(3):
        #         yield
        #     yield self.dac.busy.eq(1)
        #     yield
        # while not (yield self.dac.ready):
        #     yield
        # yield
        # while not (yield self.done):
        #     yield
        # yield

    def init_seq(self):
        
        while (yield self.dac.dac_ready):
            yield
        
        while not (yield self.dac_tb.syncr):
            yield

        while not (yield self.dac.initialized & self.pgia.initialized):
            yield        

     
    
    def check_iter(self, x0, x1, y1):
        w = self.iir.widths

        x0 = x0 << (w.state - w.adc - 1)
        _ = yield from self.iir.get_state(self.adc, coeff="x1")
        assert _ == x0, (hex(_), hex(x0))

        offset = self.coeff["offset"] << (w.state - w.coeff - 1)
        a1, b0, b1 = self.coeff["a1"], self.coeff["b0"], self.coeff["b1"]
        out = (
                0*(1 << w.shift - 1) +  # rounding
                a1*(y1 + 0) + b0*(x0 + offset) + b1*(x1 + offset)
        ) >> w.shift
        y1 = min(max(0, out), (1 << w.state - 1) - 1)

        # _ = yield from self.iir.get_state(self.channel, self.profile, coeff="y1")
        # assert _ + 0x800000 == y1, (hex(_), hex(y1))

      
        
    def test_iter(self, x0, x1, y1, adc, channel, profile):
        
        assert (yield self.done)

        yield from self.set_states(x0, x1, y1, self.adc, self.channel, self.profile)


        yield self.start.eq(1)
        yield from self.init_seq()
        
        yield self.start.eq(0)
        yield from self.servo_iter()

        yield from self.check_iter(x0, x1, y1)        

def main():
    servo = ServoSim()
    run_simulation(servo, servo.test(), vcd_name="servo_dac3.vcd",
            clocks={
                "sys":   (8, 0),
                "adc":   (8, 0),
                "ret":   (8, 0),
                "async2": (2, 0),
            })


class ServoTest(unittest.TestCase):
    def test_run(self):
        main()


if __name__ == "__main__":
    main()
