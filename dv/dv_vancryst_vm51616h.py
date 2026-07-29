# 마지막 수정일 : 20260714
"""ATEN VanCryst VM5-1616H (16x16 HDMI 매트릭스 스위처) CLI 제어.

RS-232(19200-8-N-1, 흐름제어 없음)와 Telnet(port 23) 둘 다 같은 CLI 명령을 쓰므로,
다른 dv 드라이버들(dv_wp412.py 등)과 동일하게 통신 객체(dv)를 주입받는 방식으로 구현했다.
RS-232로 쓸지 Telnet(TcpClient)으로 쓸지는 config.py 에서 다른 dv 객체를 주입해서 결정.

명령은 CR("\\r")로 종료, 성공 시 "Command OK", 실패 시 "Command incorrect" 로 응답.
(ATEN VM51616H 사용자 매뉴얼 Chapter 5. CLI 참고)
- sw i{xx} o{yy}        : 입력 xx 를 출력 yy 로 라우팅 (yy 자리에 * 가능 - 전체 출력)
- sw o{yy} on / off     : 출력 yy 켜기/끄기 (yy 자리에 * 가능)
- sw o{yy} + / -        : 출력 yy 의 입력을 다음/이전으로 전환 (yy 자리에 * 가능)
- sw i{xx} normal audio / sw i{xx} console audio : 입력 xx 오디오 소스 전환
- mute o{yy} on / off   : 출력 yy 오디오 음소거 on/off (yy 자리에 * 가능)
- cec o{yy} on / off    : 출력 yy CEC 기능 on/off (yy 자리에 * 가능)
- osd o{yy} on / off    : 출력 yy OSD(포트 전환 정보 표시) on/off (yy 자리에 * 가능)
- edid {mode}           : EDID 모드 설정 (default / port1 / remix / custom), 포트 구분 없이 장치 전체 적용
- profile f {nn} load   : 저장된 연결 프로파일 nn(01~32) 을 불러와 적용 (전면 패널 PROFILE 버튼과 동일 동작)

주의: 매뉴얼 CLI 명령어 표에는 입력 범위가 "xx:01~08"로 표기돼 있으나, 매뉴얼 맨 앞 제품
사양은 "16 x 16 HDMI"로 16입력 16출력임. 표기가 오기(다른 모델 챕터 재사용)로 보여 NUM_IN=16
으로 뒀지만, 실제 장비 연결 후 입력 1~16 전체가 정상적으로 라우팅되는지 반드시 확인할 것.
CLI 에 현재 라우팅 상태를 조회하는 명령이 안 보여서, routes 는 스위칭 명령을 보낼 때
낙관적으로만 갱신한다 (장비가 실제로 그 상태인지 재확인하는 별도 read-back 없음).
프로파일 로드(load_profile)는 어떤 입출력이 매핑되는지 CLI 로는 알 수 없으므로 routes 를
갱신하지 않는다 - 로드 후 routes 는 실제 상태와 다를 수 있음에 유의.

주의(프로파일 로드 명령 불일치): 매뉴얼 부록 "Telnet 작동" 절에는 프로파일을 불러오는 별도
명령으로 "LO {nn}" 이 나오는데, Chapter 5. CLI 명령어의 "프로파일 로드 명령어" 절과 형식이
다르다(부록 쪽은 다른/구형 모델 매뉴얼을 그대로 재사용한 것으로 보임 - 위 NUM_IN 오기와 같은
사례). 이 드라이버는 CLI 명령어 목록에 정식으로 실려 있는 "profile f {nn} load" 를 사용한다.
실제 장비에서 두 형식 모두 동작하는지, 혹은 "LO" 만 동작하는지 반드시 확인할 것.

Telnet 로그인: RS-232 와 달리 Telnet(port 23) 은 접속 직후 "Enter Username:" / "Password:"
로그인 절차를 요구하고, 응답이 늦으면 "connections timeout for login!" 과 함께 서버가 연결을
끊는다(매뉴얼 CLI 명령과 무관한, 장비 자체의 텔넷 인증 절차). password 인자를 넘기면 이
드라이버가 로그인 프롬프트를 감지해 자동으로 응답하고, 로그인 완료 전까지는 CLI 명령을
큐에 쌓아뒀다가 로그인 성공 후 흘려보낸다. RS-232 로 쓸 때는 password=None(기본값)으로 두면
로그인 절차 없이 바로 명령을 보낸다.
"""

