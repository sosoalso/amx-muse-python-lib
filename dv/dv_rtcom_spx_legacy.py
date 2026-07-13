# 마지막 수정일 : 20260713
"""RTCOM SPX 시리즈 HDMI 매트릭스 스위처 제어 - 구식(vol.1) ASCII 커맨드 프로토콜.

매뉴얼 § 6 Control Command vol.1 기준. RS-232 또는 TCP/IP(Telnet, 기본 23번 포트) 로 통신하며,
커맨드는 "*" 로 시작, "!" 로 끝나고, CR LF (Ctrl+Enter) 로 실행된다.
    *{router_id}{command}!\\r\\n

router_id 는 기본 255, 임의의 라우터에 항상 반응하는 범용 ID는 999 (UNIVERSAL_ROUTER_ID).
포트 번호/값은 커맨드마다 고정된 자리수로 0-padding 되어야 한다 (예: 입출력 포트는 3자리, 타이밍/모드 코드는 2자리).

§ 7 Control Command vol.2 (신식 `s .../r ...!` 프로토콜) 는 [dv_rtcom_spx.py](dv_rtcom_spx.py) 의
RtcomSpx 클래스에서 다룬다. 신식 프로토콜을 지원하는 펌웨어라면 그쪽을 우선 사용할 것.
"""

import re

from lib.event_manager import EventManager
from lib.network_manager import DEFAULT_TCP_CLIENT_RECONNECT_TIME, TcpClient
from lib.utility import CommonLogger, handle_exception


