# 마지막 수정일 : 20260625
# Cisco 코덱 - xCommand 프로토콜 (Serial RS-232, 115200 baud)
from lib.utility import CommonLogger, handle_exception


class CiscoCodec(CommonLogger):

    def __init__(self, dv):
        self.dv = dv
        self.dial = ""

    @handle_exception
    def init(self):
        pass

    def _send(self, cmd: str):
        self.dv.send(f"{cmd}\r\n".encode())
        self.log_debug(f"_send {cmd=}")

    # ---------------------------------------------------------------------------- #
    # 다이얼 입력

    @handle_exception
    def append_dial(self, char: str):
        self.dial += char

    @handle_exception
    def backspace_dial(self):
        self.dial = self.dial[:-1]

    @handle_exception
    def clear_dial(self):
        self.dial = ""

    # ---------------------------------------------------------------------------- #
    # 통화

    @handle_exception
    def call_dial(self):
        if self.dial:
            self._send(f"xCommand Dial Number: {self.dial}")

    @handle_exception
    def call_disconnect(self):
        self._send("xCommand Call Disconnect")

    # ---------------------------------------------------------------------------- #
    # 화면

    @handle_exception
    def set_selfview(self, enable: bool):
        self._send(f"xCommand Video Selfview Set Mode: {'On' if enable else 'Off'}")

    @handle_exception
    def set_selfview_fullscreen(self, enable: bool):
        self._send(f"xCommand Video Selfview Set FullscreenMode: {'On' if enable else 'Off'}")

    @handle_exception
    def set_presentation(self, enable: bool):
        self._send(f"xCommand Presentation {'Start' if enable else 'Stop'}")
