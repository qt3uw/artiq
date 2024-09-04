from artiq.language.core import *
from artiq.language.types import *
from artiq.coredevice.rtio import rtio_output

class LinkedLED:

    def __init__(self, dmgr, channel, core_device="core"):
        self.core = dmgr.get(core_device)
        self.channel = channel
        self.target_o = channel << 8

    @staticmethod
    def get_rtio_channels(channel, **kwargs):
        return [(channel, None)]

    @kernel
    def set_o(self, o):
        rtio_output(self.target_o, o)