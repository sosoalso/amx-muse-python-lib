from lib.eventmanager import EventManager
from lib.scheduler import Scheduler
from lib.utility import CommonLogger


# todo 기능 더 추가해야 됨
class DigitalProjectionVidprj(CommonLogger, EventManager):
    def __init__(self, dv):
        super().__init__("power", "poweron", "poweroff", "mute", "muted", "unmuted", "poll")
        self.dv = dv
        self.power = False
        self.mute = False
        self.poll = Scheduler(name=self.__class__.__name__ + " poll")
        # ---------------------------------------------------------------------------- #
        self.last_send_command = ""
        self.dv.receive.listen(self.parse_response)
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
            self.send("*power ?")

        def query_mute():
            self.send("*mute ?")

        self.poll.set_timeout(1.0, lambda: self.poll.set_interval(10.0, query_power))
        self.poll.set_timeout(3.0, lambda: self.poll.set_interval(10.0, query_mute))

    def parse_response(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"parse_response() Received response is in an invalid format. {args=}")
        else:
            try:
                data_text = args[0].arguments["data"].decode("utf-8")
                response = data_text.strip()
                if response.startswith("ack"):
                    content = response.replace("ack", "", 1).strip()
                    key, value = content.split("=", 1)
                    key = key.strip()
                    value = value.strip()
                    if "*power" == key:
                        self.power = True if value in ["true", "1"] else False if value in ["false", "0"] else self.power
                        self.trigger_event("power", value=self.power)
                    if "*mute" == key:
                        self.mute = True if value in ["true", "1"] else False if value in ["false", "0"] else self.mute
                        self.trigger_event("mute", value=self.mute)
            except Exception as e:
                self.log_error(f"parse_response() {e=}")

    def set_power(self, value):
        self.send("*power = true" if value else "*power = false")
        self.power = value
        self.trigger_event("power", value=value)

    def power_on(self):
        self.set_power(True)

    def power_off(self):
        self.set_power(False)

    def set_mute(self, value):
        self.send("*mute = true" if value else "*mute = false")
        self.mute = value
        self.trigger_event("mute", value=value)

    def mute_on(self):
        self.set_mute(True)

    def mute_off(self):
        self.set_mute(False)
