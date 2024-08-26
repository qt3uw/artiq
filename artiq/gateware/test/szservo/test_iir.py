import logging
import unittest

from migen import *
from artiq.gateware.szservo import iir
from artiq.gateware.szservo.servo import coeff_to_mu


def main():
    w = iir.IIRWidths(state=25, coeff=18, adc=16,
            asf=14, word=16, accu=48, shift=11,
            channel=1, profile=1)
    # w = iir.IIRWidths(state=17, coeff=16, adc=16,
    #         asf=14, word=16, accu=48, shift=11,
    #         channel=2, profile=1, dly=8)

    def run2(dut):
        yield dut.m_coeff[0].eq(0x1BAB)
        yield dut.m_coeff[5].eq(0xAA09)
        yield dut.m_coeff[7].eq(0x00CF)
        yield dut.m_coeff[1].eq(0xEFDC)
        yield dut.m_coeff[1].eq(0xA00A)
        yield dut.m_coeff[2].eq(0x0980)

        for i in range(1 << w.channel):
            yield from dut.set_state(i, i << 8, coeff="x1")
            yield from dut.set_state(i, i << 8, coeff="x0")
            for j in range(1 << w.profile):
                yield from dut.set_state(i,
                        (j << 1) | (i << 8), profile=j, coeff="y1")

        for i in range(100):
            yield

    # def run(dut):
    #     for i, ch in enumerate(dut.adc):
    #         yield ch.eq(i)
    #     for i, ch in enumerate(dut.ctrl):
    #         yield ch.en_iir.eq(1)
    #         yield ch.en_out.eq(1)
    #         yield ch.profile.eq(i)
    #     for i in range(1 << w.channel):
    #         yield from dut.set_state(i, i << 8, coeff="x1")
    #         yield from dut.set_state(i, i << 8, coeff="x0")
    #         for j in range(1 << w.profile):
    #             yield from dut.set_state(i,
    #                     (j << 1) | (i << 8), profile=j, coeff="y1")
    #             for k, l in enumerate("pow offset ftw0 ftw1".split()):
    #                 yield from dut.set_coeff(i, profile=j, coeff=l,
    #                         value=(i << 12) | (j << 8) | (k << 4))
    #     yield
    #     for i in range(1 << w.channel):
    #         for j in range(1 << w.profile):
    #             for k, l in enumerate("cfg a1 b0 b1".split()):
    #                 yield from dut.set_coeff(i, profile=j, coeff=l,
    #                         value=(i << 12) | (j << 8) | (k << 4))
    #             yield from dut.set_coeff(i, profile=j, coeff="cfg",
    #                     value=(i << 0) | (j << 8))  # sel, dly
    #     yield
    #     for i in range(10):
    #         yield from dut.check_iter()
    #         yield


    channel = 0
    profile = 0
    adc = 1

    length = 8
    addrs = Array(Signal(max = 4 << w.profile + w.channel) for i in range(length))
    values = Array(Signal(w.coeff) for i in range(length))
    words = Array(Signal() for i in range(length))
    masks = Array(Signal(w.coeff) for i in range (length))

    dut = iir.IIR(w, addrs, values, words, masks)

    a1, b0, b1 = coeff_to_mu(Kp = 1, Ki = 0)

    coeff = dict(pow=0xFACD, offset=0x1234, ftw0=0x1727, ftw1=0x1929,
        a1=a1, b0=b0, b1=b1, cfg=1 | (0 << 3))


    for i,k in enumerate("ftw1 pow offset ftw0 b1 cfg a1 b0".split()):
        word, addr, mask = dut._coeff(channel, profile, coeff = k)
        dut.comb += addrs[i].eq(addr), words[i].eq(word), masks[i].eq(mask), values[i].eq(coeff[k])
        print(k, word, addr, mask, coeff[k])
    
    # dut.comb += [
    #     addrs[0].eq(0),      # ftw1
    #     addrs[1].eq(0),      # b1
    #     addrs[2].eq(5),      # pow
    #     addrs[3].eq(5),      # cfg
    #     addrs[4].eq(7),      # offset
    #     addrs[5].eq(7),      # a1
    #     addrs[6].eq(1),      # ftw0
    #     addrs[7].eq(1),      # b0

    #     values[0].eq(0x5A),
    #     values[1].eq(10),
    #     values[2].eq(0xF),
    #     values[3].eq(0xAB),
    #     values[4].eq(5),
    #     values[5].eq(10),
    #     values[6].eq(0xF),
    #     values[7].eq(0xAB),

    #     words[0].eq(0),
    #     words[1].eq(1),
    #     words[2].eq(0),
    #     words[3].eq(1),
    #     words[4].eq(0),
    #     words[5].eq(1),
    #     words[6].eq(0),
    #     words[7].eq(1),
    
    # ]


    # for i in range(length):
    #     dut.comb += masks[i].eq(0xFF)

    # dut.sync +=[
    #     If(~dut.loading,
    #         dut.adc[channel].eq(adc)                     # assinging adc number to iir and in result to dac channel
    #     ),
    #     dut.ctrl[channel].en_iir.eq(1),
    #     dut.ctrl[channel].en_out.eq(1),
    #     dut.ctrl[channel].profile.eq(profile),
    #     dut. start.eq(dut.done_writing)
    # ]


    dut.comb += dut.start_coeff.eq(~dut.done_writing),

    run_simulation(dut, [run2(dut)], vcd_name="iir_mod.vcd")


class IIRTest(unittest.TestCase):
    def test_run(self):
        main()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    main()
