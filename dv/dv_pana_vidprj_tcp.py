# 마지막 수정일 : 20260514
from lib.event_manager import EventManager
from lib.network_manager import TcpClient, DEFAULT_TCP_CLIENT_RECONNECT_TIME
from lib.scheduler import Scheduler
from lib.utility import CommonLogger, handle_exception


# SECTION : 제어 장비
# todo 기능 더 추가해야 됨
class PanaVidprjTcp(CommonLogger, EventManager):
    DEFAULT_PORT = 1024

    def __init__(self, ip, port=DEFAULT_PORT, reconnect_time=DEFAULT_TCP_CLIENT_RECONNECT_TIME):
        super().__init__("power", "poweron", "poweroff", "mute", "muted", "unmuted", "poll", "lamp_time")
        self.dv = TcpClient(ip, port, reconnect_time=reconnect_time)
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.power = False  # USERDATA.get_value(f"{self.name}_power", False)
        self.mute = False  # USERDATA.get_value(f"{self.name}_mute", False)
        self.freeze = False  # USERDATA.get_value(f"{self.name}_freeze", False)
        self.last_sent_message = ""
        self.poll = Scheduler()

    @handle_exception
    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.start_poll()

    def send(self, msg):
        self.last_sent_message = msg
        self.dv.send("00" + msg + "\r")

    @handle_exception
    def start_poll(self, *args):
        @handle_exception
        def query_power():
            self.send("QPW")

        @handle_exception
        def query_mute():
            self.send("QSH")

        self.poll.set_timeout(1.0, lambda: self.poll.set_interval(10.0, query_power))
        self.poll.set_timeout(2.0, lambda: self.poll.set_interval(10.0, query_mute))

    @handle_exception
    def parse_response(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"Received response has an invalid format. {args=}")
        else:
            try:
                data_text = args[0].arguments["data"].decode("utf-8")
                response = data_text.split("\r")[0]
                res = response.partition("=")[2]
                if res == "00001":
                    self.power = True
                    self.emit("power", value=self.power)
                elif res == "00000":
                    self.power = False
                    self.emit("power", value=self.power)
                if res == "001":
                    self.mute = True
                    self.emit("mute", value=self.mute)
                elif res == "000":
                    self.mute = False
                    self.emit("mute", value=self.mute)
                else:
                    return
            except Exception as e:
                self.log_error(f"parse_response() : {e=}")

    @handle_exception
    def set_power(self, value):
        self.send("PON" if value else "POF")
        self.power = value
        # USERDATA.set_value(f"{self.name}_power", self.power)
        self.emit("power", value=self.power)

    @handle_exception
    def power_on(self):
        self.set_power(True)

    @handle_exception
    def power_off(self):
        self.set_power(False)

    @handle_exception
    def set_mute(self, value):
        self.send("OSH:1" if value else "OSH:0")
        self.mute = value
        # USERDATA.set_value(f"{self.name}_mute", self.mute)
        self.emit("mute", value=self.mute)

    @handle_exception
    def mute_on(self):
        self.set_mute(True)

    @handle_exception
    def mute_off(self):
        self.set_mute(False)
