import re

# from config import SCUIMXER, TP_LIST, TP_PORT_SCUI
from mojo import context

# from lib.button import add_btn_ss
from lib.eventmanager import EventManager

# from lib.lib_tp import tp_send_lvl_ss, tp_set_btn_ss, tp_set_btn_txt_ss
# from lib.networkmanager import TcpClient
from lib.scheduler import Scheduler


# "MEDIA_PLAY\n"
# "MEDIA_STOP\n"
# "MEDIA_PAUSE\n"
# "MEDIA_PREV\n
# "MEDIA_NEXT\n"
# "MEDIA_SWITCH_TRACK^~all~^/{filename}\n"
# `SETD^p.0.mix^${speakerVolume}\n`
# "SETD^a.0.mute^0\n" // aux
# msg.payload = "LOADSNAPSHOT^Default^Demo\n\n"
class SCUiMxer(EventManager):
    def __init__(self, dv, ip):
        super().__init__()
        self.ip = ip
        self.dv = dv
        self.state = {}
        self.media_status = "STOP"
        self.media_file_name = ""
        self.heartbeat: Scheduler | None = None
        self.init()

    def init(self):
        self.dv.receive.listen(self.parse_response)

        def delayed_init():
            sch = Scheduler()
            sch.set_timeout(lambda: self.send("GET /raw HTTP1.1\r\n"), 1.0)

        self.dv.online(delayed_init)
        self.heartbeat = Scheduler(name=f"SCUiMxer-{self.ip}-Heartbeat")
        self.heartbeat.set_interval(self.ping, 10.0)

    def send(self, msg: str):
        self.dv.send(f"{msg}\r\n".encode())

    def send_params(self, address: str, v: int | float | str):
        self.send(f"SETD^{address}^{v}")

    def ping(self):
        if self.dv.is_connected():
            self.send("ALIVE")

    def media_play(self):
        self.send("MEDIA_PLAY")
        self.media_status = "PLAY"

    def media_stop(self):
        self.send("MEDIA_STOP")
        self.media_status = "STOP"

    def media_pause(self):
        self.send("MEDIA_PAUSE")
        self.media_status = "PAUSE"

    def media_prev(self):
        self.send("MEDIA_PREV")

    def media_next(self):
        self.send("MEDIA_NEXT")

    def media_switch_track(self, filename: str):
        self.send(f"MEDIA_SWITCH_TRACK^~all~^{filename}")
        self.media_file_name = filename

    # ---------------------------------------------------------------------------- #
    # i.0
    # a.0
    # p.0
    # m 마스터
    # SETD^i.0.mix^1.0 // 0~100 /100 float
    # SETD^i.0.mute^1
    # ---------------------------------------------------------------------------- #
    def set_mute(self, address, v: int):
        if v not in (0, 1):
            return
        self.state[address + ".mute"] = v
        self.send_params(address + ".mute", v)
        self.emit(f"{address}.mute", value=v)

    def toggle_mute(self, address):
        current = self.state.get(address + ".mute", 0)
        new_value = 0 if current == 1 else 1
        self.set_mute(address, new_value)

    def set_volume(self, address, v: int):
        if v < 0 or v > 100:
            return
        f = float(v) / 100.0
        context.log.debug(f"set_volume {address=} {v=} {f=}")
        self.state[address + ".mix"] = v
        self.send_params(address + ".mix", f)
        self.emit(f"{address}.mix", value=v)

    def set_input_mute(self, idx: int, v: int):
        self.set_mute(f"i.{idx}", v)

    def toggle_input_mute(self, idx: int):
        self.toggle_mute(f"i.{idx}")

    def set_aux_mute(self, idx: int, v: int):
        self.set_mute(f"a.{idx}", v)

    def toggle_aux_mute(self, idx: int):
        self.toggle_mute(f"a.{idx}")

    def set_master_mute(self, v: int):
        self.set_mute("m", v)

    def toggle_master_mute(self):
        self.toggle_mute("m")

    def set_input_volume(self, idx: int, v: int):
        self.set_volume(f"i.{idx}", v)

    def set_aux_volume(self, idx: int, v: int):
        self.set_volume(f"a.{idx}", v)

    def set_master_volume(self, v: int):
        self.set_volume("m", v)

    # ---------------------------------------------------------------------------- #
    def get_input_mute(self, idx: int) -> int:
        return int(self.state.get(f"i.{idx}.mute", -1))

    def get_aux_mute(self, idx: int) -> int:
        return int(self.state.get(f"a.{idx}.mute", -1))

    def get_master_mute(self) -> int:
        return int(self.state.get("m.mute", -1))

    def get_input_volume(self, idx: int) -> int:
        # context.log.debug(f"get_input_volume {idx=} {self.state.get(f'i.{idx}.mix')=}")
        return int(self.state.get(f"i.{idx}.mix", -1))

    def get_aux_volume(self, idx: int) -> int:
        return int(self.state.get(f"a.{idx}.mix", -1))

    def get_master_volume(self) -> int:
        return int(self.state.get("m.mix", -1))

    # ---------------------------------------------------------------------------- #
    def parse_response(self, evt):
        data_text = evt.arguments["data"].decode()

        def iter_lines(text: str):
            line = []
            for ch in text:
                if ch in ("\n", "\r", "\u2028", "\u2029", "\u0085"):
                    yield "".join(line)
                    line = []
                    if ch == "\r":
                        continue
                else:
                    line.append(ch)
            if line:
                yield "".join(line)

        for line in iter_lines(data_text):
            match = re.search(r"SETD\^(.+?)\^(.+)", line)
            if match:
                address = match.group(1)
                value = match.group(2)
                # ---------------------------------------------------------------------------- #
                if address.startswith("RTA^") or address.startswith("VU2^"):
                    continue
                if not address.startswith(("i.")) and not address.startswith(("a.")) and not address.startswith(("m")):
                    continue
                # ---------------------------------------------------------------------------- #
                if address.endswith(".mix"):
                    try:
                        value = int(float(value) * 100)
                        context.log.debug(f"address find value * 100 ! {address=}, {value=}")
                    except ValueError:
                        continue
                elif address.endswith(".mute"):
                    try:
                        value = int(value)
                    except ValueError:
                        continue
                else:
                    continue
                self.state[address] = value
                self.emit(f"{address}", value=self.state[address])

                context.log.debug(f"parse_response {address=}, Value: {self.state[address]=}")

    # ---------------------------------------------------------------------------- #


