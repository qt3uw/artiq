from migen import *

from artiq.gateware.szservo.adc_ser import ADC, ADCParams
from artiq.gateware.szservo.dac_ser3 import DAC, DACParams
from artiq.gateware.szservo.iir import IIR, IIRWidths
from artiq.gateware.szservo.pgia_ser import PGIA, PGIAParams
from artiq.language.units import us, ns


# coefficients width and normalization factors
COEFF_SHIFT = 11                # the number of bits that the calculated by IIR output has to be shifted
B_NORM = 1 << COEFF_SHIFT + 1   # the input values' coefficient normalization factor
A_NORM = 1 << COEFF_SHIFT       # the filter's a0 value
COEFF_width = 18                # each coefficient's width
COEFF_MAX = 1 << COEFF_width - 1    # coefficient's maximum value before the filter's registers overflow due to the calcualtions

# delay needed before the Servo starts its operation - it allows the FPGA setting its signals' initial values
start_delay = 100


class Servo(Module):
    def __init__(self, adc_pads, pgia_pads, dac_pads, adc_p, pgia_p, iir_p, dac_p, pgia_init_val, Kps, Kis):
        self.clock_domains.cd_sys = ClockDomain()
        
        # the arrays of signals needed for writing the controller's coefficients into the FPGA's memory
        length = adc_p.channels*8
        addrs = Array(Signal(max = 4 << iir_p.profile + iir_p.channel) for i in range(length))
        values = Array(Signal(iir_p.coeff) for i in range(length))
        words = Array(Signal() for i in range(length))
        masks = Array(Signal(iir_p.coeff) for i in range (length))
            
        
        self.submodules.adc = ADC(adc_pads, adc_p)
        self.submodules.iir = IIR(iir_p, addrs, values, words, masks)
        self.submodules.dac = DAC(dac_pads, dac_p)

        self.submodules.pgia = PGIA(pgia_pads, pgia_p, pgia_init_val)

        # assigning paths and signals - adc data to iir.adc and iir.dac to dac.profie
        # adc channels are reversed on Sampler
        for i, j, k, l in zip(reversed(self.adc.data), self.iir.adc,
                self.iir.dds, self.dac.profile):
            self.comb += j.eq(i), l.eq(k)


        # calculating each submodule's operation time needed for defining the sampling period and restarting
        # Sampler's transmission
        t_adc = (adc_p.t_cnvh + adc_p.t_conv + adc_p.t_rtt +
            adc_p.channels*adc_p.width//adc_p.lanes) + 1
        t_iir = ((1 + 4 + 1) << iir_p.channel) + 1
        t_dac_1ch = (dac_p.data_width*2*dac_p.clk_width + 3 + 1)
        
        # 8ns - 1 clock cycle, DAC needs about 34.5 us to settle, hence 34.5us/8ns = number of cycles
        t_dac = t_dac_1ch * dac_p.channels + 1 
        t_update = 4256

        self.t_cycle = t_cycle = max(t_adc, t_iir, t_dac, 4256)
        T_CYCLE = self.t_cycle*8*ns  # Must match gateware Servo.t_cycle.

        self.start = Signal()
        self.done = Signal()

        t_restart = t_cycle - (t_adc + t_iir + t_dac_1ch) + 1
        cnt = Signal(max = t_restart)
        cnt_done = Signal()
        active = Signal(3)
        
        self.sync += [
            If(self.dac.dac_ready,
                active[2].eq(0)
            ),
            If(self.dac.dac_start & self.dac.dac_ready,
                active[2].eq(1),
                active[1].eq(0)
            ),
            If(self.iir.start & self.iir.done, 
                active[1].eq(1),
                active[0].eq(0)
            ),
            If(~cnt_done & self.adc.done,
                cnt.eq(cnt - 1)
            ),
            If(self.adc.start & self.adc.done,
                active[0].eq(1),
                cnt.eq(t_restart - 1)
            )
        ]
        
        # counting clock cycles to delay the begining of the module's operation
        assert start_delay <= 100
        start_cnt = Signal(max=start_delay + 1, reset = start_delay)
        start_done = Signal()

        self.comb += [
             start_done.eq(start_cnt == 0)
        ]

        self.sync += [
            If(~start_done,
                start_cnt.eq(start_cnt - 1)
            ) 
        ]


        self.comb += [
            cnt_done.eq(cnt == 0),
            self.dac.dac_init.eq(self.start & ~self.dac.initialized & start_done),
            self.pgia.start.eq(self.start & ~self.pgia.initialized & start_done),
            self.iir.start_coeff.eq(self.start & ~self.iir.done_writing & start_done),
            
            self.adc.start.eq(self.start & cnt_done & self.pgia.initialized & self.dac.initialized & self.iir.done_writing),
            self.iir.start.eq(active[0] & self.adc.done),
            self.dac.dac_start.eq(active[1] & (self.iir.shifting | self.iir.done)),
            
            self.done.eq(self.dac.dac_ready)
        ]

        # list of coefficients for each controller's channel
        coeff_list = [[] for j in range(len(Kps))]

        assert len(coeff_list) == adc_p.channels

        # conversion of coefficients
        for idx, (i, j) in enumerate(zip (Kps, Kis)):
            coeff_list[idx] = coeff_to_mu(Kp = i, Ki = j, T_CYCLE = T_CYCLE)

        profile = 0

        # creating lists of coefficients and their placements in the IIR's memory that are passed to the IIR
        # constructor.
        for ix in range(adc_p.channels):
            ch = ix
            adc = ix
            a1, b0, b1 = coeff_list[ix]
            coeff = dict(pow=0x0000, offset=0x0000, ftw0=0x1727, ftw1=0x1929,
                a1=a1, b0=b0, b1=b1, cfg = adc | (0 << 3))

            for i,k in enumerate("ftw1 pow offset ftw0 b1 cfg a1 b0".split()):
                word, addr, mask = self.iir._coeff(ch, profile, coeff = k)
                self.comb += addrs[i + ix*8].eq(addr), words[i + ix*8].eq(word), masks[i + ix*8].eq(mask), values[i + ix*8].eq(coeff[k])

            self.comb += [
                If(~self.iir.loading,
                    self.iir.adc[ch].eq(adc)                     # assinging adc number to iir and in result to dac channel
                ),
            ]
            # enabling IIR's output for every channel
            self.sync +=[
                self.iir.ctrl[ch].en_iir.eq(1),
                self.iir.ctrl[ch].en_out.eq(1),
                self.iir.ctrl[ch].profile.eq(profile),
            ]


# function that converts the coefficients from the continuous-frequency domain to the 
# discrete Z domain; T_CYCLE is the controller's sampling period that needs to match the 
# calculated t_cycle in the Servo module.
def coeff_to_mu(Kp, Ki, T_CYCLE):
    Kp *=B_NORM
    if Ki == 0:
        # pure P
        a1 = 0
        b1 = 0
        b0 = int(round(Kp))
    else:
        # I or PI
        Ki *= B_NORM*T_CYCLE/2.
        c = 1.
        a1 = A_NORM
        b0 = int(round(2.*Kp + Ki*c))
        b1 = int(round(Ki - 2.*Kp))
        if b1 == -b0:
            raise ValueError("low integrator gain and")

    if (b0 >= COEFF_MAX or b0 < -COEFF_MAX or
            b1 >= COEFF_MAX or b1 < -COEFF_MAX):
        raise ValueError("high gains")
    
    return [a1, b0, b1]