class RtcomSpxLegacy(CommonLogger, EventManager):
    DEFAULT_PORT = 23
    DEFAULT_ROUTER_ID = 255
    UNIVERSAL_ROUTER_ID = 999

    # 6장 커맨드 코드 문자표 - Output Scaler Timing(H)/QuadView(M)/Wall(M) 공용 해상도 코드
    TIMING_AUTO = 1
    TIMING_720X480P60 = 2
    TIMING_720X576P50 = 3
    TIMING_1280X720P50 = 4
    TIMING_1280X720P59 = 5
    TIMING_1280X720P60 = 6
    TIMING_1920X1080P50 = 7
    TIMING_1920X1080P59 = 8
    TIMING_1920X1080P60 = 9
    TIMING_3840X2160P30 = 10
    TIMING_3840X2160P50 = 11
    TIMING_3840X2160P59 = 12
    TIMING_3840X2160P60 = 13
    TIMING_1024X768P60 = 14
    TIMING_1280X1024P60 = 15
    TIMING_1920X1200P60 = 16

    # OV 커맨드 - Output Video Stream Set
    STREAM_NORMAL = 0
    STREAM_FREEZE = 1
    STREAM_BLACK = 2

    def __init__(
        self,
        dv,
        max_inputs=16,
        max_outputs=20,
        router_id=DEFAULT_ROUTER_ID,
        reconnect_time=DEFAULT_TCP_CLIENT_RECONNECT_TIME,
    ):
        super().__init__("received", "ack", "route")
        self.dv = dv
        self.max_inputs = max_inputs
        self.max_outputs = max_outputs
        self.router_id = router_id
        self.name = f"{__class__.__name__.lower()}_{getattr(self.dv, 'name', '') or ''}"
        self.routes = {output_id: 0 for output_id in range(1, self.max_outputs + 1)}

    @handle_exception
    def init(self):
        self.dv.receive.listen(self.parse_response)

    @handle_exception
    def _send(self, body: str):
        cmd = f"*{self.router_id}{body}!"
        self.dv.send(f"{cmd}\r\n".encode())
        self.log_debug(f"_send() : cmd={cmd}")

    @staticmethod
    def _port_range(port_id, port_id_end=None) -> str:
        if port_id_end:
            return f"O{port_id:03d}-{port_id_end:03d}"
        return f"O{port_id:03d}"

    @handle_exception
    def get_route_value(self, output_id) -> int:
        return self.routes.get(output_id, 0)

    @handle_exception
    def parse_response(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"parse_response() : {args=}")
            return
        text = args[0].arguments["data"].decode(errors="ignore")
        self.log_debug(f"parse_response() : {text=}")
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            ack_match = re.match(rf"\*{self.router_id}s(.+)", line, re.IGNORECASE)
            if ack_match:
                # emit: ack(success: bool, body: str)
                self.emit("ack", success=True, body=ack_match.group(1))
                route_match = re.match(r"CI(\d{3})O(\d{3})", ack_match.group(1), re.IGNORECASE)
                if route_match:
                    input_id, output_id = int(route_match.group(1)), int(route_match.group(2))
                    if output_id in self.routes:
                        self.routes[output_id] = input_id
                        # emit: route(idx_in: int, idx_out: int)
                        self.emit("route", idx_in=input_id, idx_out=output_id)
                continue
            if "error" in line.lower():
                # emit: ack(success: bool, body: str)
                self.emit("ack", success=False, body=line)
        # emit: received(text: str)
        self.emit("received", text=text)

    # ------------------------------------------------------------------ #
    # Switching (C/D)
    # ------------------------------------------------------------------ #
    @handle_exception
    def switch(self, input_id, output_id, output_id_end=None):
        """input_id: 1~max_inputs, output_id(_end): 출력 포트 (범위 연결 시 output_id_end 지정)"""
        self._send(f"CI{input_id:03d}{self._port_range(output_id, output_id_end)}")
        self.log_debug(f"connect() : {input_id=} {output_id=} {output_id_end=}")

    @handle_exception
    def disconnect_switch(self, output_id, output_id_end=None):
        self._send(f"DI000{self._port_range(output_id, output_id_end)}")

    # ------------------------------------------------------------------ #
    # Preset (P) / Video Status (?V)
    # ------------------------------------------------------------------ #
    @handle_exception
    def call_preset(self, preset_id):
        self._send(f"PC{preset_id:02d}")

    @handle_exception
    def get_video_status(self, output_id=0):
        """output_id: 0(all)~max_outputs"""
        self._send(f"?VO{output_id:03d}")

    # ------------------------------------------------------------------ #
    # Input (IF/IA)
    # ------------------------------------------------------------------ #
    @handle_exception
    def get_input_info(self, input_id):
        self._send(f"IFI{input_id:03d}")

    @handle_exception
    def set_input_volume(self, input_id, volume):
        """volume: 10~70 (0.5dB step, 50=0dB, 70=+10dB, 10=Mute)"""
        self._send(f"IAI{input_id:03d}V{volume:02d}")

    @handle_exception
    def get_input_volume(self, input_id=0):
        """input_id: 0(all)~max_inputs"""
        self._send(f"?IAI{input_id:03d}V")

    # ------------------------------------------------------------------ #
    # Output (OF/OS/OV/OG/OQ/OW/OB/OR/OC/OA)
    # ------------------------------------------------------------------ #
    @handle_exception
    def get_output_info(self, output_id):
        self._send(f"OFO{output_id:03d}")

    @handle_exception
    def set_output_timing(self, output_id, timing_code, output_id_end=None):
        """timing_code: TIMING_* 상수"""
        self._send(f"OS{self._port_range(output_id, output_id_end)}H{timing_code:02d}")

    @handle_exception
    def set_output_stream_mode(self, output_id, mode, output_id_end=None):
        """mode: STREAM_* 상수"""
        self._send(f"OV{self._port_range(output_id, output_id_end)}M{mode:02d}")

    @handle_exception
    def set_output_brightness(self, output_id, value, output_id_end=None):
        """value: 0~255, default 128"""
        self._send(f"OG{self._port_range(output_id, output_id_end)}B{value:03d}")

    @handle_exception
    def set_output_hue(self, output_id, value, output_id_end=None):
        """value: 0~255, default 128"""
        self._send(f"OG{self._port_range(output_id, output_id_end)}H{value:03d}")

    @handle_exception
    def set_output_saturation(self, output_id, value, output_id_end=None):
        """value: 0~255, default 128"""
        self._send(f"OG{self._port_range(output_id, output_id_end)}S{value:03d}")

    @handle_exception
    def set_output_contrast(self, output_id, value, output_id_end=None):
        """value: 0~255, default 128"""
        self._send(f"OG{self._port_range(output_id, output_id_end)}C{value:03d}")

    @handle_exception
    def set_output_quadview(self, output_id, timing_code, layer_id=None):
        """timing_code: 0(off) 또는 TIMING_* (TIMING_AUTO 는 QuadView 미지원), layer_id: 레이어 번호"""
        body = f"OQO{output_id:03d}M{timing_code:02d}"
        if layer_id is not None:
            body += f"L{layer_id:02d}"
        self._send(body)

    @handle_exception
    def set_wall_mode(self, output_id_start, output_id_end, timing_code, hdiv, vdiv, output_order: list[int]):
        """output_id_start~end: Wall 로 구성할 출력 범위, hdiv/vdiv: 가로/세로 분할 수,
        output_order: Wall 레이어 순서대로 나열한 출력 포트 번호 목록"""
        outputs = "".join(f"O{o:03d}" for o in output_order)
        self._send(f"OWO{output_id_start:03d}-{output_id_end:03d}M{timing_code:02d}H{hdiv:02d}V{vdiv:02d}{outputs}")

    @handle_exception
    def set_wall_mode_off(self, output_id_start, output_id_end):
        self._send(f"OWO{output_id_start:03d}-{output_id_end:03d}M00")

    @handle_exception
    def set_wall_bezel(self, output_id, hdiv, vdiv, output_id_end=None):
        self._send(f"OB{self._port_range(output_id, output_id_end)}H{hdiv:02d}V{vdiv:02d}")

    @handle_exception
    def reset_output(self, output_id):
        self._send(f"ORO{output_id:03d}")

    @handle_exception
    def set_output_cec_power(self, output_id, on: bool, output_id_end=None):
        self._send(f"OC{self._port_range(output_id, output_id_end)}M{'01' if on else '00'}")

    @handle_exception
    def send_output_cec_stream(self, output_id, hex_data: str, output_id_end=None):
        """hex_data: CEC 스트림 HEX 문자열 (예: "FE8210F0")"""
        self._send(f'OC{self._port_range(output_id, output_id_end)}S"{hex_data}"')

    @handle_exception
    def set_output_volume(self, output_id, volume, output_id_end=None):
        """volume: 10~70 (0.5dB step, 50=0dB, 70=+10dB, 10=Mute)"""
        self._send(f"OA{self._port_range(output_id, output_id_end)}V{volume:02d}")

    @handle_exception
    def get_output_volume(self, output_id=0):
        """output_id: 0(all)~max_outputs"""
        self._send(f"?OAO{output_id:03d}V")

    # ------------------------------------------------------------------ #
    # Firmware
    # ------------------------------------------------------------------ #
    @handle_exception
    def get_firmware_version(self):
        self._send("?version")