ENUM_SCUI_INT_DB = {
    0: -100.0,
    1: -80.0,
    2: -72.0,
    3: -67.0,
    4: -64.0,
    5: -61.0,
    6: -59.0,
    7: -57.0,
    8: -56.0,
    9: -54.0,
    10: -52.0,
    11: -51.0,
    12: -49.0,
    13: -48.0,
    14: -46.0,
    15: -45.0,
    16: -43.0,
    17: -42.0,
    18: -40.0,
    19: -39.0,
    20: -38.0,
    21: -36.0,
    22: -35.0,
    23: -34.0,
    24: -33.0,
    25: -32.0,
    26: -30.0,
    27: -29.0,
    28: -28.0,
    29: -27.0,
    30: -26.0,
    31: -25.0,
    32: -24.0,
    33: -23.0,
    34: -23.0,
    35: -22.0,
    36: -21.0,
    37: -20.0,
    38: -19.6,
    39: -18.8,
    40: -18.1,
    41: -17.3,
    42: -16.6,
    43: -15.9,
    44: -15.2,
    45: -14.6,
    46: -13.9,
    47: -13.3,
    48: -12.7,
    49: -12.1,
    50: -11.5,
    51: -11.0,
    52: -10.4,
    53: -9.9,
    54: -9.4,
    55: -8.8,
    56: -8.3,
    57: -7.9,
    58: -7.4,
    59: -6.9,
    60: -6.5,
    61: -6.0,
    62: -5.6,
    63: -5.2,
    64: -4.7,
    65: -4.3,
    66: -3.9,
    67: -3.5,
    68: -3.1,
    69: -2.7,
    70: -2.3,
    71: -2.0,
    72: -1.6,
    73: -1.2,
    74: -0.8,
    75: -0.5,
    76: -0.1,
    77: 0.2,
    78: 0.6,
    79: 0.9,
    80: 1.3,
    81: 1.7,
    82: 2.1,
    83: 2.5,
    84: 2.8,
    85: 3.2,
    86: 3.6,
    87: 4.0,
    88: 4.4,
    89: 4.9,
    90: 5.3,
    91: 5.7,
    92: 6.1,
    93: 6.6,
    94: 7.0,
    95: 7.5,
    96: 8.0,
    97: 8.5,
    98: 9.0,
    99: 9.5,
    100: 10.0,
}

