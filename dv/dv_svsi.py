# 마지막 수정일 : 20260511
from lib.event_manager import EventManager
from lib.network_manager import TcpClient
from lib.utility import CommonLogger, handle_exception


# note : 프로토타입
# 어차피 파라메터에 때려놓고 필요한거 가져가면 됨 그 정도 속도 안나는 놈 아님
class Svsi(CommonLogger, EventManager):
    DEFAULT_PORT = 50002

    def __init__(self, ip, port=DEFAULT_PORT):
        super().__init__("connected", "disconnected", "received")
        self.dv = TcpClient(ip, port)
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.states = {}

    @handle_exception
    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.dv.connect()

    @handle_exception
    def send(self, msg):
        self.dv.send(msg + "\r")
        self.log_debug(f"send() : ip={self.dv.ip} {msg=}")

    @handle_exception
    def set_live(self):
        self.send("live")

    @handle_exception
    def set_local(self, idx_ch):
        if idx_ch is None:
            self.send("local:1")
        else:
            self.send(f"local:{idx_ch}")

    @handle_exception
    def set_stream(self, idx_ch):
        self.send(f"stream:{idx_ch}")

    @handle_exception
    def get_status(self):
        self.send("get")

    @handle_exception
    def parse_response(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"parse_response() : ip={self.dv.ip} {args=}")
        else:
            responses = args[0].arguments["data"]
            responses = responses.decode("utf-8")
            for response in responses.splitlines():
                if ":" in response:
                    key, value = response.split(":", 1)
                    self.states[key.strip()] = value.strip()
            self.log_debug(f"parse_response() : ip={self.dv.ip}")
            self.log_debug(f"{responses.splitlines()=}")
            self.emit("received")
