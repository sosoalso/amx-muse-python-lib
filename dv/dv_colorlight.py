from lib.event_manager import EventManager
from lib.network_manager import UdpClient
from lib.utility import CommonLogger, handle_exception


class Colorlight(CommonLogger, EventManager):
    DEFAULT_SERVER_PORT = 9099
    DEFAULT_BOUND_PORT = 8080

    # Colorlight Device Control Protocol 3.0, 5.2.2.2 응답 프레임의 Sender model(addr24) 표
    SENDER_MODEL = {
        1: "V20",
        2: "Z8",
        3: "X100-4U",
        4: "X100-7U",
        5: "X40m",
        6: "D9",
        7: "D16",
        9: "Z5",
        10: "Z4 PRO",
        11: "X20m",
        13: "V3 Pro",
        14: "V3",
        15: "V2 Pro",
        16: "V2",
        19: "Z3",
        20: "V4",
        21: "V7",
        23: "VX10",
        24: "X100 Pro-4U",
        25: "X100 Pro-7U",
        26: "X100 Pro-11U",
        28: "S20 Pro",
        29: "X12m",
        30: "X8m",
        31: "X26m",
        32: "VX6",
        33: "VX4",
        36: "X100 Pro-2U",
    }

    # 5.2.2.1 Detecting Sender Parameters - 1대만 붙는 구조라 sender index는 항상 0으로 고정
    REQUEST_SENDER_INFO = bytes(
        [
            0x01,
            0x00,
            0x00,
            0x22,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x65,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
        ]
    )

    def __init__(self, ip):
        super().__init__("preset", "input", "sender_info")
        self.dv = UdpClient(ip=ip, port=self.DEFAULT_SERVER_PORT, bound_port=self.DEFAULT_BOUND_PORT)
        self.preset = None
        self.model = None
        self.layers = {}  # layer_no(1-base) -> {slot_no, board_type, input_type, src_no}

    @handle_exception
    def init(self):
        self.dv.connect()
        self.dv.receive.listen(self.parse_response)

    # 5.2.3.9 Preset Switching (128 Presets or More) - X100 Pro 2U/4U/7U/11U 지원 확인됨
    @handle_exception
    def set_preset(self, preset_no):
        command = bytearray([0x07, 0x10, 0x03, 0x13] + [0x00] * 13 + [preset_no - 1, 0x00])
        self.dv.send(command)
        self.log_debug(f"set_preset() {preset_no=}")
        self.preset = preset_no
        # emit: preset(value: int)
        self.emit("preset", value=preset_no)
        return preset_no

    # 5.2.3.4 Setting Input Video Source, byte layout (0-idx):
    # [0-3]header [4-15]zero(sender=0) [16]screen_group(0) [17]layer(0=main,1=PIP1,...)
    # [18-19]slot(LE, 0x0010+slot_no-1) [20]board_type [21]zero [22]input_type [23]src_no-1
    @handle_exception
    def set_input(self, layer_no, slot_no, board_type, input_type, src_no):
        command = bytearray([0x20, 0x10, 0x00, 0x18] + [0x00] * 12)
        command += bytearray([0x00, layer_no - 1])  # group_no == 0
        command += bytearray([0x10 + slot_no - 1, 0x00])
        command += bytearray([board_type, 0x00])
        command += bytearray([input_type, src_no - 1])
        self.dv.send(command)
        # 5.2.3.6 Batch Operation - 입력소스 전환을 실제로 적용시키는 커맨드
        self.dv.send(bytearray([0x52, 0x00, 0x00, 0x10] + [0x00] * 12))
        self.log_debug(f"set_input() {layer_no=}, {slot_no=}, {board_type=}, {input_type=}, {src_no=}")
        self.layers[layer_no] = {
            "slot_no": slot_no,
            "board_type": board_type,
            "input_type": input_type,
            "src_no": src_no,
        }
        # emit: input(layer_no, slot_no, board_type, input_type, src_no)
        self.emit(
            "input",
            layer_no=layer_no,
            slot_no=slot_no,
            board_type=board_type,
            input_type=input_type,
            src_no=src_no,
        )

    def get_layer_input(self, layer_no):
        return self.layers.get(layer_no)

    # 5.2.2.1 Detecting Sender Parameters - 모델/레이어1 입력 정보 조회 요청
    @handle_exception
    def request_sender_info(self):
        self.dv.send(self.REQUEST_SENDER_INFO)
        self.log_debug("request_sender_info()")

    # 5.2.2.2 Response Frame for Detecting Sender Parameters
    @handle_exception
    def parse_response(self, evt):
        data = evt.arguments.get("data", b"")
        if isinstance(data, str):
            data = data.encode("latin-1")
        if not data or data[0] != 0xF1:
            return
        if len(data) < 182 or data[12] != 0x65:
            self.log_debug(f"parse_response() unhandled frame {bytes(data).hex(' ')}")
            return

        self.model = self.SENDER_MODEL.get(data[24], data[24])
        slot_value = int.from_bytes(data[176:178], "little")
        self.layers[1] = {
            "slot_no": slot_value - 0x10 + 1,
            "board_type": data[178],
            "input_type": data[180],
            "src_no": data[181] + 1,
        }
        self.log_debug(f"parse_response() model={self.model} layer1={self.layers[1]}")
        # emit: sender_info(model, layer1)
        self.emit("sender_info", model=self.model, layer1=self.layers[1])
