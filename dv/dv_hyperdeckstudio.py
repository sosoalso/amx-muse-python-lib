from lib.eventmanager import EventManager
from lib.utility import CommonLogger


class HyperDeckStudio(CommonLogger, EventManager):
    PORT = 9993

    def __init__(self, dv):
        super().__init__("play", "stop", "record", "preview")
        self.dv = dv
        self.is_recording = False
        self.is_playing = False
        self.is_stopped = False
        self.timecode = "00:00:00:00"
        self.video_format = ""
        self.init()

    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.dv.online(lambda: self.send("notify: remote: true"))
        self.dv.online(lambda: self.send("notify: transport: true"))

    def send(self, cmd):
        self.dv.send(f"{cmd}\r\n".encode())

    def record(self):
        self.send("record")
        self.is_recording = True
        self.is_playing = False
        self.is_stopped = False
        self.emit("record")

    def stop(self):
        self.send("stop")
        self.is_playing = False
        self.is_recording = False
        self.is_stopped = True
        self.emit("stop")

    def play(self):
        self.send("play")
        self.is_playing = True
        self.is_recording = False
        self.is_stopped = False
        self.emit("play")

    def track_prev(self):
        self.send("goto: clip id: -1")

    def track_next(self):
        self.send("goto: clip id: +1")

    def track_start(self):
        self.send("goto: clip: start")

    def track_end(self):
        self.send("goto: clip: end")

    def parse_response(self, *args):
        try:
            if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
                return
            data_text = args[0].arguments["data"].decode("utf-8")
            self.log_debug(data_text)
            while "\r\n" in data_text:
                response = data_text.split("\r\n", 1)[0]
                data_text = data_text.split("\r\n", 1)[1]  # 처리한 줄 제거
                # ---------------------------------------------------------------------------- #
                if response.startswith("status: "):
                    if "record" in response[7:]:
                        self.is_recording = True
                        self.is_playing = False
                        self.is_stopped = False
                        self.emit("record")
                    elif "stopped" in response[7:]:
                        self.is_recording = False
                        self.is_playing = False
                        self.is_stopped = True
                        self.emit("stop")
                    elif "preview" in response[7:]:
                        self.is_recording = False
                        self.is_playing = False
                        self.is_stopped = False
                        self.emit("preview")
                    elif "play" in response[7:]:
                        self.is_recording = False
                        self.is_playing = True
                        self.is_stopped = False
                        self.emit("play")
                    # ---------------------------------------------------------------------------- #
                elif response.startswith("display timecode: "):
                    self.timecode = response[17:].strip()
                    self.emit("timecode", timecode=self.timecode)
                elif response.startswith("video format: "):
                    self.video_format = response[14:].strip()
                    # context.log.info(f"Video format: {self.video_format}")
        except (AttributeError, KeyError, UnicodeDecodeError) as e:
            print(f"Error decoding data: {e}")
