from mojo import context

from lib.eventmanager import EventManager


class HyperDeck(EventManager):
    def __init__(self, dv):
        super().__init__("transport")
        self.dv = dv
        self.transport = 0
        self.init()

    def init(self):
        self.dv.receive.listen(self.parse_response)

    def send(self, cmd):
        self.dv.send(f"{cmd}\r\n")

    def record(self):
        self.send("record")
        self.transport = "record"
        self.trigger_event("transport", transport=self.transport, this=self)

    def vidrec_stop(self):
        self.send("stop")
        self.transport = "stopped"
        self.trigger_event("transport", transport=self.transport, this=self)

    def play(self):
        self.send("play")
        self.transport = "play"
        self.trigger_event("transport", transport=self.transport, this=self)

    def track_prev(self):
        self.send("goto: clip id: -1")

    def track_next(self):
        self.send("goto: clip id: +1")

    def track_start(self):
        self.send("goto: clip: start")

    def track_end(self):
        self.send("goto: clip: end")

    def parse_response(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            return
        else:
            try:
                data_text = args[0].arguments["data"].decode("utf-8")
                while "\r\n" in data_text:
                    response = data_text.split("\r\n", 1)
                    if "status: " in response:
                        if "record" in response[7:]:
                            self.transport = "record"
                        elif "stopped" in response[7:]:
                            self.transport = "stopped"
                        elif "preview" in response[7:]:
                            self.transport = "preview"
                        elif "play" in response[7:]:
                            self.transport = "play"
                        else:
                            pass  # Add appropriate handling here if needed
            except (AttributeError, KeyError, UnicodeDecodeError) as e:
                context.log.debug(f"Error decoding data: {e}")
            self.trigger_event("transport", transport=self.transport, this=self)


# vidrec_instance = Vidrec(VIDREC)
# # ---------------------------------------------------------------------------- #
# # SECTION : TP
# # ---------------------------------------------------------------------------- #
# TP_PORT_VIDREC = 7


# def refresh_vidrec_button():
#     tp_set_button_ss(TP_LIST, TP_PORT_VIDREC, 101, vidrec_instance.transport == "record")
#     tp_set_button_ss(TP_LIST, TP_PORT_VIDREC, 102, vidrec_instance.transport == "stopped")
#     tp_set_button_ss(TP_LIST, TP_PORT_VIDREC, 103, vidrec_instance.transport == "play")


# def add_tp_vidrec():
#     record_button = ButtonHandler()
#     play_button = ButtonHandler()
#     stop_button = ButtonHandler()
#     record_button.add_event_handler("push", vidrec_instance.record)
#     play_button.add_event_handler("push", vidrec_instance.play)
#     stop_button.add_event_handler("push", vidrec_instance.vidrec_stop)
#     tp_add_watcher_ss(TP_LIST, TP_PORT_VIDREC, 101, record_button.handle_event)
#     tp_add_watcher_ss(TP_LIST, TP_PORT_VIDREC, 102, stop_button.handle_event)
#     tp_add_watcher_ss(TP_LIST, TP_PORT_VIDREC, 103, play_button.handle_event)
#     context.log.debug("add_tp_vidrec 등록 완료")


# def add_evt_vidrec():
#     # NOTE : 비디오레코더 이벤트 피드백
#     vidrec_instance.add_event_handler("transport", lambda **kwargss: refresh_vidrec_button())
#     # NOTE : TP 온라인 피드백
#     for tp_online in TP_LIST:
#         tp_online.online(lambda evt: refresh_vidrec_button())
#     context.log.debug("add_evt_vidrec 등록 완료")
