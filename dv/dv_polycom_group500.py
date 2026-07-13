# 마지막 수정일 : 20260713
# Polycom Group 500 - 텍스트 API (RS-232 Serial 19200baud/8N1 또는 Telnet 포트 23)
# 참고: Login Mode를 none으로 설정하면 인증 없이 제어 가능
from lib.event_manager import EventManager
from lib.utility import CommonLogger, handle_exception


class PolycomGroup500(CommonLogger, EventManager):

    def __init__(self, dv):
        super().__init__(
            "call_connected",
            "call_disconnected",
            "call_incoming",
            "selfview_changed",
            "presentation_changed",
        )
        self.dv = dv
        self.dial = ""
        self.is_in_call = False
        self.is_incoming = False
        self.is_selfview = False
        self.is_presentation = False

    @handle_exception
    def init(self):
        self.dv.receive.listen(self._on_receive)
        self._send("callstate register")
        # 초기 상태 조회
        self._send("systemsetting selfview get")
        self._send("vcbutton get")
        self._send("getcallstate")

    def _send(self, cmd: str):
        self.dv.send(f"{cmd}\r\n".encode())
        self.log_debug(f"_send {cmd=}")

    @handle_exception
    def _on_receive(self, evt):
        data = evt.arguments.get("data", b"")
        msg = data.decode("utf-8", errors="ignore") if isinstance(data, bytes) else str(data)
        self.log_debug(f"_on_receive {msg=}")
        for line in msg.splitlines():
            line = line.strip()
            if line:
                self._parse_line(line)

    @handle_exception
    def _parse_line(self, line: str):
        # 콜론 포함/미포함 응답 모두 처리하기 위해 정규화: "selfview: on" → "selfview on"
        normalized = line.replace(":", " ").split()

        # 통화 상태: cs: call[N] speed[N] dialstr[...] state[connected|disconnected|idle|ringing]
        if line.startswith("cs:"):
            try:
                state = line.split("state[")[1].rstrip("]").lower()
            except IndexError:
                return
            if state == "connected":
                self.is_in_call = True
                self.is_incoming = False
                self.emit("call_connected")
            elif state in ("disconnected", "idle"):
                self.is_in_call = False
                self.is_incoming = False
                self.emit("call_disconnected")
            elif state == "ringing":
                self.is_incoming = True
                self.emit("call_incoming")

        # 셀프뷰 (로컬 카메라 미리보기): "systemsetting selfview on" / "systemsetting selfview: on"
        elif line.startswith("systemsetting selfview"):
            state = normalized[-1].lower() if normalized else ""
            if state in ("on", "off"):
                self.is_selfview = state == "on"
                self.emit("selfview_changed", value=self.is_selfview)

        # 프레젠테이션: "vcbutton play [N]" / "vcbutton stop"
        elif line.startswith("vcbutton") and len(normalized) >= 2:
            action = normalized[1].lower()
            if action == "play":
                self.is_presentation = True
                self.emit("presentation_changed", value=self.is_presentation)
            elif action == "stop":
                self.is_presentation = False
                self.emit("presentation_changed", value=self.is_presentation)

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
    def call_dial(self, speed: int = 384, protocol: str = "h323"):
        if self.dial:
            self._send(f"dial manual {speed} {self.dial} {protocol}")

    @handle_exception
    def call_accept(self):
        self._send("answer video")

    @handle_exception
    def call_reject(self):
        # hangup all은 수신 거절과 통화 종료 모두 처리
        self._send("hangup all")

    @handle_exception
    def call_disconnect(self):
        self._send("hangup all")

    # ---------------------------------------------------------------------------- #
    # 오디오 뮤트

    @handle_exception
    def set_mute_near(self, enable: bool):
        self._send(f"mute near {'on' if enable else 'off'}")

    @handle_exception
    def mute_near_on(self):
        self.set_mute_near(True)

    @handle_exception
    def mute_near_off(self):
        self.set_mute_near(False)

    @handle_exception
    def toggle_mute_near(self):
        self._send("mute near toggle")

    # ---------------------------------------------------------------------------- #
    # 비디오 뮤트 (원격 전송 차단 - 상대방에게 블랙 화면 전송)

    @handle_exception
    def set_videomute_near(self, enable: bool):
        self._send(f"videomute near {'on' if enable else 'off'}")

    @handle_exception
    def toggle_videomute_near(self):
        self._send("videomute near toggle")

    # ---------------------------------------------------------------------------- #
    # 셀프뷰 (로컬 카메라 미리보기 화면 표시)

    @handle_exception
    def set_selfview(self, enable: bool):
        self._send(f"selfview {'on' if enable else 'off'}")

    @handle_exception
    def toggle_selfview(self):
        self.set_selfview(not self.is_selfview)

    # ---------------------------------------------------------------------------- #
    # 프레젠테이션 (HDMI 콘텐츠 공유)

    @handle_exception
    def set_presentation(self, enable: bool, index_source=2):
        self._send(f"vcbutton {f'play {index_source}' if enable else 'stop'}")

    @handle_exception
    def toggle_presentation(self):
        self.set_presentation(not self.is_presentation)

    # ---------------------------------------------------------------------------- #
    # 볼륨 (0~50)

    @handle_exception
    def volume_up(self):
        self._send("volume up")

    @handle_exception
    def volume_down(self):
        self._send("volume down")

    @handle_exception
    def set_volume(self, level: int):
        self._send(f"volume set {max(0, min(50, level))}")

    # ---------------------------------------------------------------------------- #
    # 슬립 / 웨이크

    @handle_exception
    def sleep(self):
        self._send("sleep")

    @handle_exception
    def wake(self):
        self._send("wake")

    # ---------------------------------------------------------------------------- #
    # 리모컨 버튼 에뮬레이션 (button <name>)

    # 지원 키 (Group 500 button 명령)
    BUTTON_NAMES = frozenset(
        [
            "#", "*", ".",
            "0", "1", "2", "3", "4", "5", "6", "7", "8", "9",
            "down", "left", "right", "select", "up",
            "back", "call", "graphics", "hangup",
            "help", "mute", "volume+", "volume-",
            "camera", "delete", "directory", "home", "keyboard", "period", "pip", "preset",
            "info",
        ]
    )

    @handle_exception
    def button(self, name: str):
        if name not in self.BUTTON_NAMES:
            self.log_error(f"button() unknown {name=}")
            return
        self._send(f"button {name}")

    @handle_exception
    def button_up(self):
        self.button("up")

    @handle_exception
    def button_down(self):
        self.button("down")

    @handle_exception
    def button_left(self):
        self.button("left")

    @handle_exception
    def button_right(self):
        self.button("right")

    @handle_exception
    def button_select(self):
        self.button("select")

    @handle_exception
    def button_home(self):
        self.button("home")

    @handle_exception
    def button_back(self):
        self.button("back")

    # 통화
    @handle_exception
    def button_call(self):
        self.button("call")

    @handle_exception
    def button_hangup(self):
        self.button("hangup")

    # 오디오
    @handle_exception
    def button_mute(self):
        self.button("mute")

    @handle_exception
    def button_volume_up(self):
        self.button("volume+")

    @handle_exception
    def button_volume_down(self):
        self.button("volume-")

    # 기타 기능
    @handle_exception
    def button_graphics(self):
        self.button("graphics")

    @handle_exception
    def button_help(self):
        self.button("help")

    @handle_exception
    def button_camera(self):
        self.button("camera")

    @handle_exception
    def button_delete(self):
        self.button("delete")

    @handle_exception
    def button_directory(self):
        self.button("directory")

    @handle_exception
    def button_keyboard(self):
        self.button("keyboard")

    @handle_exception
    def button_period(self):
        self.button("period")

    @handle_exception
    def button_pip(self):
        self.button("pip")

    @handle_exception
    def button_preset(self):
        self.button("preset")

    @handle_exception
    def button_info(self):
        self.button("info")

    # 숫자패드 / 기호
    @handle_exception
    def button_digit(self, digit):
        """0~9 숫자 키 (digit: int 또는 str)"""
        self.button(str(digit))

    @handle_exception
    def button_star(self):
        self.button("*")

    @handle_exception
    def button_pound(self):
        self.button("#")

    @handle_exception
    def button_dot(self):
        self.button(".")