# ---------------------------------------------------------------------------- #
# scuimixer_instance = SCUiMxer(dv=SCUIMXER, ip="192.168.0.99")


# scuimixer_instance.dv.debug = True
# # ---------------------------------------------------------------------------- #
# def add_tp_scuimixer():
#     def vol_up_input(idx):
#         try:
#             cur_value = int(scuimixer_instance.get_input_volume(idx))
#             new_value = 76 if cur_value == -1 else min(100, cur_value + 1)
#             # ---------------------------------------------------------------------------- #
#             scuimixer_instance.set_input_volume(idx, new_value)
#             if idx == 6:
#                 scuimixer_instance.set_input_volume(7, new_value)
#             elif idx == 8:
#                 scuimixer_instance.set_input_volume(9, new_value)
#             elif idx == 10:
#                 scuimixer_instance.set_input_volume(11, new_value)
#             # ---------------------------------------------------------------------------- #
#         except Exception as e:
#             print(f"add_tp_scui vol_up_input {idx=} {e=}")

#     def vol_down_input(idx):
#         try:
#             cur_value = scuimixer_instance.get_input_volume(idx)
#             new_value = 76 if cur_value == -1 else max(0, cur_value - 1)
#             # ---------------------------------------------------------------------------- #
#             scuimixer_instance.set_input_volume(idx, new_value)
#             if idx == 6:
#                 scuimixer_instance.set_input_volume(7, new_value)
#             elif idx == 8:
#                 scuimixer_instance.set_input_volume(9, new_value)
#             elif idx == 10:
#                 scuimixer_instance.set_input_volume(11, new_value)
#         except Exception as e:
#             print(f"add_tp_scui vol_down_input {idx=} {e=}")

#     def toggle_mute_input(idx):
#         try:
#             scuimixer_instance.toggle_input_mute(idx)
#             if idx == 6:
#                 scuimixer_instance.toggle_input_mute(7)
#             elif idx == 8:
#                 scuimixer_instance.toggle_input_mute(9)
#             elif idx == 10:
#                 scuimixer_instance.toggle_input_mute(11)
#         except Exception as e:
#             print(f"add_tp_scui toggle_mute_input {idx=} {e=}")

#     for idx, btn in enumerate(range(101, 112 + 1)):
#         add_btn_ss(TP_LIST, TP_PORT_SCUI, btn, "repeat_0.2", lambda idx=idx: toggle_mute_input(idx))
#     for idx, btn in enumerate(range(201, 212 + 1)):
#         add_btn_ss(TP_LIST, TP_PORT_SCUI, btn, "repeat_0.2", lambda idx=idx: vol_up_input(idx))
#     for idx, btn in enumerate(range(301, 312 + 1)):
#         add_btn_ss(TP_LIST, TP_PORT_SCUI, btn, "repeat_0.2", lambda idx=idx: vol_down_input(idx))


# # ---------------------------------------------------------------------------- #
# def add_evt_scuimixer():
#     def refresh_tp_vol_by_input_idx(idx, *args, **kwargs):
#         try:
#             cur_value = scuimixer_instance.get_input_volume(idx)
#             tp_send_lvl_ss(TP_LIST, TP_PORT_SCUI, 101 + idx, cur_value)
#             tp_set_btn_txt_ss(TP_LIST, TP_PORT_SCUI, 101 + idx, f"{ENUM_SCUI_INT_DB.get(cur_value, 'NaN')} dB")
#         except Exception as e:
#             context.log.error(f"add_evt_scui refresh_tp_vol_by_input_idx {idx=} {e=}")

#     def refresh_tp_mute_button_by_input_idx(idx, *args, **kwargs):
#         try:
#             cur_value = scuimixer_instance.get_input_mute(idx)
#             tp_set_btn_ss(TP_LIST, TP_PORT_SCUI, 101 + idx, cur_value == 1)
#         except Exception as e:
#             context.log.error(f"add_evt_scui refresh_tp_mute_button_by_input_idx {idx=} {e=}")

#     for idx in range(0, 12 + 1):
#         scuimixer_instance.on(f"i.{idx}.mix", lambda idx=idx, **kwargs: refresh_tp_vol_by_input_idx(idx))
#         scuimixer_instance.on(f"i.{idx}.mute", lambda idx=idx, **kwargs: refresh_tp_mute_button_by_input_idx(idx))
