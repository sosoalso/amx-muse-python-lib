# 마지막 수정일 : 20260629
from lib.event_manager import EventManager
from lib.userdata import Userdata
from lib.utility import CommonLogger, handle_exception


# SECTION - 제어 장비
class BrsU808m(CommonLogger, EventManager):
    def __init__(self, dv, name):
        super().__init__("route", "routes")
        self.dv = dv
        self.name = name
        self.userdata = Userdata(f"{self.name}_routes.json", default_value={key: 0 for key in range(1, 8)})
        self.routes =

    @handle_exception
    def init(self):
        self.dv.receive.listen(self.parse_response)

    @handle_exception
    def vidmtx_send(self, cmd: int, body: bytearray):
        msg = bytearray([0x7B, 0x7B, cmd, len(body)])
        msg += body
        # msg.append((sum(msg) + 0xFA) % 256)
        msg += bytearray([(sum(msg) + 0xFA) % 256])
        msg += bytearray([0x7D, 0x7D])
        self.dv.send(msg)

    @handle_exception
    def set_route(self, idx_in, idx_out):
        self.log_info(f"set_route() {idx_in=} {idx_out=}")
        if idx_in < 1 or idx_in > 8 or idx_out < 1 or idx_out > 8:
            return
        if self.userdata.get_value(idx_out, 0) == idx_in:
            return
        flag_in = idx_in - 1
        flag_out = 1 << (idx_out - 1)
        self.vidmtx_send(0x01, bytearray([flag_in, flag_out]))
        self.userdata.set_value(idx_out, idx_in)
        # emit: route(idx_in: int, idx_out: int)
        self.emit("route", idx_in=idx_in, idx_out=idx_out)

    @handle_exception
    def set_routes(self, idx_in, idx_outs):
        self.log_info(f"set_routes()     {idx_in=} {idx_outs=}")
        if idx_in < 1 or idx_in > 8 or not all(1 <= idx_out <= 8 for idx_out in idx_outs):
            return
        flag_in = idx_in - 1
        flags_out = 0
        for idx_out in idx_outs:
            if self.userdata.get_value(idx_out, 0) != idx_in:
                flags_out |= 1 << (idx_out - 1)
            self.userdata.set_value(idx_out, idx_in if idx_out in idx_outs else 0)
        self.vidmtx_send(0x01, bytearray([flag_in, flags_out]))
        # emit: routes(idx_in: int, idx_outs: list[int])
        self.emit("routes", idx_in=idx_in, idx_outs=idx_outs)

    def parse_response(self, *args):
        pass
