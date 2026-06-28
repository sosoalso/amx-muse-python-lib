# 마지막 수정일 : 20260514
from lib.event_manager import EventManager
from lib.network_manager import DEFAULT_TCP_CLIENT_RECONNECT_TIME, TcpClient
from lib.scheduler import Scheduler
from lib.utility import CommonLogger, handle_exception


# note : 프로토타입
class SvsiN2600(CommonLogger, EventManager):
    DEFAULT_PORT = 50002

    def __init__(self, ip, port=DEFAULT_PORT, reconnect_time=DEFAULT_TCP_CLIENT_RECONNECT_TIME):
        super().__init__("connected", "disconnected", "received")
        self.dv = TcpClient(ip, port, reconnect_time=reconnect_time)
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.states = {}
        self.poll = Scheduler()

    @handle_exception
    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.dv.online(lambda *_args, **_kwargs: self.poll.set_interval(10.0, self.get_status))
        self.dv.offline(lambda *_args, **_kwargs: self.poll.shutdown())
        self.dv.connect()

    def send(self, msg):
        self.dv.send(msg + "\n")
        self.log_debug(f"send() : ip={self.dv.ip} {msg=}")

    def set_live(self):
        self.send("live")

    @handle_exception
    def set_local(self, idx_ch):
        if idx_ch is None:
            self.send("local:1")
        else:
            self.send(f"local:{idx_ch}")

    @handle_exception
    # 인코더 용
    def set_stream(self, idx_ch):
        self.send(f"setSettings:stream:{idx_ch}")

    @handle_exception
    # 디코더 용
    def set(self, idx_ch):
        self.send(f"set:{idx_ch}")

    # 디코더 용
    @handle_exception
    def seta(self, idx_ch):
        self.send(f"seta:{idx_ch}")

    def get_status(self):
        self.send("getStatus")

    @handle_exception
    def parse_response(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"parse_response() ip={self.dv.ip} {args=}")
        else:
            responses = args[0].arguments["data"]
            responses = responses.decode("utf-8")
            for response in responses.splitlines():
                if ":" in response:
                    key, value = response.split(":", 1)
                    self.states[key.strip()] = value.strip()
            self.log_debug(f"parse_response() : ip={self.dv.ip}")
            self.log_debug(f"{self.states=}")
            self.emit("received")
