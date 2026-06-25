"""
KJH Conference Gooseneck Microphone Controller
"""

from lib.event_manager import EventManager
from lib.network_manager import MulticastGroup
from lib.scheduler import Scheduler
from lib.utility import CommonLogger, handle_exception

# class MessageHandler(Protocol):
#     def __call__(self, msg: str) -> None: ...


# class IoStateHandler(Protocol):
#     def __call__(self, *, device_index: int, ch_index: int, value: bool) -> None: ...


# class InputTriggerHandler(Protocol):
#     def __call__(self, *, device_index: int, ch_index: int) -> None: ...


# TIoStateHandler = TypeVar("TIoStateHandler", bound=IoStateHandler)
# TInputTriggerHandler = TypeVar("TInputTriggerHandler", bound=InputTriggerHandler)


class KjhIoController(CommonLogger, EventManager):
    DEFAULT_GROUP = "239.224.0.1"
    DEFAULT_PORT = 9000
    MCAST_TTL = 4
    NUM_IO = 16

    def __init__(self, device_index_list=None, group=DEFAULT_GROUP, port=DEFAULT_PORT):
        super().__init__("a", "b", "c", "d", "e", "in", "out", "in_trigger")
        if device_index_list is None:
            device_index_list = [1]
        self.device_index_list = device_index_list
        self.dv = MulticastGroup(group, port, ttl=self.MCAST_TTL)
        self.state_in = {device_index: [False] * self.NUM_IO for device_index in self.device_index_list}
        self.state_out = {device_index: [False] * self.NUM_IO for device_index in self.device_index_list}
        self.poll = Scheduler()
        self.mode = ""

    def init(self):
        self.dv.receive.listen(self.handle_receive)
        self.dv.on("connected", self.query_all_out)
        self.dv.connect()

    def query_all_out(self):
        self.log_info("query_all_out")
        for idx, device_index in enumerate(self.device_index_list):
            self.poll.set_timeout(1.0 + idx, lambda device_index=device_index: self.cmd_get_all_out(device_index))

    def mode_set_toggle(self):
        self.send("settriggermode,toggle")

    def mode_set_trigger(self):
        self.send("settriggermode,trigger")

    def query_all_in(self):
        for idx, device_index in enumerate(self.device_index_list):
            self.poll.set_timeout(1.2 + idx, lambda device_index=device_index: self.cmd_get_all_in(device_index))

    # ---------------------------------------------------------------------------- #
    # INFO : TX
    def send(self, cmd):
        self.dv.send(f"{cmd}\r\n".encode("ascii"))

    # ---------------------------------------------------------------------------- #
    # INFO : RX
    @handle_exception
    def handle_receive(self, evt):
        data = evt.arguments["data"]
        msg = data.decode("ascii", errors="ignore").strip()
        if not msg:
            return
        if "help" in msg:
            pass

        if msg.lower().startswith("trigger mode"):
            _, _, mode_raw = msg.partition(":")
            mode = mode_raw.strip().lower()
            print(mode)
            if mode in ("trigger", "toggle"):
                self.mode = mode
                if self.mode == "toggle":
                    self.poll.set_timeout(1.0, self.query_all_in)

        # self.log_debug(f"handle_receive(evt))
        # self.emit("received", msg)

        # Dispatch only comma-delimited IO status messages.
        if "," in msg:
            self.dispatch_msg(msg)

    @handle_exception
    def dispatch_msg(self, msg):
        # self.log_debug(f"dispatch_msg() {msg=}")
        device_index = int(msg.split(",")[1])
        if device_index not in self.device_index_list:
            return
        if len(msg) > 16:
            if msg.startswith("in,"):
                parts = msg.split(",")
                if len(parts) == 3:
                    if self.mode == "toggle":
                        for idx, value in enumerate(parts[2]):
                            if value == "1":
                                self.state_in[device_index][idx] = False
                                self.emit("in", device_index=device_index, ch_index=idx + 1, value=False)
                            if value == "0":
                                self.state_in[device_index][idx] = True
                                self.emit("in", device_index=device_index, ch_index=idx + 1, value=True)
            elif msg.startswith("out,"):
                parts = msg.split(",")
                if len(parts) == 3:
                    print(f"get_all_out {parts[0]=} {parts[1]=} {parts[2]=}")
                    for idx, value in enumerate(parts[2]):
                        if value == "1":
                            self.state_out[device_index][idx] = True
                            self.emit("out", device_index=device_index, ch_index=idx + 1, value=True)
                        if value == "0":
                            self.state_out[device_index][idx] = False
                            self.emit("out", device_index=device_index, ch_index=idx + 1, value=False)
        else:
            if msg.startswith("in,") or msg.startswith("input_ch,"):
                parts = msg.split(",")
                if len(parts) == 4:
                    idx = int(parts[2]) - 1
                    value = parts[3]
                    if self.mode == "toggle":
                        if value == "0":
                            self.state_in[device_index][idx] = True
                            self.emit("in", device_index=device_index, ch_index=idx + 1, value=True)
                        elif value == "1":
                            self.state_in[device_index][idx] = False
                            self.emit("in", device_index=device_index, ch_index=idx + 1, value=False)
                    elif self.mode == "trigger" or self.mode == "":
                        self.emit("in_trigger", device_index=device_index, ch_index=idx + 1)

            if msg.startswith("out,") or msg.startswith("output_ch,"):
                parts = msg.split(",")
                if len(parts) == 4:
                    print(f"get_out {parts[0]=} {parts[1]=} {parts[2]=} {parts[3]=}")
                    idx = int(parts[2]) - 1
                    value = parts[3]
                    if value == "1":
                        self.state_out[device_index][idx] = True
                        self.emit("out", device_index=device_index, ch_index=idx + 1, value=True)
                    elif value == "0":
                        self.state_out[device_index][idx] = False
                        self.emit("out", device_index=device_index, ch_index=idx + 1, value=False)

    # ---------------------------------------------------------------------------- #
    def get_event_handler_help(self):
        return {
            "e": "handler(msg)",
            "in": "handler(*, device_index, ch_index, value)",
            "out": "handler(*, device_index, ch_index, value)",
            "in_trigger": "handler(*, device_index, ch_index)",
        }

    # def on_message(self, handler: MessageHandler):
    #     """Register raw message handler: handler(msg)."""
    #     self.on("e", handler)

    # def on_in(self, handler: IoStateHandler):
    #     """Register input-state handler: handler(*, device_index, ch_index, value)."""
    #     self.on("in", handler)

    # def on_out(self, handler: IoStateHandler):
    #     """Register output-state handler: handler(*, device_index, ch_index, value)."""
    #     self.on("out", handler)

    # def on_in_trigger(self, handler: InputTriggerHandler):
    #     """Register trigger input handler: handler(*, device_index, ch_index)."""
    #     self.on("in_trigger", handler)

    def cmd_get_all_in(self, device_index):
        self.send(f"getins,{device_index}")

    def cmd_get_all_out(self, device_index):
        self.send(f"getouts,{device_index}")

    def cmd_get_in(self, device_index, index_ch: int):
        self.send(f"getin,{device_index},{index_ch}")

    def cmd_get_out(self, device_index, index_ch: int):
        self.send(f"getout,{device_index},{index_ch}")

    def cmd_set_out(self, device_index, index_ch: int, state: bool):
        self.send(f"set,{device_index},{index_ch},{1 if state else 0}")

    def cmd_toggle_out(self, device_index, index_ch: int):
        current_state = self.get_out(device_index, index_ch)
        self.cmd_set_out(device_index, index_ch, not current_state)

    # ---------------------------------------------------------------------------- #
    def cmd_get_ip(self):
        self.send("getip")

    # ---------------------------------------------------------------------------- #
    @handle_exception
    def get_out(self, device_index, index_ch: int):
        return self.state_out[device_index][index_ch - 1]

    @handle_exception
    def get_in(self, device_index, index_ch: int):
        return self.state_in[device_index][index_ch - 1]
