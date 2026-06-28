# 마지막 수정일 : 20260629
# Polycom Group 500 - 텍스트 API (RS-232 Serial 19200baud/8N1 또는 Telnet 포트 23)
# 참고: Login Mode를 none으로 설정하면 인증 없이 제어 가능
from lib.event_manager import EventManager
from lib.utility import CommonLogger, handle_exception


class PolycomGroup500(CommonLogger, EventManager):

    def __init__(self, dv):
        super().__init__("call_connected", "call_disconnected", "call_incoming", "mute_changed", "videomute_changed", "volume_changed")
        self.dv = dv
        self.dial = ""
        self.is_in_call = False
        self.is_incoming = False
        self.is_muted_near = False
        self.is_videomuted_near = False
        self.volume = 0

    @handle_exception
    def init(self):
        self.dv.receive.listen(self._on_receive)
        # 상태 변화 푸시 등록
        self._send("callstate register")
        self._send("mute register")
        self._send("videomute register")
        self._send("volume register")
        # 초기 상태 조회
        self._send("mute near get")
        self._send("videomute near get")
        self._send("volume get")
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

    def _parse_line(self, line: str):
        # 통화 상태: cs: call[N] speed[N] dialstr[...] state[connected|disconnected|idle|ringing]
        if line.startswith("cs:"):
            try:
                state = line.split("state[")[1].rstrip("]").lower()
            except IndexError:
                return
            if state == "connected":
                self.is_in_call = True
                self.is_incoming = False
                # emit: call_connected()
                self.emit("call_connected")
            elif state in ("disconnected", "idle"):
                self.is_in_call = False
                self.is_incoming = False
                # emit: call_disconnected()
                self.emit("call_disconnected")
            elif state == "ringing":
                self.is_incoming = True
                # emit: call_incoming()
                self.emit("call_incoming")

        # 오디오 뮤트: mute near on / mute near off
        elif line.startswith("mute near"):
            self.is_muted_near = line.endswith("on")
            # emit: mute_changed(value: bool)
            self.emit("mute_changed", value=self.is_muted_near)

        # 비디오 뮤트: videomute near on / videomute near off
        elif line.startswith("videomute near"):
            self.is_videomuted_near = line.endswith("on")
            # emit: videomute_changed(value: bool)
            self.emit("videomute_changed", value=self.is_videomuted_near)

        # 볼륨: volume N (0~50)
        elif line.startswith("volume "):
            try:
                self.volume = int(line.split()[1])
                # emit: volume_changed(value: int)
                self.emit("volume_changed", value=self.volume)
            except (IndexError, ValueError):
                pass

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
    # 비디오 뮤트

    @handle_exception
    def set_videomute_near(self, enable: bool):
        self._send(f"videomute near {'on' if enable else 'off'}")

    @handle_exception
    def videomute_near_on(self):
        self.set_videomute_near(True)

    @handle_exception
    def videomute_near_off(self):
        self.set_videomute_near(False)

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
    # 카메라 PTZ

    @handle_exception
    def camera_move(self, direction: str):
        # direction: left, right, up, down, zoom+, zoom-
        self._send(f"camera near move {direction}")

    @handle_exception
    def camera_stop(self):
        self._send("camera near stop")

    # ---------------------------------------------------------------------------- #
    # 프리셋 (0~99)

    @handle_exception
    def preset_go(self, index: int):
        self._send(f"preset near go {index}")

    @handle_exception
    def preset_set(self, index: int):
        self._send(f"preset near set {index}")

    # ---------------------------------------------------------------------------- #
    # 슬립 / 웨이크

    @handle_exception
    def sleep(self):
        self._send("sleep")

    @handle_exception
    def wake(self):
        self._send("wake")
