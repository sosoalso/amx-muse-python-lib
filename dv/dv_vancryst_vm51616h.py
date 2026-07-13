# 마지막 수정일 : 20260713
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

주의: 매뉴얼 CLI 명령어 표에는 입력 범위가 "xx:01~08"로 표기돼 있으나, 매뉴얼 맨 앞 제품
사양은 "16 x 16 HDMI"로 16입력 16출력임. 표기가 오기(다른 모델 챕터 재사용)로 보여 NUM_IN=16
으로 뒀지만, 실제 장비 연결 후 입력 1~16 전체가 정상적으로 라우팅되는지 반드시 확인할 것.
CLI 에 현재 라우팅 상태를 조회하는 명령이 안 보여서, routes 는 스위칭 명령을 보낼 때
낙관적으로만 갱신한다 (장비가 실제로 그 상태인지 재확인하는 별도 read-back 없음).
"""

from lib.event_manager import EventManager
from lib.utility import CommonLogger, handle_exception


class VancrystVm51616H(CommonLogger, EventManager):
    DEFAULT_TELNET_PORT = 23  # RS-232 라면 19200-8-N-1

    NUM_IN = 16
    NUM_OUT = 16

    def __init__(self, dv):
        super().__init__("route")
        self.dv = dv
        self.name = f"{__class__.__name__.lower()}_{getattr(self.dv, 'name', '')}"
        self.routes = {i: 0 for i in range(1, self.NUM_OUT + 1)}
        self._buf = ""

    @handle_exception
    def init(self):
        self.dv.receive.listen(self._parse)

    # ---------------------------------------------------------------------------- #
    def _next_line(self):
        idx = self._buf.find("\r\n")
        if idx < 0:
            return None
        line, self._buf = self._buf[:idx], self._buf[idx + 2 :]
        return line

    @handle_exception
    def _parse(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"_parse() invalid response format {args=}")
            return

        try:
            data = args[0].arguments["data"]
            self._buf += data.decode("utf-8", "ignore") if isinstance(data, bytes) else data
        except (AttributeError, UnicodeDecodeError) as e:
            self.log_error(f"_parse() decode error {e=}")
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
                self.log_error("_parse() : 장비가 마지막 명령을 'Command incorrect' 로 응답함")

    def _send(self, cmd: str):
        self.log_debug(f"_send() {cmd=}")
        self.dv.send(f"{cmd}\r".encode())

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
