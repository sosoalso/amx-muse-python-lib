from lib.eventmanager import EventManager
from lib.utility import handle_exception


class TascamCdp(EventManager):
    def __init__(self, dv):
        super().__init__()
        self.dv = dv
        self.debug = False

    def log_debug(self, message):
        if self.debug:
            print(f"{self.__class__.__name__} DEBUG -- {message}")


tascam_cdp_01 = TascamCdp(dv_cdp)
