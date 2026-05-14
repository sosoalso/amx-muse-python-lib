from lib.eventmanager import EventManager
from lib.scheduler import Scheduler
from lib.utility import CommonLogger


# todo 기능 더 추가해야 됨
class EikiVidprj(CommonLogger, EventManager):
    def __init__(self, dv):
        super().__init__("power", "poweron", "poweroff", "mute", "muted", "unmuted", "poll")
        self.dv = dv
        self.power = False
        self.mute = False
        self.poll = Scheduler(name=self.__class__.__name__ + " poll")
        # ---------------------------------------------------------------------------- #
        self.last_send_command = ""
        self.init()

    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.dv.connect()
        self.start_poll()

    def send(self, msg):
        if self.dv.connected:
            self.last_send_command = msg
            self.dv.send(msg + "\r")

    def start_poll(self, *args):
        def query_power():
            self.send("CR0")

        self.poll.set_interval(10.0, query_power)

    def parse_response(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"Received response is in an invalid format. {args=}")
        else:
            try:
                data_text = args[0].arguments["data"].decode("utf-8")
                response = data_text.splitlines()[0]
                self.log_debug(f"parse_response() {response=}")
                if "CR0" == self.last_send_command:
                    self.log_debug(f"parse_response() {self.last_send_command=} power? {response=}")
                    if "00" == response:
                        self.power = True
                    elif "80" == response:
                        self.power = False
                    else:
                        return
                    self.trigger_event("power", value=self.power)
                self.last_send_command = ""
            except (AttributeError, KeyError, UnicodeDecodeError) as e:
                self.log_error(f"Error decoding data {e=}")

    def set_power(self, value):
        self.send("C00" if value else "C01")
        self.power = value
        self.trigger_event("power", value=self.power)
        self.mute = False
        self.trigger_event("mute", value=self.mute)

    def power_on(self):
        self.set_power(True)

    def power_off(self):
        self.set_power(False)

    # blank 임 eiki 명령어집에서는
    def set_mute(self, value):
        self.send("C0D" if value else "C0E")
        self.mute = value
        self.trigger_event("mute", value=self.mute)

    def mute_on(self):
        self.set_mute(True)

    def mute_off(self):
        self.set_mute(False)
