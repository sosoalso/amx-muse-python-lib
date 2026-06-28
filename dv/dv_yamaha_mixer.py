# 마지막 수정일 : 20260629
from lib.utility import handle_exception, CommonLogger
from lib.event_manager import EventManager
from lib.network_manager import TcpClient, DEFAULT_TCP_CLIENT_RECONNECT_TIME

YAMAHA_GAIN_LUT = [
    -6000,
    -5950,
    -5900,
    -5850,
    -5800,
    -5700,
    -5650,
    -5600,
    -5550,
    -5500,
    -5400,
    -5350,
    -5300,
    -5250,
    -5200,
    -5100,
    -5050,
    -5000,
    -4950,
    -4850,
    -4800,
    -4750,
    -4700,
    -4650,
    -4550,
    -4500,
    -4450,
    -4400,
    -4350,
    -4250,
    -4200,
    -4150,
    -4100,
    -4000,
    -3950,
    -3900,
    -3850,
    -3800,
    -3700,
    -3650,
    -3600,
    -3550,
    -3500,
    -3400,
    -3350,
    -3300,
    -3250,
    -3200,
    -3100,
    -3050,
    -3000,
    -2950,
    -2850,
    -2800,
    -2750,
    -2700,
    -2650,
    -2550,
    -2500,
    -2450,
    -2400,
    -2350,
    -2250,
    -2200,
    -2150,
    -2100,
    -2000,
    -1950,
    -1900,
    -1850,
    -1800,
    -1700,
    -1650,
    -1600,
    -1550,
    -1500,
    -1400,
    -1350,
    -1300,
    -1250,
    -1200,
    -1100,
    -1050,
    -1000,
    -950,
    -850,
    -800,
    -750,
    -700,
    -650,
    -550,
    -500,
    -450,
    -400,
    -350,
    -250,
    -200,
    -150,
    -100,
    0,
]
# Device network settings
# Command constants
YAMAHA_CMD_RES_OK = "OK"
YAMAHA_CMD_RES_OKM = "OKm"
YAMAHA_CMD_RES_NOTIFY = "NOTIFY"
YAMAHA_CMD_PREFIX = "MIXER:Current/"
YAMAHA_CMD_TYPE_GAIN = "Level"
YAMAHA_CMD_TYPE_MUTE = "On"
YAMAHA_CMD_SET = "set"
YAMAHACMD_GET = "get"
YAMAHA_CMD_LEVEL = "Level"
YAMAHA_CMD_MUTE = "Mute"
YAMAHA_CMD_INPUT = "InCh/Fader/"
YAMAHA_CMD_MIX = "Mix/Fader/"


class YamahaMixer(CommonLogger, EventManager):
    DEFAULT_PORT = 49280

    def __init__(self, ip, port=DEFAULT_PORT, reconnect_time=DEFAULT_TCP_CLIENT_RECONNECT_TIME):
        super().__init__()
        # 1-indexed channel arrays; index 0 is unused
        # self.yamahaGain = [0] * (self.NUM_CH + 1)
        # self.yamahaMute = [False] * (self.NUM_CH + 1)
        self.buffer = ""
        self.dv = TcpClient(ip, port, reconnect_time=reconnect_time)
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.last_scene = -1
        self.state = {}

    @handle_exception
    def init(self):
        self.dv.on("received", lambda evt: self.parse_response(evt.arguments["data"]))
        self.dv.connect()

    @handle_exception
    def recall_scene(self, scene_no):
        if scene_no < 1:
            return -1
        self.dv.send(f"ssrecall_ex scene_a {scene_no-1}\n")
        # self.dv.send(f"ssrecall_ex MIXER:Lib/Scene {scene_no-1}\n")
        self.last_scene = scene_no
        return self.last_scene

    @handle_exception
    def send_set(self, data):
        # Prepare command string by concatenating with prefix and line-ending
        send_msg = f"{YAMAHA_CMD_SET} {YAMAHA_CMD_PREFIX}{data}\n"
        self.dv.send(send_msg)

    @handle_exception
    def compare_value_with_lut(self, arr, val):
        if len(arr) < 2:
            return 1
        if val <= arr[0]:
            # self.log_yamaha("compare_value_with_lut() :: value is below index 0")
            return 0
        if val >= arr[-1]:
            # self.log_yamaha("compare_value_with_lut() :: value is above last index")
            return len(arr) - 1
        low = 0
        high = len(arr) - 1
        while low <= high:
            mid = (low + high) // 2
            if val < arr[mid]:
                high = mid - 1
            elif val >= arr[mid] and val < arr[mid + 1]:
                # self.log_yamaha("compare_value_with_lut() :: result =", mid)
                return mid
            else:
                low = mid + 1
        return 0

    # TODO - 만들거임 ㅠ
    @handle_exception
    def set_gain(self, address, idx_ch, lut_gain):
        if self.state.get(address) is None:
            self.state[address] = {}
        if self.state[address].get(idx_ch) is None:
            self.state[address][idx_ch] = {}
        self.state[address][idx_ch]["lut_gain"] = lut_gain
        self.state[address][idx_ch]["gain"] = YAMAHA_GAIN_LUT[lut_gain]
        self.send_set(f"{address}{YAMAHA_CMD_TYPE_GAIN} {idx_ch} 0 {YAMAHA_GAIN_LUT[lut_gain]}")

    # TODO - 만들거임 ㅠ
    @handle_exception
    def set_mute(self, address, idx_ch, mute: bool):
        if self.state.get(address) is None:
            self.state[address] = {}
        if self.state[address].get(idx_ch) is None:
            self.state[address][idx_ch] = {}
        self.state[address][idx_ch]["mute"] = mute
        self.send_set(f"{address}{YAMAHA_CMD_TYPE_MUTE} {idx_ch} 0 {1 if mute else 0}")

    # TODO - self.state[YAMAHA_CMD_INPUT]["1"]["lut_gain"] = 10 이런식으로 데이터 저장되고 가져오도록 dict 구조 만들거임
    @handle_exception
    def parse_response(self, data_text):
        msg = "".join(data_text.decode().split("\n")[0])
        self.log_debug(f"parse_response() : {msg=}")
        if msg.startswith("NOTIFY ssrecall_ex scene_a"):
            idx_scene = int(msg[27:])
            self.last_scene = idx_scene + 1
            # emit: scene_recall(scene_no: int)
            self.emit("scene_recall", scene_no=self.last_scene)
