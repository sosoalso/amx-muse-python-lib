# 마지막 수정일 : 20260625
# PR-0808 8x8 HDMI 매트릭스 (TCP 포트 23, 시리얼)
import re

from lib.event_manager import EventManager
from lib.utility import CommonLogger, handle_exception


class Pr0808(CommonLogger, EventManager):
    DEFAULT_PORT = 23
    NUM_IN = 8
    NUM_OUT = 8

    def __init__(self, dv):
        super().__init__("route")
        self.dv = dv
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.routes = {i: 0 for i in range(1, self.NUM_OUT + 1)}
        self._buf = ""

    @handle_exception
    def init(self):
        self.dv.receive.listen(self._parse)

    def _next_line(self):
        idx = self._buf.find("\r\n>")
        if idx < 0:
            return None
        line, self._buf = self._buf[:idx], self._buf[idx + 3 :]
        return line

    @handle_exception
    def _parse(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"Received response is in an invalid format. {args=}")
            return
        try:
            self._buf += args[0].arguments["data"].decode("utf-8", "ignore")
        except (AttributeError, UnicodeDecodeError) as e:
            self.log_error(f"_parse() decode error {e=}")
            return
        self.log_debug(f"_parse() buf={self._buf!r}")
        while True:
            line = self._next_line()
            if line is None:
                return
            self.log_debug(f"_parse() line={line!r}")
            m = re.match(r"set switch video from input (\d+) for output (\d+)", line)
            if m:
                idx_in, idx_out = int(m.group(1)), int(m.group(2))
                self.routes[idx_out] = idx_in
                # emit: route(idx_in: int, idx_out: int, routes: dict)
                self.emit("route", idx_in=idx_in, idx_out=idx_out, routes=self.routes)
                continue
            m = re.match(r"set switch video from no input for output (\d+)", line)
            if m:
                idx_out = int(m.group(1))
                self.routes[idx_out] = 0
                # emit: route(idx_in: int, idx_out: int, routes: dict)
                self.emit("route", idx_in=0, idx_out=idx_out, routes=self.routes)

    @handle_exception
    def switch(self, idx_in: int, idx_out: int):
        """입력 idx_in 을 출력 idx_out 으로 라우팅 (1-based). 비디오+오디오"""
        self.dv.send(f"set switch CI{idx_in}O{idx_out}\r\n".encode())
        self.routes[idx_out] = idx_in
        # emit: route(idx_in: int, idx_out: int, routes: dict)
        self.emit("route", idx_in=idx_in, idx_out=idx_out, routes=self.routes)

    @handle_exception
    def switch_video(self, idx_in: int, idx_out: int):
        """입력 idx_in 을 출력 idx_out 으로 라우팅 (1-based). 비디오만"""
        self.dv.send(f"set switch VI{idx_in}O{idx_out}\r\n".encode())
        self.routes[idx_out] = idx_in
        # emit: route(idx_in: int, idx_out: int, routes: dict)
        self.emit("route", idx_in=idx_in, idx_out=idx_out, routes=self.routes)
