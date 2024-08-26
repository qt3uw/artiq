from migen import *
from artiq.gateware.szservo.pgia_ser import PGIA, PGIAParams

class TB(Module):
    def __init__(self, params):
        self.sdi = Signal()
        self.srclk = Signal()
        self.rclk = Signal()

def main():
    gain_vector = 0x5555        # 8 times "01" - sets gains of all PGIAs to 10 to measure +/- 1V input
    params = PGIAParams(data_width = 16, clk_width = 2)
    tb = TB(params)
    pgia = PGIA(tb, params, gain_vector)
    tb.submodules += pgia

    def run(tb):
        dut = pgia
        yield
        yield dut.start.eq(1)
        yield
        yield
        yield
        yield dut.start.eq(0)
        while not (yield dut.initialized):
            yield
        yield

    run_simulation(tb, run(tb), vcd_name="pgia.vcd")

if __name__ == "__main__":
    main()