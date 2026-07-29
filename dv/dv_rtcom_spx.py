# 마지막 수정일 : 20260713
"""RTCOM SPX 시리즈 (M810 / M1620 / M3236 / M2472 / M24120) HDMI 2.0 4K 매트릭스 스위처 제어.

TCP/IP (Telnet, 기본 23번 포트) ASCII 커맨드 프로토콜 기준 (매뉴얼 § 7 Control Command vol.2).
모든 커맨드는 "!\\r\\n" 로 끝나며, 응답도 동일한 방식의 ASCII 텍스트로 온다.
SPX-M1620 기준 기본값은 입력 16 (HIS8 x2), 출력 20 (HOS10 x2) 이다.
HOS12/COS12 카드 구성(출력 24) 등 다른 프레임/카드 조합을 쓰면 max_inputs/max_outputs 를 맞춰서 넘긴다.
"""

import re

from lib.event_manager import EventManager
from lib.network_manager import DEFAULT_TCP_CLIENT_RECONNECT_TIME, TcpClient
from lib.utility import CommonLogger, handle_exception


class RtcomSpx(CommonLogger, EventManager):
    DEFAULT_PORT = 23

    # 7.5/7.8/7.12 출력 해상도 코드 (Wall/Quadview/Scaler 공용 테이블)
    RESOLUTION_AUTO = 1
    RESOLUTION_720X480P60 = 2
    RESOLUTION_720X576P50 = 3
    RESOLUTION_1280X720P50 = 4
    RESOLUTION_1280X720P59 = 5
    RESOLUTION_1280X720P60 = 6
    RESOLUTION_1920X1080P50 = 7
    RESOLUTION_1920X1080P59 = 8
    RESOLUTION_1920X1080P60 = 9
    RESOLUTION_3840X2160P30 = 10
    RESOLUTION_3840X2160P50 = 11
    RESOLUTION_3840X2160P59 = 12
    RESOLUTION_3840X2160P60 = 13
    RESOLUTION_1024X768P60 = 14
    RESOLUTION_1280X1024P60 = 15
    RESOLUTION_1920X1200P60 = 16

    def __init__(self, dv, max_inputs=16, max_outputs=20, reconnect_time=DEFAULT_TCP_CLIENT_RECONNECT_TIME):
        super().__init__("received", "route", "link_in", "link_out")
        self.dv = dv
        self.max_inputs = max_inputs
        self.max_outputs = max_outputs
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.routes = {output_id: 0 for output_id in range(1, self.max_outputs + 1)}
        self._buf = ""

    @handle_exception
    def init(self):
        self.dv.receive.listen(self.parse_response)

    def _next_line(self):
        idx = self._buf.find("\r")
        if idx < 0:
            return None
        line, self._buf = self._buf[:idx], self._buf[idx + 1 :]
        return line

    @handle_exception
    def _send(self, cmd: str):
        self.dv.send(f"{cmd}!\r\n".encode())
        self.log_debug(f"_send() : cmd={cmd}!")

    @handle_exception
    def get_route_value(self, output_id) -> int:
        return self.routes.get(output_id, 0)

    @handle_exception
    def parse_response(self, evt):
        data = evt.arguments.get("data", b"")
        if not data:
            self.log_error(f"parse_response() : {evt=}")
            return
        try:
            self._buf += data.decode("utf-8", "ignore")
        except (AttributeError, UnicodeDecodeError) as e:
            self.log_error(f"parse_response() decode error {e=}")
            return
        self.log_debug(f"parse_response() : buf={self._buf!r}")
        while True:
            line = self._next_line()
            if line is None:
                return
            line = line.strip()
            if not line:
                continue
            route_match = re.match(r"input\s*(\d+)\s*->\s*output\s*(\d+)", line, re.IGNORECASE)
            if route_match:
                input_id, output_id = int(route_match.group(1)), int(route_match.group(2))
                if output_id in self.routes:
                    self.routes[output_id] = input_id
                    # emit: route(idx_in: int, idx_out: int)
                    self.emit("route", idx_in=input_id, idx_out=output_id)
            else:
                link_match = re.match(r"hdmi\s+(input|output)\s*(\d+)\s*:\s*(connect|disconnect)", line, re.IGNORECASE)
                if link_match:
                    direction, port_id, status = link_match.group(1).lower(), int(link_match.group(2)), link_match.group(3).lower()
                    # emit: link_in/link_out(port_id: int, connected: bool)
                    self.emit("link_in" if direction == "input" else "link_out", port_id=port_id, connected=status == "connect")
            # emit: received(text: str)
            self.emit("received", text=line)

    # ------------------------------------------------------------------ #
    # 7.1 System Setup Command
    # ------------------------------------------------------------------ #
    @handle_exception
    def reboot(self):
        self._send("s reboot")

    @handle_exception
    def reset_factory(self):
        self._send("s reset")

    @handle_exception
    def get_type(self):
        self._send("r type")

    @handle_exception
    def get_fw_version(self):
        self._send("r fw version")

    @handle_exception
    def get_input_link_status(self, input_id=0):
        """input_id: 0(all)~max_inputs"""
        self._send(f"r link in {input_id}")

    @handle_exception
    def get_output_link_status(self, output_id=0):
        """output_id: 0(all)~max_outputs"""
        self._send(f"r link out {output_id}")

    @handle_exception
    def get_ip_config(self):
        self._send("r ipconfig")

    @handle_exception
    def get_mac_address(self):
        self._send("r mac addr")

    @handle_exception
    def get_ip_mode(self):
        self._send("r ip mode")

    @handle_exception
    def get_ip_address(self):
        self._send("r ip addr")

    @handle_exception
    def get_subnet_mask(self):
        self._send("r subnet")

    @handle_exception
    def get_gateway(self):
        self._send("r gateway")

    @handle_exception
    def get_tcp_port(self):
        self._send("r tcp/ip port")

    @handle_exception
    def get_telnet_port(self):
        self._send("r telnet port")

    @handle_exception
    def get_connect_status(self):
        self._send("r connect")

    # ------------------------------------------------------------------ #
    # 7.2 Preset Command
    # ------------------------------------------------------------------ #
    @handle_exception
    def save_preset(self, preset_id):
        """preset_id: 1~8"""
        self._send(f"s save preset {preset_id}")

    @handle_exception
    def recall_preset(self, preset_id):
        self._send(f"s recall preset {preset_id}")

    @handle_exception
    def clear_preset(self, preset_id):
        self._send(f"s clear preset {preset_id}")

    @handle_exception
    def get_preset(self, preset_id):
        self._send(f"r preset {preset_id}")

    # ------------------------------------------------------------------ #
    # 7.3 Output Setting Command
    # ------------------------------------------------------------------ #
    @handle_exception
    def switch(self, input_id, output_id=0):
        """input_id: 1~max_inputs, output_id: 0(all)~max_outputs"""
        self._send(f"s in {input_id} av out {output_id}")
        self.log_debug(f"switch() : {input_id=} {output_id=}")

    @handle_exception
    def get_route(self, output_id=0):
        self._send(f"r av out {output_id}")

    @handle_exception
    def set_output_stream(self, output_id, enable: bool):
        """output_id: 0(all)~max_outputs"""
        self._send(f"s hdmi {output_id} stream{1 if enable else 0}")

    @handle_exception
    def get_output_stream(self, output_id=0):
        self._send(f"r hdmi {output_id} stream")

    # ------------------------------------------------------------------ #
    # 7.4 EDID Setting Command
    # ------------------------------------------------------------------ #
    @handle_exception
    def set_edid(self, input_id, edid_id):
        """input_id: 0(all)~max_inputs, edid_id: 1~39 (매뉴얼 § 7.4 EDID 목록 참조)"""
        self._send(f"s edid in {input_id} from {edid_id}")

    @handle_exception
    def get_edid(self, input_id=0):
        self._send(f"r edid in {input_id}")

    @handle_exception
    def get_edid_data(self, output_id):
        self._send(f"r edid data hdmi{output_id}")

    # ------------------------------------------------------------------ #
    # 7.5~7.7 Video Wall Command
    # ------------------------------------------------------------------ #
    @handle_exception
    def create_wall(self, wall_id, hdiv, vdiv, resolution_id, start_output_id):
        """wall_id: 1~30, hdiv/vdiv: 가로/세로 분할 수, start_output_id: 슬롯의 1/5/9번 출력"""
        self._send(f"s wall {wall_id} hdiv {hdiv} vdiv {vdiv} time {resolution_id} out {start_output_id}")

    @handle_exception
    def switch_wall(self, input_id, wall_id):
        self._send(f"s in {input_id} wall out {wall_id}")

    @handle_exception
    def wall_off(self, wall_id):
        self._send(f"s wall {wall_id} off")

    # ------------------------------------------------------------------ #
    # 7.8~7.9 Quadview Command
    # ------------------------------------------------------------------ #
    @handle_exception
    def quadview_on(self, layer_id, resolution_id, start_output_id):
        """layer_id: 1~3, start_output_id: 슬롯의 1/5/9번 출력"""
        self._send(f"s quad on layer {layer_id} time {resolution_id} out {start_output_id}")

    @handle_exception
    def quadview_off(self, output_id):
        self._send(f"s quad off out {output_id}")

    # ------------------------------------------------------------------ #
    # 7.10~7.11 CEC Command
    # ------------------------------------------------------------------ #
    @handle_exception
    def set_cec_power(self, output_id, on: bool):
        """output_id: 0(all)~max_outputs"""
        self._send(f"s cec hdmi out {output_id} {'on' if on else 'off'}")

    @handle_exception
    def send_cec_custom(self, output_id, *data_bytes: str):
        """output_id: 0(all)~max_outputs, data_bytes: HEX 문자열 (예: "ef", "82", "10", "00")"""
        self._send(f"s cec send out {output_id} cmd {' '.join(data_bytes)}")

    # ------------------------------------------------------------------ #
    # 7.12~7.16 Output Scaler Command
    # ------------------------------------------------------------------ #
    @handle_exception
    def set_output_resolution(self, output_id, resolution_id):
        """output_id: 0(all)~max_outputs"""
        self._send(f"s hdmi {output_id} scaler {resolution_id}")

    @handle_exception
    def set_output_contrast(self, output_id, value):
        """value: 0~255, default 128"""
        self._send(f"s hdmi {output_id} con {value}")

    @handle_exception
    def set_output_brightness(self, output_id, value):
        """value: 0~255, default 128"""
        self._send(f"s hdmi {output_id} bri {value}")

    @handle_exception
    def set_output_saturation(self, output_id, value):
        """value: 0~255, default 128"""
        self._send(f"s hdmi {output_id} sat {value}")

    @handle_exception
    def set_output_hue(self, output_id, value):
        """value: 0~255, default 128"""
        self._send(f"s hdmi {output_id} hue {value}")
