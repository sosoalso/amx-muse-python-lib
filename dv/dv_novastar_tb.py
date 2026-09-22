# 마지막 수정일 : 20260713
"""
Novastar TB Series LED Multimedia Player
중앙 제어 프로토콜 (TCP, port 16603)

로그인 명령은 장치 SN/비밀번호 기반으로 계산되므로,
"T카드 로그인 프로토콜 계산.exe" 도구로 생성한 HEX 문자열을 login_hex 파라미터로 전달한다.
"""

import struct

from lib.event_manager import EventManager
from lib.network_manager import TcpClient
from lib.utility import CommonLogger, handle_exception


class NovastarTb(CommonLogger, EventManager):
    DEFAULT_PORT = 16603

    # ---------------------------------------------------------------------------- #
    # 페이지 전환: 문서에서 추출한 pre-computed 패킷 (field1이 command별로 고정값)
    _CMD_PAGE_LAST = bytes.fromhex("41564f4e4307000051521e00280700000a000000000078027b2274797065223a337d")
    _CMD_PAGE_PREV = bytes.fromhex("41564f4e4d07000051521e00280700000a000000000082027b2274797065223a307d")
    _CMD_PAGE_NEXT = bytes.fromhex("41564f4e5a07000051521e00280700000a00000000008f027b2274797065223a317d")
    _CMD_PAGE_HOME = bytes.fromhex("41564f4ea406000051521e00280700000a0000000000d8017b2274797065223a327d")

    # 음량 조절: 10% 단위 pre-computed 패킷 (0~90%)
    _CMD_VOLUME = {
        0: bytes.fromhex("41564f4ea507000051522600040000000b0000000000b8017b22726174696f223a307d"),
        10: bytes.fromhex("41564f4eab07000051522600040000000c0000000000bf017b22726174696f223a31307d"),
        20: bytes.fromhex("41564f4eb507000051522600040000000c0000000000c9017b22726174696f223a32307d"),
        30: bytes.fromhex("41564f4ebc07000051522600040000000c0000000000d0017b22726174696f223a33307d"),
        40: bytes.fromhex("41564f4ec207000051522600040000000c0000000000d6017b22726174696f223a34307d"),
        50: bytes.fromhex("41564f4ec807000051522600040000000c0000000000dc017b22726174696f223a35307d"),
        60: bytes.fromhex("41564f4ed007000051522600040000000c0000000000e4017b22726174696f223a36307d"),
        70: bytes.fromhex("41564f4ed607000051522600040000000c0000000000ea017b22726174696f223a37307d"),
        80: bytes.fromhex("41564f4edb07000051522600040000000c0000000000ef017b22726174696f223a38307d"),
        90: bytes.fromhex("41564f4ee207000051522600040000000c0000000000f6017b22726174696f223a39307d"),
    }

    # ---------------------------------------------------------------------------- #
    def __init__(self, ip: str, login_hex: str, port: int = DEFAULT_PORT):
        super().__init__("connected", "disconnected", "received")
        self.dv = TcpClient(ip, port, reconnect_time=10.0)
        self._login_cmd = bytes.fromhex(login_hex)
        self.name = f"{self.__class__.__name__.lower()}_{ip}"

    # ---------------------------------------------------------------------------- #
    @handle_exception
    def init(self):
        self.dv.receive.listen(self._on_receive)
        self.dv.on("connected", self._on_connected)
        self.dv.on("disconnected", lambda *args, **kwargs: self.emit("disconnected"))
        self.dv.connect()

    # ---------------------------------------------------------------------------- #
    # INFO : TX
    def _send(self, data: bytes):
        self.dv.send(data)
        self.log_debug(f"_send: {data.hex()}")

    def _on_connected(self, *args, **kwargs):
        self._send(self._login_cmd)
        self.emit("connected")

    @staticmethod
    def _build_packet(subcmd: int, payload: bytes = b"") -> bytes:
        """
        program play / play-control 공통 패킷 빌더.

        패킷 구조 (27 + payload bytes):
          [0:4]   AVON  magic header
          [4:8]   field1 = 2  (program/play 계열 고정값)
          [8:10]  0x51 0x52
          [10:12] cmd code = 0x001e (LE)
          [12:16] sub-command (LE uint32)
          [16:20] payload length (LE uint32)
          [20:25] 0x00 x5
          [25:27] checksum = sum([0:25]) as LE uint16
          [27:]   JSON payload
        """
        header = (
            b"AVON"
            + struct.pack("<I", 2)  # field1
            + b"\x51\x52"  # constant
            + struct.pack("<H", 0x001E)  # cmd code
            + struct.pack("<I", subcmd)  # sub-command
            + struct.pack("<I", len(payload))  # payload length
            + b"\x00" * 5  # padding
        )
        checksum = sum(header) & 0xFFFF
        return header + struct.pack("<H", checksum) + payload

    # ---------------------------------------------------------------------------- #
    # INFO : RX
    @handle_exception
    def _on_receive(self, evt):
        data = evt.arguments.get("data", b"")
        self.log_debug(f"_on_receive: {data}")
        # emit: received(data: bytes)
        self.emit("received", data=data)

    # ---------------------------------------------------------------------------- #
    # INFO : 프로그램 재생
    @handle_exception
    def play_program(self, name: str):
        """프로그램 이름 지정 재생 (예: "01", "02", ...)"""
        payload = f'{{"name":"{name}"}}'.encode("ascii")
        self._send(self._build_packet(0x00000409, payload))
        self.log_info(f"play_program: {name=}")

    # ---------------------------------------------------------------------------- #
    # INFO : 플레이 제어
    @handle_exception
    def pause(self):
        """재생 일시 정지"""
        self._send(self._build_packet(0x0000040C))
        self.log_info("pause")

    @handle_exception
    def resume(self):
        """재생 재개"""
        self._send(self._build_packet(0x0000040A))
        self.log_info("resume")

    @handle_exception
    def stop(self):
        """재생 중지"""
        self._send(self._build_packet(0x0000040B))
        self.log_info("stop")

    # ---------------------------------------------------------------------------- #
    # INFO : 페이지 전환
    @handle_exception
    def page_home(self):
        """홈 페이지"""
        self._send(self._CMD_PAGE_HOME)
        self.log_info("page_home")

    @handle_exception
    def page_next(self):
        """다음 페이지"""
        self._send(self._CMD_PAGE_NEXT)
        self.log_info("page_next")

    @handle_exception
    def page_prev(self):
        """이전 페이지"""
        self._send(self._CMD_PAGE_PREV)
        self.log_info("page_prev")

    @handle_exception
    def page_last(self):
        """마지막 페이지"""
        self._send(self._CMD_PAGE_LAST)
        self.log_info("page_last")

    # ---------------------------------------------------------------------------- #
    # INFO : 음량 조절
    @handle_exception
    def set_volume(self, percent: int):
        """음량 설정 (0~100). 10% 단위로 반올림, 최대 90%."""
        level = round(percent / 10) * 10
        level = max(0, min(90, level))
        self._send(self._CMD_VOLUME[level])
        self.log_info(f"set_volume: {percent=} → level={level}")
