# 마지막 수정일 : 20260629
# Cisco 코덱 - xCommand 프로토콜 (Serial RS-232, 115200 baud)
from lib.event_manager import EventManager
from lib.utility import CommonLogger, handle_exception


class CiscoCodec(CommonLogger, EventManager):

    def __init__(self, dv):
        super().__init__("call_connected", "call_disconnected", "call_incoming", "selfview_changed", "presentation_changed")
        self.dv = dv
        self.dial = ""
        self.is_in_call = False
        self.is_incoming = False
        self.is_selfview = False
        self.is_presentation = False
        self._incoming_call_id = None

    @handle_exception
    def init(self):
        self.log_debug("init()")
        self.dv.receive.listen(self._on_receive)
        self._send("xFeedback Register /Event/CallSuccessful")
        self._send("xFeedback Register /Event/CallDisconnect")
        self._send("xFeedback Register /Event/IncomingCallIndication")
        self._send("xFeedback Register /Status/Video/Selfview/Mode")
        self._send("xFeedback Register /Event/PresentationStarted")
        self._send("xFeedback Register /Event/PresentationStopped")
        # 초기 상태 조회
        self._send("xStatus Video Selfview Mode")
        self._send("xStatus Conference Presentation Mode")

    def _send(self, cmd: str):
        self.dv.send(f"{cmd}\r\n".encode())
        self.log_debug(f"_send {cmd=}")

    @handle_exception
    def _on_receive(self, evt):
        data = evt.arguments.get("data", b"")
        msg = data.decode("utf-8", errors="ignore") if isinstance(data, bytes) else str(data)
        self.log_debug(f"_on_receive {msg=}")
        # 통화 상태
        if "*e CallSuccessful" in msg:
            self.is_in_call = True
            self.is_incoming = False
            self._incoming_call_id = None
            # emit: call_connected()
            self.emit("call_connected")
        elif "*e CallDisconnect" in msg:
            self.is_in_call = False
            self.is_incoming = False
            self._incoming_call_id = None
            # emit: call_disconnected()
            self.emit("call_disconnected")
        # 수신 전화 (*e IncomingCallIndication CallId: N ...)
        elif "*e IncomingCallIndication" in msg:
            try:
                self._incoming_call_id = int(msg.split("CallId:")[1].split()[0])
            except (IndexError, ValueError):
                self._incoming_call_id = None
            self.is_incoming = True
            # emit: call_incoming()
            self.emit("call_incoming")
        # 셀프뷰 상태 (*s Video Selfview Mode: On/Off)
        elif "*s Video Selfview Mode:" in msg:
            self.is_selfview = "On" in msg
            # emit: selfview_changed(value: bool)
            self.emit("selfview_changed", value=self.is_selfview)
        # 프레젠테이션 상태
        elif "*e PresentationStarted" in msg:
            self.is_presentation = True
            # emit: presentation_changed(value: bool)
            self.emit("presentation_changed", value=True)
        elif "*e PresentationStopped" in msg:
            self.is_presentation = False
            # emit: presentation_changed(value: bool)
            self.emit("presentation_changed", value=False)
        # xStatus Conference Presentation Mode 응답 (*s Conference Presentation Mode: Sending/Off)
        elif "*s Conference Presentation Mode:" in msg:
            self.is_presentation = "Sending" in msg
            # emit: presentation_changed(value: bool)
            self.emit("presentation_changed", value=self.is_presentation)

    # ---------------------------------------------------------------------------- #
    # 다이얼 입력 (통화 전 번호 구성)

    @handle_exception
    def append_dial(self, char: str):
        self.dial += char
        self.log_debug(f"append_dial() {char=} dial={self.dial!r}")

    @handle_exception
    def backspace_dial(self):
        self.dial = self.dial[:-1]
        self.log_debug(f"backspace_dial() dial={self.dial!r}")

    @handle_exception
    def clear_dial(self):
        self.dial = ""
        self.log_debug("clear_dial()")

    # ---------------------------------------------------------------------------- #
    # 통화

    @handle_exception
    def call_dial(self):
        self.log_debug(f"call_dial() dial={self.dial!r}")
        if self.dial:
            self._send(f"xCommand Dial Number: {self.dial}")

    @handle_exception
    def call_accept(self):
        self.log_debug(f"call_accept() {self._incoming_call_id=}")
        if self._incoming_call_id is not None:
            self._send(f"xCommand Call Accept CallId: {self._incoming_call_id}")
        else:
            self._send("xCommand Call Accept")

    @handle_exception
    def call_reject(self):
        self.log_debug(f"call_reject() {self._incoming_call_id=}")
        if self._incoming_call_id is not None:
            self._send(f"xCommand Call Reject CallId: {self._incoming_call_id}")
        else:
            self._send("xCommand Call Reject")

    @handle_exception
    def call_disconnect(self):
        self.log_debug("call_disconnect()")
        self._send("xCommand Call Disconnect")

    # ---------------------------------------------------------------------------- #
    # 통화 중 DTMF 전송 (MCU 메뉴 조작 등)

    @handle_exception
    def send_dtmf(self, char: str):
        self.log_debug(f"send_dtmf() {char=}")
        self._send(f"xCommand Call DTMFSend DTMFString: {char}")

    # ---------------------------------------------------------------------------- #
    # 화면

    @handle_exception
    def set_selfview(self, enable: bool):
        self.log_debug(f"set_selfview() {enable=}")
        self._send(f"xCommand Video Selfview Set Mode: {'On' if enable else 'Off'}")

    @handle_exception
    def set_selfview_fullscreen(self, enable: bool):
        self.log_debug(f"set_selfview_fullscreen() {enable=}")
        self._send(f"xCommand Video Selfview Set FullscreenMode: {'On' if enable else 'Off'}")

    @handle_exception
    def set_presentation(self, enable: bool):
        self.log_debug(f"set_presentation() {enable=}")
        self._send(f"xCommand Presentation {'Start' if enable else 'Stop'}")
