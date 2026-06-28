# 마지막 수정일 : 20260629
from lib.event_manager import EventManager
from lib.utility import CommonLogger, handle_exception
from lib.network_manager import DEFAULT_TCP_CLIENT_RECONNECT_TIME, TcpClient


class HyperdeckStudio(CommonLogger, EventManager):
    DEFAULT_PORT = 9993

    def __init__(self, ip, port=DEFAULT_PORT, reconnect_time=DEFAULT_TCP_CLIENT_RECONNECT_TIME):
        super().__init__("play", "stop", "record", "preview")
        self.dv = TcpClient(ip, port, reconnect_time=reconnect_time)
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.is_recording = False
        self.is_playing = False
        self.is_stopped = False
        self.transport = "stopped"
        self.timecode = "00:00:00:00"
        self.video_format = ""

    @handle_exception
    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.dv.online(lambda *_args, **_kwargs: self.send("notify: remote: true"))
        self.dv.online(lambda *_args, **_kwargs: self.send("notify: transport: true"))
        self.dv.connect()

    @handle_exception
    def send(self, cmd):
        self.dv.send(f"{cmd}\r\n".encode())

    @handle_exception
    def record(self):
        self.send("record")
        self.is_recording = True
        self.is_playing = False
        self.is_stopped = False
        # emit: record()
        self.emit("record")
        # emit: transport(transport: str)
        self.emit("transport", transport=self.transport)

    @handle_exception
    def stop(self):
        self.send("stop")
        self.is_playing = False
        self.is_recording = False
        self.is_stopped = True
        # emit: stop()
        self.emit("stop")
        # emit: transport(transport: str)
        self.emit("transport", transport=self.transport)

    @handle_exception
    def play(self):
        self.send("play")
        self.is_playing = True
        self.is_recording = False
        self.is_stopped = False
        # emit: play()
        self.emit("play")
        # emit: transport(transport: str)
        self.emit("transport", transport=self.transport)

    @handle_exception
    def track_prev(self):
        self.send("goto: clip id: -1")

    @handle_exception
    def track_next(self):
        self.send("goto: clip id: +1")

    @handle_exception
    def track_start(self):
        self.send("goto: clip: start")

    @handle_exception
    def track_end(self):
        self.send("goto: clip: end")

    @handle_exception
    def parse_response(self, *args):
        try:
            if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
                return
            data_text = args[0].arguments["data"].decode("utf-8")
            self.log_debug(f"parse_response() {data_text=}")
            while "\r\n" in data_text:
                response = data_text.split("\r\n", 1)[0]
                data_text = data_text.split("\r\n", 1)[1]  # 처리한 줄 제거
                if response.startswith("status: "):
                    if "record" in response[7:]:
                        self.is_recording = True
                        self.is_playing = False
                        self.is_stopped = False
                        self.transport = "record"
                        # emit: record()
                        self.emit("record")
                    elif "stopped" in response[7:]:
                        self.is_recording = False
                        self.is_playing = False
                        self.is_stopped = True
                        self.transport = "stopped"
                        # emit: stop()
                        self.emit("stop")
                    elif "preview" in response[7:]:
                        self.is_recording = False
                        self.is_playing = False
                        self.is_stopped = False
                        self.transport = "preview"
                        # emit: preview()
                        self.emit("preview")
                    elif "play" in response[7:]:
                        self.is_recording = False
                        self.is_playing = True
                        self.is_stopped = False
                        self.transport = "play"
                        # emit: play()
                        self.emit("play")
                    else:
                        return
                    # emit: transport(transport: str, this: HyperdeckStudio)
                    self.emit("transport", transport=self.transport, this=self)
                elif response.startswith("display timecode: "):
                    self.timecode = response[17:].strip()
                    # emit: timecode(timecode: str)
                    self.emit("timecode", timecode=self.timecode)
                elif response.startswith("video format: "):
                    self.video_format = response[14:].strip()
        except (AttributeError, KeyError, UnicodeDecodeError) as e:
            self.log_error(f"Error decoding data: {e}")
