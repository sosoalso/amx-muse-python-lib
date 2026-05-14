from lib.eventmanager import EventManager
from lib.networkmanager import TcpClient
from lib.utility import handle_exception


# note : 프로토타입
# 어차피 파라메터에 때려놓고 필요한거 가져가면 됨 그 정도 속도 안나는 놈 아님
class Svsi(EventManager):
    def __init__(self, ip_address, name=None):
        super().__init__("connected", "disconnected", "received")
        self.dv = TcpClient(ip_address, 50002)
        self.states = {}
        self.name = name
        self.debug = False

    def log_debug(self, message):
        if self.debug:
            print(f"{self.__class__.__name__} (DEBUG) -- {message}")

    @handle_exception
    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.dv.connect()

    def send(self, msg):
        self.dv.send(msg + "\r")
        self.log_debug(f"{self.__class__.__name__} send() {self.name if self.name else ''} ip={self.dv.ip} {msg=}")

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

    def get_status(self):
        self.send("get")

    @handle_exception
    def parse_response(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"{self.__class__.__name__} parse_response() {self.name if self.name else ''} ip={self.dv.ip} {args=}")
        else:
            responses = args[0].arguments["data"]
            responses = responses.decode("utf-8")
            for response in responses.splitlines():
                if ":" in response:
                    key, value = response.split(":", 1)
                    self.states[key.strip()] = value.strip()
            self.log_debug(f"{self.__class__.__name__} parse_response()  {self.name if self.name else ''} ip={self.dv.ip}")
            self.log_debug(f"{responses.splitlines()=}")

            self.emit("received")
