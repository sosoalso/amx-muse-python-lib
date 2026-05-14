# 마지막 수정일 : 20260511
from lib.event_manager import EventManager
from lib.network_manager import TcpClient
from lib.utility import CommonLogger, handle_exception
from lib.network_manager import TcpClient


class PanaVidswt(CommonLogger, EventManager):
    DEFAULT_PORT = 62000

    # AXI active mapping (1-based index)
    SRC_NAME_IN_01 = "01"
    SRC_NAME_IN_02 = "02"
    SRC_NAME_IN_03 = "03"
    SRC_NAME_IN_04 = "04"
    SRC_NAME_IN_05 = "05"
    SRC_NAME_IN_06 = "06"
    SRC_NAME_IN_07 = "07"
    SRC_NAME_IN_08 = "08"
    SRC_NAME_AUX_01 = "227"
    SRC_NAME_AUX_02 = "228"
    SRC_NAME_AUX_03 = "229"
    SRC_NAME_AUX_04 = "230"
    SRC_NAME_PVW = "02"
    SRC_NAME_PGM = "01"

    SRC_NAME = {
        "IN_01": SRC_NAME_IN_01,
        "IN_02": SRC_NAME_IN_02,
        "IN_03": SRC_NAME_IN_03,
        "IN_04": SRC_NAME_IN_04,
        "IN_05": SRC_NAME_IN_05,
        "IN_06": SRC_NAME_IN_06,
        "IN_07": SRC_NAME_IN_07,
        "IN_08": SRC_NAME_IN_08,
        "AUX_01": SRC_NAME_AUX_01,
        "AUX_02": SRC_NAME_AUX_02,
        "AUX_03": SRC_NAME_AUX_03,
        "AUX_04": SRC_NAME_AUX_04,
        "PVW": SRC_NAME_PVW,
        "PGM": SRC_NAME_PGM,
    }

    DEST_NAME_AUX1 = "113"
    DEST_NAME_AUX2 = "114"
    DEST_NAME_AUX3 = "115"
    DEST_NAME_AUX4 = "116"
    DEST_NAME_ME1PVW = "03"
    DEST_NAME_ME1PGM = "01"

    DEST_NAME = {
        "AUX1": DEST_NAME_AUX1,
        "AUX2": DEST_NAME_AUX2,
        "AUX3": DEST_NAME_AUX3,
        "AUX4": DEST_NAME_AUX4,
        "PVW": DEST_NAME_ME1PVW,
        "PGM": DEST_NAME_ME1PGM,
    }

    CMD_SELECTBUS = "SBUS"
    CMD_CUT = "SCUT"
    CMD_AUTO_TRS = "SAUT"
    CMD_TRS_SRC_BKGD = "00"
    CMD_TRS_SRC_KEY1 = "01"
    CMD_TRS_SRC_KEY2 = "04"
    CMD_TRS_SRC_FTB = "06"
    CMD_TRS_SRC_DSK_1 = "07"
    CMD_TRS_SRC_DSK_2 = "08"

    CMD_SETAUTOTRANSITION = "SAUT"
    CMD_AUTOTR_PARAM_BKGD = "00"
    CMD_REPLY_BUS_STATUS = "ABUS"

    def __init__(self, ip, port=DEFAULT_PORT):
        super().__init__()
        self.dv = TcpClient(ip, port)
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.routes = [0] * (len(self.DEST_NAME) + 1)
        self.params: dict[str, str] = {}

    @handle_exception
    def init(self):
        self.dv.receive.listen(self.parse_response)
        # self.dv.connect() 얘는 한 번 보내고 끊는 애라 안해도 됨

    @handle_exception
    def _send_cmd(self, cmd: str):
        payload = f"\x02{cmd}\x03".encode("utf-8")
        self.dv.send(payload)
        self.log_debug(f"_send_cmd() : cmd={cmd}")

    @handle_exception
    def _source_name(self, src_name) -> str:
        if not src_name in self.SRC_NAME:
            raise ValueError(f"invalid source name: {src_name}")
        return self.SRC_NAME.get(src_name, "")

    @handle_exception
    def _dest_name(self, dest_name) -> str:
        if not dest_name in self.DEST_NAME:
            raise ValueError(f"invalid dest name: {dest_name}")
        return self.DEST_NAME.get(dest_name, "")

    @handle_exception
    def switch(self, src_name: str, dest_name: str):
        self._send_cmd(f"{self.CMD_SELECTBUS}:{self._dest_name(dest_name)}:{self._source_name(src_name)}")

    @handle_exception
    def auto_transition(self, src: str = CMD_TRS_SRC_BKGD, effect: str = "0", action: str = "0"):
        self._send_cmd(f"{self.CMD_AUTO_TRS}:{src}:{effect}:{action}")

    @handle_exception
    def cut(self, src: str = CMD_TRS_SRC_BKGD):
        self._send_cmd(f"{self.CMD_CUT}:{src}")

    @handle_exception
    def set_ftb(self, state: bool):
        action = "1" if state else "2"
        self._send_cmd(f"{self.CMD_SETAUTOTRANSITION}:{self.CMD_TRS_SRC_FTB}:0:{action}")

    @handle_exception
    def set_dsk(self, dsk: int, state: bool):
        if dsk == 1:
            src = self.CMD_TRS_SRC_DSK_1
        elif dsk == 2:
            src = self.CMD_TRS_SRC_DSK_2
        else:
            raise ValueError(f"invalid dsk channel: {dsk}")
        action = "1" if state else "2"
        self._send_cmd(f"{self.CMD_SETAUTOTRANSITION}:{src}:0:{action}")

    @handle_exception
    def _receive_response(self, *args) -> bytes | str | None:
        if not args:
            return None
        evt = args[0]
        if hasattr(evt, "arguments") and isinstance(evt.arguments, dict):
            return evt.arguments.get("data")
        return evt

    @handle_exception
    def _parse_route_from_abus(self, line: str) -> tuple[int, int] | None:
        line = line.strip().strip("\x02").strip("\x03")
        if not line:
            return None
        parts = line.split(":")
        if len(parts) < 3:
            return None
        if parts[0] != self.CMD_REPLY_BUS_STATUS:
            return None
        dest_name = parts[1].strip()
        src_name = parts[2].strip()
        idx_dest = 0
        idx_src = 0
        for i, dest in enumerate(self.DEST_NAME, start=1):
            if dest_name == dest:
                idx_dest = i
                break
        if idx_dest:
            for i, src in enumerate(self.SRC_NAME, start=1):
                if src_name == src:
                    idx_src = i
                    break
        if idx_dest and idx_src:
            return idx_dest, idx_src
        return None

    @handle_exception
    def parse_response(self, *args):
        raw_data = self._receive_response(*args)
        if raw_data is None:
            self.log_debug(f"{self.__class__.__name__} parse_response invalid payload: {args=}")
            return
        if isinstance(raw_data, bytes):
            text = raw_data.decode("utf-8", errors="ignore")
        else:
            text = str(raw_data)
        for line in text.splitlines():
            line = line.strip()
            route = self._parse_route_from_abus(line)
            if route:
                idx_dest, idx_src = route
                self.routes[idx_dest] = idx_src
                self.emit("route", idx_dest=idx_dest, idx_src=idx_src, routes=self.routes)
                continue
            if ":" in line:
                key, value = line.strip("\x02\x03").split(":", 1)
                self.params[key.strip()] = value.strip()
        self.emit("received", text=text)
