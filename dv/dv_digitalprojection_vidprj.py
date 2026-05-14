# 마지막 수정일 : 20260508
from lib.event_manager import EventManager
from lib.scheduler import Scheduler
from lib.utility import CommonLogger, handle_exception


# todo 기능 더 추가해야 됨
class DigitalProjectionVidprj(CommonLogger, EventManager):
    def __init__(self, dv):
        super().__init__("power", "poweron", "poweroff", "mute", "muted", "unmuted", "poll")
        self.dv = dv
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.power = False
        self.mute = False
        self.last_send_command = ""
        self.poll = Scheduler()

    @handle_exception
    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.dv.online(lambda *_args, **_kwargs: self.start_poll())
        self.dv.offline(lambda *_args, **_kwargs: self.poll.shutdown())

    @handle_exception
    def send(self, msg):
        self.last_send_command = msg
        self.dv.send(msg + "\r")

    @handle_exception
    def start_poll(self, *args):
        @handle_exception
        def query_power():
            self.send("*power ?")

        @handle_exception
        def query_mute():
            self.send("*mute ?")

        self.poll.set_timeout(1.0, lambda: self.poll.set_interval(10.0, query_power))
        self.poll.set_timeout(3.0, lambda: self.poll.set_interval(10.0, query_mute))

    @handle_exception
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

    @handle_exception
    def set_power(self, value):
        self.send("*power = true" if value else "*power = false")
        self.power = value
        self.trigger_event("power", value=value)

    @handle_exception
    def power_on(self):
        self.set_power(True)

    @handle_exception
    def power_off(self):
        self.set_power(False)

    @handle_exception
    def set_mute(self, value):
        self.send("*mute = true" if value else "*mute = false")
        self.mute = value
        self.trigger_event("mute", value=value)

    @handle_exception
    def mute_on(self):
        self.set_mute(True)

    @handle_exception
    def mute_off(self):
        self.set_mute(False)
