import threading

import PyATEMMax
from lib.eventmanager import EventManager
from mojo import context


class AtemHandler(EventManager):
    def __init__(self, ip):
        super().__init__(
            "connected", "disconnected", "pgm_switched", "pvw_switched", "switch_pgm", "switch_pvw", "cut", "auto"
        )
        self.ip = ip
        self._thread_switcher = None
        self.init()

    # ---------------------------------------------------------------------------- #
    def init(self):
        self._thread_switcher = threading.Thread(target=self._handle_thread_switcher, daemon=True)
        self._thread_switcher.start()

    def _handle_thread_switcher(self):
        switcher = PyATEMMax.ATEMMax()

        def on_received(params):
            context.log.info(f"on_received {params}")
            if params["cmd"] == "PrgI":
                input_idx =  switcher.programInput[0].videoSource.value
                self.trigger_event( "pgm_switched", input_idx)
            elif params["cmd"] == "PrvI":
                input_idx = switcher.previewInput[0].videoSource.value
                self.trigger_event("pvw_switched",input_idx)

        # ---------------------------------------------------------------------------- #
        # switcher.registerEvent(switcher.atem.events.connectAttempt, on_connect_attempt)
        # switcher.registerEvent(switcher.atem.events.connect, on_connected)
        # switcher.registerEvent(switcher.atem.events.disconnect, on_disconnected)
        # switcher.registerEvent(switcher.atem.events.warning, on_warning)
        switcher.registerEvent(switcher.atem.events.receive, on_received)

        # ---------------------------------------------------------------------------- #
        def on_switch_pgm(input_idx):
            context.log.info(f"on_switch_pgm {input_idx}")
            switcher.setProgramInputVideoSource(0, input_idx)

        def on_switch_pvw(input_idx):
            context.log.info(f"on_switch_pvw {input_idx}")
            switcher.setPreviewInputVideoSource(0, input_idx)

        def on_switch_cut():
            switcher.execCutME(0)

        def on_switch_auto():
            switcher.execAutoME(0)

        self.add_event_handler("switch_pgm", on_switch_pgm)
        self.add_event_handler("switch_pvw", on_switch_pvw)
        self.add_event_handler("cut", on_switch_cut)
        self.add_event_handler("auto", on_switch_auto)

        # ---------------------------------------------------------------------------- #
        switcher.connect(self.ip)
        # ---------------------------------------------------------------------------- #


switcher = AtemHandler("10.20.0.88")


switcher.trigger_event("switch_pgm", 3)
switcher.trigger_event("switch_pvw"4)
switcher.trigger_event("cut")
switcher.trigger_event("auto")
