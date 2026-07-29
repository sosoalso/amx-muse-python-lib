# 마지막 수정일 : 20260713
import json

from lib.event_manager import EventManager
from lib.network_manager import DEFAULT_TCP_CLIENT_RECONNECT_TIME, TcpClient
from lib.utility import CommonLogger, handle_exception


class DCernoCur(CommonLogger, EventManager):
    DEFAULT_PORT = 5011

    MIC_OFF = 0
    MIC_ON = 1
    MIC_REQUEST = 2
    MIC_TOGGLE = 3

    def __init__(self, ip, port=DEFAULT_PORT, reconnect_time=DEFAULT_TCP_CLIENT_RECONNECT_TIME):
        super().__init__(
            "mic_changed",
            "mic_on",
            "mic_off",
            "mic_request",
            "mic_error",
            "unit_presence",
            "connected",
            "disconnected",
        )
        self.dv = TcpClient(ip, port, reconnect_time=reconnect_time)
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.buffer = b""
        self.state = {}
        self._packet_id = 0
        self._pending_bodies = {}

    @handle_exception
    def init(self):
        self.dv.on("connected", self._on_connected)
        self.dv.on("disconnected", lambda: self.emit("disconnected"))
        self.dv.on("received", lambda evt: self._on_receive(evt.arguments.get("data", b"")))
        self.dv.connect()

    @handle_exception
    def set_mic(self, uid, enable: bool):
        self.set_mic_status(uid, self.MIC_ON if enable else self.MIC_OFF)

    @handle_exception
    def mic_on(self, uid):
        self.set_mic_status(uid, self.MIC_ON)

    @handle_exception
    def mic_off(self, uid):
        self.set_mic_status(uid, self.MIC_OFF)

    @handle_exception
    def toggle_mic(self, uid):
        self.set_mic_status(uid, self.MIC_TOGGLE)

    @handle_exception
    def all_mic_off(self):
        self.set_mic_status("0", self.MIC_OFF)

    @handle_exception
    def get_mic_status(self, uid="0"):
        self._send("get", {"nam": "gmicstat", "uid": str(uid)})

    @handle_exception
    def get_all_units(self):
        self._send("get", {"nam": "gunits"})

    @handle_exception
    def set_mic_status(self, uid, status: int):
        if status not in (self.MIC_OFF, self.MIC_ON, self.MIC_REQUEST, self.MIC_TOGGLE):
            raise ValueError(f"invalid microphone status: {status}")
        if str(uid) == "0" and status != self.MIC_OFF:
            raise ValueError("uid=0 only supports MIC_OFF")
        self._send("set", {"nam": "smicstat", "uid": str(uid), "stat": str(status)})

    def _on_connected(self):
        self.emit("connected")
        self._connect_tccp()
        self.get_all_units()

    def _connect_tccp(self):
        self._send_packet("con", '\n{ \n"typ":"Application", \n"nam":"DU", \n"ver":"1.01", \n"inf":"", \n"svr":0, \n"tim":"" \n}', qos="0")

    def _send(self, packet_type: str, body: dict):
        self._send_packet(packet_type, json.dumps(body, separators=(",", ":")), qos="9")

    def _send_packet(self, packet_type: str, body: str | None, qos: str):
        packet_id = self._next_packet_id()
        payload = body or ""
        msg = f"\x0202:{packet_type}{packet_id:04d}02{qos}O00000C00000000000000:{payload}\x03"
        self.log_debug(f"_send_packet() {msg=}")
        self.dv.send(msg)

    def _next_packet_id(self) -> int:
        packet_id = self._packet_id
        self._packet_id = (self._packet_id + 1) % 10000
        return packet_id

    def _on_receive(self, data):
        if isinstance(data, str):
            data = data.encode()
        self.buffer += data

        while True:
            start = self.buffer.find(b"\x02")
            if start < 0:
                self.buffer = b""
                return
            end = self.buffer.find(b"\x03", start + 1)
            if end < 0:
                self.buffer = self.buffer[start:]
                return

            packet = self.buffer[start + 1 : end]
            self.buffer = self.buffer[end + 1 :]
            self._parse_packet(packet)

    def _parse_packet(self, packet: bytes):
        text = packet.decode("utf-8", errors="ignore")
        self.log_debug(f"_parse_packet() {text=}")

        try:
            _, header, body = text.split(":", 2)
        except ValueError:
            return

        packet_type = header[:3]
        if packet_type not in ("evt", "rep"):
            return
        if not body:
            return

        packet_key = header[3:7]
        full_body = self._pending_bodies.pop(packet_key, "") + body

        try:
            payload = json.loads(full_body)
        except json.JSONDecodeError as e:
            # 큰 응답(예: gunits)은 장비가 같은 packet_id로 여러 프레임에 나눠 보낼 수 있어서, 파싱 실패 시 (불완전한 JSON 코드가 들어올 테니 JSONDecodeError 발생) 다음 프레임과 이어붙여 재시도한다.
            self._pending_bodies[packet_key] = full_body
            self.log_debug(f"_parse_packet() incomplete json, waiting for more data {packet_key=} {e=}")
            return

        name = payload.get("nam")
        if name == "micstat":
            self._handle_mic_status(payload)
        elif name == "units":
            self._handle_units(payload)
        elif name == "unit":
            uid = str(payload.get("uid", "")).upper()
            presence = payload.get("pres")
            self.emit("unit_presence", uid=uid, presence=presence)
        elif name == "err":
            error_id = payload.get("id")
            self.emit("mic_error", id=error_id)

    def _handle_units(self, payload: dict):
        units = payload.get("s") or payload.get("units") or []
        if not isinstance(units, list):
            return
        for unit in units:
            if isinstance(unit, dict):
                self._handle_mic_status(unit)

    def _handle_mic_status(self, payload: dict):
        uid = str(payload.get("uid", "")).upper()
        if not uid:
            return

        try:
            status = int(payload.get("stat", -1))
        except (TypeError, ValueError):
            return

        self.state[uid] = status
        value = status == self.MIC_ON
        self.emit("mic_changed", uid=uid, status=status, value=value)

        if status == self.MIC_ON:
            self.emit("mic_on", uid=uid)
        elif status == self.MIC_OFF:
            self.emit("mic_off", uid=uid)
        elif status == self.MIC_REQUEST:
            self.emit("mic_request", uid=uid)
