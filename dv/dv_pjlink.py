# 마지막 수정일 : 20260511
from lib.event_manager import EventManager
from lib.network_manager import TcpClient, DEFAULT_TCP_CLIENT_RECONNECT_TIME
from lib.scheduler import Scheduler
from lib.utility import CommonLogger, handle_exception


# SECTION : 제어 장비
# todo 기능 더 추가해야 됨
class PjLink(CommonLogger, EventManager):
    DEFAULT_PORT = 4352

    def __init__(self, ip, port=DEFAULT_PORT, reconnect_time=DEFAULT_TCP_CLIENT_RECONNECT_TIME):
        super().__init__("power", "poweron", "poweroff", "mute", "muted", "unmuted", "poll", "lamp_time")
        self.dv = TcpClient(ip, port, reconnect_time=reconnect_time)
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.power = False  # USERDATA.get_value(f"{self.name}_power", False)
        self.mute = False  # USERDATA.get_value(f"{self.name}_mute", False)
        self.freeze = False  # USERDATA.get_value(f"{self.name}_freeze", False)
        self.source = "0"
        self.lamp_time = 0
        self.poll = Scheduler()

    @handle_exception
    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.dv.online(lambda *_args, **_kwargs: self.start_poll())
        self.dv.offline(lambda *_args, **_kwargs: self.poll.shutdown())
        self.dv.connect()

    @handle_exception
    def start_poll(self, *args):
        @handle_exception
        def query_power():
            self.dv.send("%1POWR ?\r")

        @handle_exception
        def query_mute():
            self.dv.send("%1AVMT ?\r")

        @handle_exception
        def query_lamp():
            self.dv.send("%1LAMP ?\r")

        @handle_exception
        def query_freeze():
            self.dv.send("%2FREZ ?\r")

        self.poll.set_timeout(1.0, lambda: self.poll.set_interval(10.0, query_power))
        self.poll.set_timeout(2.0, lambda: self.poll.set_interval(10.0, query_mute))
        self.poll.set_timeout(3.0, lambda: self.poll.set_interval(10.0, query_lamp))
        self.poll.set_timeout(4.0, lambda: self.poll.set_interval(10.0, query_freeze))

    @handle_exception
    def parse_response(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"Received response has an invalid format. {args=}")
        else:
            try:
                data_text = args[0].arguments["data"].decode("utf-8")
                response = data_text.split("\r")[0]
                res = response.partition("=")[2]
                if "%1POWR=" in response:
                    if res == "1":
                        self.power = True
                    elif res == "0":
                        self.power = False
                    else:
                        return
                    # USERDATA.set_value(f"{self.name}_power", self.power)
                    # emit: power(value: bool)
                    self.emit("power", value=self.power)
                elif "%1AVMT=" in response:
                    try:
                        if res == "31":
                            self.mute = True
                        elif res == "30":
                            self.mute = False
                        else:
                            return
                        # USERDATA.set_value(f"{self.name}_mute", self.mute)
                        # emit: mute(value: bool)
                        self.emit("mute", value=self.mute)
                    except ValueError:
                        self.log_error(f"Invalid video mute response: {res}")
                elif "%1LAMP=" in response:
                    try:
                        p = res.split()[0]
                        if p.isnumeric():
                            self.lamp_time = int(p) or -1
                            # USERDATA.set_value(f"{self.name}_lamp_time", self.lamp_time)
                            # emit: lamp_time(value: int)
                            self.emit("lamp_time", value=self.lamp_time)
                    except ValueError:
                        self.log_error(f"Invalid lamp time response: {res}")
                elif "%2FREZ=" in response:
                    res = response.partition("=")[2]
                    try:
                        if res == "1":
                            self.freeze = True
                        elif res == "0":
                            self.freeze = False
                        else:
                            return
                        # USERDATA.set_value(f"{self.name}_freeze", self.freeze)
                    except ValueError:
                        self.log_error(f"Invalid freeze response: {res}")
            except (AttributeError, KeyError, UnicodeDecodeError) as e:
                self.log_error(f"PJLink {self.name=} Error decoding data: {e}")

    @handle_exception
    def set_power(self, value):
        self.dv.send("%1POWR 1\r" if value else "%1POWR 0\r")
        self.power = value
        # USERDATA.set_value(f"{self.name}_power", self.power)
        # emit: power(value: bool)
        self.emit("power", value=self.power)

    @handle_exception
    def power_on(self):
        self.set_power(True)

    @handle_exception
    def power_off(self):
        self.set_power(False)

    @handle_exception
    def set_mute(self, value):
        self.dv.send("%1AVMT 31\r" if value else "%1AVMT 30\r")
        self.mute = value
        # USERDATA.set_value(f"{self.name}_mute", self.mute)
        # emit: mute(value: bool)
        self.emit("mute", value=self.mute)

    @handle_exception
    def mute_on(self):
        self.set_mute(True)

    @handle_exception
    def mute_off(self):
        self.set_mute(False)

    @handle_exception
    def set_freeze(self, value):
        self.dv.send("%2FREZ 1\r" if value else "%2FREZ 0\r")
        self.freeze = value
        # USERDATA.set_value(f"{self.name}_freeze", self.freeze)
        # emit: freeze(value: bool)
        self.emit("freeze", value=self.freeze)

    @handle_exception
    def freeze_on(self):
        self.set_freeze(True)

    @handle_exception
    def freeze_off(self):
        self.set_freeze(False)
