from lib.eventmanager import EventManager
from lib.networkmanager import TcpClient
from lib.scheduler import Scheduler

# SECTION : 제어 장비


# todo 기능 더 추가해야 됨
class PJLink(EventManager):
    def __init__(self, ip_address, name="PJLink"):
        super().__init__("power", "poweron", "poweroff", "mute", "muted", "unmuted", "poll")
        self.dv = TcpClient(ip=ip_address, port=4352, name=name)
        self.name = name
        self.power = False
        self.mute = False
        self.source = "0"
        self.poll = Scheduler(name=self.name + " poll")
        self.debug = False
        self.dv.receive.listen(self.parse_response)
        self.dv.connect()
        self.start_poll()

    def log_debug(self, message):
        if self.debug:
            print(f"{self.__class__.__name__} DEBUG -- {message}")

    def log_error(self, message):
        print(f"{self.__class__.__name__} ERROR -- {message}")

    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.dv.connect()
        self.start_poll()

    def send(self, msg):
        if self.dv.connected:
            self.dv.send(msg + "\r")

    def start_poll(self, *args):
        def query_power():
            self.send("%1POWR ?")

        def query_mute():
            self.send("%1AVMT ?")

        self.poll.set_timeout(1.0, lambda: self.poll.set_interval(10.0, query_power, 10.0))
        self.poll.set_timeout(2.0, lambda: self.poll.set_interval(10.0, query_mute, 10.0))

    def parse_response(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"수신 응답은 잘못된 형식입니다. {args=}")
        else:
            try:
                data_text = args[0].arguments["data"].decode("utf-8")
                response = data_text.split("\r")[0]
                if "%1POWR=" in response:
                    res = response.partition("=")[2]
                    if res == "1":
                        self.power = True
                    elif res == "0":
                        self.power = False
                    self.trigger_event("power", value=self.power, this=self)
                elif "%1AVMT=" in response:
                    res = response.partition("=")[2]
                    if res == "31":
                        self.mute = True
                    elif res == "30":
                        self.mute = False
                    self.trigger_event("mute", value=self.mute, this=self)
            except (AttributeError, KeyError, UnicodeDecodeError) as e:
                self.log_error(f"Pjlink {self.name=} Error decoding data: {e}")

    def set_power(self, value):
        self.send("%1POWR 1" if value else "%1POWR 0")
        self.power = value
        self.trigger_event("power", value=value, this=self)

    def power_on(self):
        self.set_power(True)

    def power_off(self):
        self.set_power(False)

    def set_mute(self, value):
        self.send("%1AVMT 31" if value else "%1AVMT 30")
        self.mute = value
        self.trigger_event("mute", value=value, this=self)

    def mute_on(self):
        self.set_mute(True)

    def mute_off(self):
        self.set_mute(False)