import threading

from lib.event_manager import EventManager
from lib.utility import CommonLogger, handle_exception


class VancrystVm51616H(CommonLogger, EventManager):
    DEFAULT_PORT = 23  # RS-232 라면 19200-8-N-1
    DEFAULT_TELNET_PORT = 23  # RS-232 라면 19200-8-N-1

    NUM_IN = 16
    NUM_OUT = 16

    LOGIN_USERNAME = "administrator"
    PROMPT_USERNAME = "Enter Username:"
    PROMPT_PASSWORD = "Password:"
    PROMPT_LOGIN_OK = "Password Successful"
    PROMPT_LOGIN_TIMEOUT = "connections timeout for login!"

    def __init__(self, dv, username: str | None = None, password: str | None = None):
        super().__init__("route")
        self.dv = dv
        self.name = f"{__class__.__name__.lower()}_{getattr(self.dv, 'name', '')}"
        self.routes = {i: 0 for i in range(1, self.NUM_OUT + 1)}
        self._buf = ""
        self._pending_cmds = []
        self._username = username  # Telnet 사용 시에만 지정 (RS-232는 None 유지)
        self._password = password  # Telnet 사용 시에만 지정 (RS-232는 None 유지)
        self._logged_in = password is None
        self._sent_username = False
        self._sent_password = False
        # _logged_in/_pending_cmds 는 main 스레드(switch() 등 -> _send())와 TCP 수신 스레드
        # (_parse -> _handle_login/_on_online/_on_offline) 양쪽에서 건드리므로 보호 필요
        self._state_lock = threading.Lock()

    @handle_exception
    def init(self):
        self.dv.receive.listen(self._parse)
        if self._password is not None and hasattr(self.dv, "online"):
            self.dv.online(self._on_online)
        if self._password is not None and hasattr(self.dv, "offline"):
            self.dv.offline(self._on_offline)

    @handle_exception
    def clear_pending_cmds(self):
        with self._state_lock:
            self._pending_cmds = []

    @handle_exception
    def _on_online(self):
        """Called whenever (re)connected - Initialize state as Telnet login procedure must restart from the beginning."""
        self.log_debug("_on_online() : Reconnected, initializing login state")
        self._buf = ""
        with self._state_lock:
            self._logged_in = False
        self._sent_username = False
        self._sent_password = False

    @handle_exception
    def _on_offline(self):
        """연결이 끊기는 즉시 _logged_in 을 내려야 한다 - 재연결(_on_online) 때까지 기다리면,
        그 사이 _send() 가 호출됐을 때 stale 한 _logged_in=True 를 보고 pending 대기열에 쌓지 않고
        바로 dv.send() 를 호출해버려서, 실제로는 끊긴 연결이라 TcpClient.send() 가 조용히 드롭한다."""
        self.log_debug("_on_offline() : Disconnected, marking as logged out")
        with self._state_lock:
            self._logged_in = False

    # ---------------------------------------------------------------------------- #
    def _next_line(self):
        idx = self._buf.find("\r\n")
        if idx < 0:
            return None
        line, self._buf = self._buf[:idx], self._buf[idx + 2 :]
        return line

    def _handle_login(self):
        """Telnet 로그인 프롬프트에 응답한다. 로그인 완료 전까지는 True 를 반환하지 않는다."""
        idx = self._buf.find(self.PROMPT_LOGIN_TIMEOUT)
        if idx >= 0:
            self.log_error("_handle_login() : 로그인 타임아웃 - 장비가 연결을 끊을 예정, 재연결 대기")
            self._buf = ""
            return

        if not self._sent_username:
            idx = self._buf.find(self.PROMPT_USERNAME)
            if idx < 0:
                return
            self._buf = self._buf[idx + len(self.PROMPT_USERNAME) :]
            self.log_debug("_handle_login() : username 전송")
            if self._username:
                self.dv.send(f"{self._username}\r")
            else:
                self.dv.send(f"{self.LOGIN_USERNAME}\r")
            self._sent_username = True
            return

        if not self._sent_password:
            idx = self._buf.find(self.PROMPT_PASSWORD)
            if idx < 0:
                return
            self._buf = self._buf[idx + len(self.PROMPT_PASSWORD) :]
            self.log_debug("_handle_login() : password 전송")
            self.dv.send(f"{self._password}\r")
            self._sent_password = True
            return

        idx = self._buf.find(self.PROMPT_LOGIN_OK)
        if idx < 0:
            return
        self._buf = self._buf[idx + len(self.PROMPT_LOGIN_OK) :]
        # _logged_in=True 설정과 _pending_cmds 비우기를 한 lock 안에서 같이 해야 한다 - 따로 하면
        # 그 사이(스냅샷 이후 ~ clear 이전)에 다른 스레드가 append 한 명령이 clear 로 같이 날아간다.
        with self._state_lock:
            self._logged_in = True
            pending, self._pending_cmds = self._pending_cmds, []
        self.log_info(f"_handle_login() : login successful - {len(pending)} pending command(s)")
        # 오프라인 때 밀렸던 커멘드 싹 보내기
        for payload in pending:
            self.dv.send(payload)

    @handle_exception
    def _parse(self, evt):
        data = evt.arguments.get("data", b"")
        if not data:
            self.log_error(f"_parse() invalid response format {evt=}")
            return

        try:
            self._buf += data.decode("utf-8", "ignore") if isinstance(data, bytes) else data
        except (AttributeError, UnicodeDecodeError) as e:
            self.log_error(f"_parse() decode error {e=}")
            return

        if not self._logged_in:
            self._handle_login()
            if not self._logged_in:
                return

        while True:
            line = self._next_line()
            if line is None:
                return
            line = line.strip()
            if not line:
                continue
            self.log_debug(f"_parse() line={line!r}")
            if line == "Command incorrect":
                self.log_error("_parse() : Device responded with 'Command incorrect' to last command")

    def _send(self, cmd: str):
        payload = f"{cmd}\r"
        with self._state_lock:
            if not self._logged_in:
                self.log_debug(f"_send() : pending command while waiting for login {cmd=}")
                self._pending_cmds.append(payload)
                return
        self.log_debug(f"_send() {cmd=}")
        self.dv.send(payload)

    # ---------------------------------------------------------------------------- #
    @handle_exception
    def switch(self, idx_in: int, idx_out: int):
        """입력 idx_in 을 출력 idx_out 으로 라우팅 (1-based)"""
        if not 1 <= idx_in <= self.NUM_IN:
            raise ValueError(f"invalid idx_in: {idx_in}")
        if not 1 <= idx_out <= self.NUM_OUT:
            raise ValueError(f"invalid idx_out: {idx_out}")
        self._send(f"sw i{idx_in:02d} o{idx_out:02d}")
        self.routes[idx_out] = idx_in
        # emit: route(idx_in: int, idx_out: int, routes: dict)
        self.emit("route", idx_in=idx_in, idx_out=idx_out, routes=self.routes)

    @handle_exception
    def switch_video(self, idx_in: int, idx_out: int):
        """VM5-1616H는 오디오/비디오를 분리 라우팅하는 명령이 없어 switch() 와 동일하게 동작"""
        self.switch(idx_in, idx_out)

    @handle_exception
    def switch_to_all_outputs(self, idx_in: int):
        """입력 idx_in 을 모든 출력에 동시 라우팅 (sw i{xx} o*)"""
        if not 1 <= idx_in <= self.NUM_IN:
            raise ValueError(f"invalid idx_in: {idx_in}")
        self._send(f"sw i{idx_in:02d} o*")
        for idx_out in self.routes:
            self.routes[idx_out] = idx_in
        # emit: route(idx_in: int, idx_out: int, routes: dict)
        self.emit("route", idx_in=idx_in, idx_out=0, routes=self.routes)

    @handle_exception
    def set_output_power(self, idx_out: int, enable: bool):
        """출력 포트 on/off. idx_out=0 이면 전체 출력(*)"""
        if idx_out != 0 and not 1 <= idx_out <= self.NUM_OUT:
            raise ValueError(f"invalid idx_out: {idx_out}")
        target = "*" if idx_out == 0 else f"{idx_out:02d}"
        self._send(f"sw o{target} {'on' if enable else 'off'}")

    @handle_exception
    def step_input(self, idx_out: int, step: int):
        """idx_out 의 입력을 다음(step>0)/이전(step<0) 입력으로 전환. idx_out=0 이면 전체 출력(*)"""
        if step == 0:
            return
        if idx_out != 0 and not 1 <= idx_out <= self.NUM_OUT:
            raise ValueError(f"invalid idx_out: {idx_out}")
        target = "*" if idx_out == 0 else f"{idx_out:02d}"
        self._send(f"sw o{target} {'+' if step > 0 else '-'}")

    @handle_exception
    def set_input_audio_mode(self, idx_in: int, mode: str):
        """입력 idx_in 의 오디오 소스 전환. mode: 'normal'(HDMI 임베디드 오디오) 또는 'console'(콘솔 오디오 입력)"""
        if mode not in ("normal", "console"):
            raise ValueError(f"invalid audio mode: {mode}")
        if not 1 <= idx_in <= self.NUM_IN:
            raise ValueError(f"invalid idx_in: {idx_in}")
        self._send(f"sw i{idx_in:02d} {mode} audio")

    @handle_exception
    def set_output_mute(self, idx_out: int, mute: bool):
        """출력 idx_out 오디오 음소거 on/off. idx_out=0 이면 전체 출력(*)"""
        if idx_out != 0 and not 1 <= idx_out <= self.NUM_OUT:
            raise ValueError(f"invalid idx_out: {idx_out}")
        target = "*" if idx_out == 0 else f"{idx_out:02d}"
        self._send(f"mute o{target} {'on' if mute else 'off'}")

    @handle_exception
    def set_output_cec(self, idx_out: int, enable: bool):
        """출력 idx_out 의 CEC(Consumer Electronics Control) 기능 on/off. idx_out=0 이면 전체 출력(*)"""
        if idx_out != 0 and not 1 <= idx_out <= self.NUM_OUT:
            raise ValueError(f"invalid idx_out: {idx_out}")
        target = "*" if idx_out == 0 else f"{idx_out:02d}"
        self._send(f"cec o{target} {'on' if enable else 'off'}")

    @handle_exception
    def set_output_osd(self, idx_out: int, enable: bool):
        """출력 idx_out 의 OSD(포트 전환 시 화면에 실시간 표시) on/off. idx_out=0 이면 전체 출력(*)"""
        if idx_out != 0 and not 1 <= idx_out <= self.NUM_OUT:
            raise ValueError(f"invalid idx_out: {idx_out}")
        target = "*" if idx_out == 0 else f"{idx_out:02d}"
        self._send(f"osd o{target} {'on' if enable else 'off'}")

    @handle_exception
    def set_edid_mode(self, mode: str):
        """EDID 모드 설정 (장치 전체 적용, 포트별 설정 아님).

        mode: 'default'(ATEN 기본 EDID) / 'port1'(포트1 EDID 를 모든 입력에 전달) /
              'remix'(연결된 각 디스플레이 EDID 사용) / 'custom'(브라우저 GUI 로 저장해둔 커스터마이징 EDID)
        """
        if mode not in ("default", "port1", "remix", "custom"):
            raise ValueError(f"invalid edid mode: {mode}")
        self._send(f"edid {mode}")

    @handle_exception
    def load_profile(self, idx: int):
        """저장된 연결 프로파일 idx(1~32) 를 불러와 적용 (전면 패널 PROFILE 버튼과 동일 동작).

        주의: 프로파일이 실제로 어떤 입출력 매핑을 적용하는지 CLI 로는 알 수 없으므로
        self.routes 는 갱신하지 않는다 - 로드 후 routes 는 실제 상태와 어긋날 수 있다.
        """
        if not 1 <= idx <= 32:
            raise ValueError(f"invalid profile idx: {idx}")
        self._send(f"profile f {idx:02d} load")
        self.log_info(f"load_profile() {idx=} load command sent - routes not updated as actual state is unknown")
