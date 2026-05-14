# 마지막 수정일 : 20260508
from lib.event_manager import EventManager
from lib.scheduler import Scheduler
from lib.utility import CommonLogger
from lib.utility import handle_exception


# note 프로토타입
class TascamCdp(CommonLogger, EventManager):
    COMMANDS = {
        "play": "012",
        "stop": "010",
        "prev": "01A01",
        "next": "01A00",
        "sdcard": "07F0100",
        "usb": "07F0110",
        "query": "050",
    }

    def __init__(self, dv):
        super().__init__("play", "stop", "source", "status", "received", "error")
        self.dv = dv
        self.poll_interval = 3.0
        self.poll = Scheduler()
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.is_playing = False
        self.source = "unknown"
        self.last_raw_message = ""
        self.last_send_command = ""
        self._is_initialized = False

    @handle_exception
    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.start_poll()

    @handle_exception
    def send(self, msg):
        self.last_send_command = msg
        self.dv.send("\n" + msg + "\r")
        self.log_debug(f"send() {msg=}")

    @handle_exception
    def start_poll(self):
        self.poll.set_timeout(1.0, lambda: self.poll.set_interval(self.poll_interval, self.query_status))

    @handle_exception
    def stop_poll(self):
        self.poll.shutdown()

    @handle_exception
    def play(self):
        self.send(self.COMMANDS.get("play"))
        self._set_playing(True)

    @handle_exception
    def stop(self):
        self.send(self.COMMANDS.get("stop"))
        self._set_playing(False)

    @handle_exception
    def next(self):
        self.send(self.COMMANDS.get("next"))
        self._set_playing(True)

    @handle_exception
    def prev(self):
        self.send(self.COMMANDS.get("prev"))
        self._set_playing(True)

    @handle_exception
    def set_src_sdcard(self):
        self.send(self.COMMANDS.get("sdcard"))
        self._set_source("sdcard")

    @handle_exception
    def set_src_usb(self):
        self.send(self.COMMANDS.get("usb"))
        self._set_source("usb")

    @handle_exception
    def _set_playing(self, value):
        self.is_playing = value
        self.emit("status", key="playing", value=self.is_playing)
        if value:
            self.log_debug(f"_set_playing() {self.is_playing=}")
            self.emit("play")
        else:
            self.log_debug(f"_set_playing() {self.is_playing=}")
            self.emit("stop")

    @handle_exception
    def _set_source(self, source):
        self.source = source
        self.emit("source", value=source)
        self.emit("status", key="source", value=source)

    @handle_exception
    def query_status(self):
        self.send(self.COMMANDS.get("query"))

    @handle_exception
    def parse_response(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"parse_response() invalid response format {args=}")
            return
        try:
            data_text = args[0].arguments["data"].decode("utf-8", errors="ignore")
            part = data_text.split("\r")[0].strip()
            if len(part) < 4:
                return
            key = part[1:3]

            if key == "D0":
                val = part[-2:]
                self.log_debug(f"parse_response() {data_text=} {key=} {part=} {val=}")
                if val == "11":
                    self._set_playing(True)
                elif val == "10":
                    self._set_playing(False)
        except Exception as e:
            self.log_error(f"parse_response() {e=}")
            self.emit("error", value=str(e))
