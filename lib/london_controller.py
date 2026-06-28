# 마지막 수정일 : 20260625
import math
import threading
from enum import IntEnum

from lib.utility import CommonLogger

MIN_VAL = -60  # 최소 값
MAX_VAL = 10  # 최대 값
UNIT_VAL = 1  # 단위 값2


class LondonObserver:
    def __init__(self):
        self._observers = []
        self._lock = threading.Lock()

    def subscribe(self, observer):
        with self._lock:
            if observer not in self._observers:
                self._observers.append(observer)

    def unsubscribe(self, observer):
        with self._lock:
            if observer in self._observers:
                self._observers.remove(observer)

    def notify(self, *args, **kwargs):
        with self._lock:
            observers = list(self._observers)
        for observer in observers:
            try:
                observer(*args, **kwargs)
            except Exception as e:
                from lib.utility import handler_loc
                print(f"(ERROR) - LondonObserver : notify() {handler_loc(observer)} {e=}")


class LondonState:
    def __init__(self):
        self._states = {}
        self._event = LondonObserver()
        self._lock = threading.Lock()

    def get_all_states_keys(self):
        with self._lock:
            return list(self._states.keys())

    def get_state(self, key):
        with self._lock:
            return self._states.get(key, None)

    def set_state(self, key, value):
        with self._lock:
            self._states[key] = value
        self._event.notify(key, value)

    def remove_state(self, key):
        with self._lock:
            self._states.pop(key, None)

    def override_notify(self, key, *args, **kwargs):
        self._event.notify(key, *args, **kwargs)

    def subscribe(self, observer):
        self._event.subscribe(observer)

    def unsubscribe(self, observer):
        self._event.unsubscribe(observer)


class LondonDev(IntEnum):
    AUTOMIXER = 1
    MIXER = 2
    GAIN = 3
    MATRIX_MIXER = 4
    ROUTER = 6
    METER = 7
    SOURCE_SELECTOR = 8
    SOURCE_MATRIX = 9
    N_GAIN = 10
    INPUT_CARD = 11
    OUTPUT_CARD = 12
    ROOM_COMBINE = 26
    TELEPHONE = 27
    LOGIC_SOURCE = 31
    LOGIC_END = 30


class LondonParam(IntEnum):
    # PARAMETER CONSTANTS <PARAM> FUNCTION PARAMETER
    METER = 7
    UNMUTE = 0
    MUTE = 1
    ROUTE = 1
    GAIN = 3
    UNROUTE = 0
    POLARITY_ON = 1
    POLARITY_OFF = 0
    BUMP_UP_ON = 3
    BUMP_UP_OFF = 2
    BUMP_DOWN_ON = 5
    BUMP_DOWN_OFF = 4
    LOGIC_SOURCE = 1
    LOGIC_END = 0
    SOURCE_SELECTOR = 0
    # PARAMETER CONSTANTS SPECIFICALLY FOR 'SET_MIXER' <PARAM> FUNCTION PARAMETER
    SOLO = 13
    GROUP = 14
    AUX = 15
    OVERRIDE = 16
    AUTO = 17
    AUX_GAIN = 18
    PAN = 19
    OFF_GAIN = 20
    GROUP_GAIN = 21
    # PARAMETER CONSTANTS SPECIFICALLY FOR 'SET_ROOMCOMBINE' <PARAM> FUNCTION PARAMETER
    SOURCE_MUTE = 30
    BGM_MUTE = 31
    MASTER_MUTE = 32
    SOURCE_GAIN = 33
    BGM_GAIN = 34
    MASTER_GAIN = 35
    BGM_SELECT = 36
    PARTITION = 37
    # PARAMETER CONSTANTS SPECIFICALLY FOR 'SET_PRESET' <PARAM> FUNCTION PARAMETER
    DEVICE_PRESET = 1
    PARAMETER_PRESET = 2
    # PARAMETER CONSTANTS ONLY WHEN <DEVICE> == INPUT_CARD || OUTPUT_CARD
    PHANTOM = 22
    REFERENCE = 23
    ATTACK = 24
    RELEASED = 25
    # GENERAL FORMAT CONSTANTS
    A = 1
    B = 2
    C = 3
    D = 4
    # INPUT_CARD DENOTIONS
    L = 1
    R = 3


BLU_IP_PORT = 1023


class LondonController(CommonLogger):
    DEFAULT_PORT = BLU_IP_PORT

    def __init__(self, dv, min_val=MIN_VAL, max_val=MAX_VAL, unit_val=UNIT_VAL):
        self.dv = dv
        self.buffer = bytearray()
        self.states = LondonState()
        self.meter_subscription_rate = 250
        self.check_message_attempts = 0
        self._buffer_lock = threading.Lock()
        self.MAX_VAL = max_val
        self.MIN_VAL = min_val
        self.UNIT_VAL = unit_val
        self._init()
        # london 은 시리얼 쓸 일도 있으니까..

    def online(self, callback):
        self.dv.online(callback)

    def parse(self, data: bytes | bytearray):
        # 수신 데이터를 버퍼에 추가하고 파싱
        with self._buffer_lock:
            self.buffer.extend(data)
            while self.buffer:
                before_len = len(self.buffer)
                self.parse_buffer()
                if len(self.buffer) == before_len:
                    self.log_error(f"parse() : parser made no progress, dropping byte {self.buffer[0]:02x}")
                    self.buffer.pop(0)

    def _init(self):
        # 디바이스 수신 이벤트 리스너 등록
        self.dv.receive.listen(lambda event: self.parse(event.arguments["data"]))

    def add_path_event(self, observer):
        # 상태 변경 옵저버 등록
        self.states.subscribe(observer)

    def set_meter_subscription_rate(self, rate: int):
        # 메터 구독 주기 설정 (ms 단위)
        self.meter_subscription_rate = rate

    def get_key(self, node_addr, index_device, index_input, index_output, index_param) -> bytes:
        # 상태 저장소의 키 생성
        s_v = self.get_sv(index_device, index_input, index_output, index_param)
        return bytes(node_addr + s_v) if s_v else b""

    def get_val(self, key: bytes | bytearray) -> int:
        # 키에 해당하는 상태값 조회 (없으면 0 반환)
        return self.states.get_state(key) or 0

    def get_val_by_node_sv(self, *node_sv) -> int:
        # 노드와 SV 값으로 상태값 조회
        return self.get_val(self.get_key(*node_sv))

    def convert_db_to_value(self, db_value: float) -> int:
        # dB 값을 장비 컨트롤 값으로 변환
        # -10dB 이상: 선형 변환, 미만: 로그 변환
        return int(db_value * 10000 if db_value >= -10 else (-math.log10(abs(db_value / 10)) * 200000) - 100000)

    def convert_value_to_db(self, int_value: int) -> float:
        # 장비 컨트롤 값을 dB 값으로 변환
        return float(int_value / 10000) if int_value >= -100000 else float(-10 * (10 ** ((-int_value - 100000) / 200000)))

    def bump_up_on(self, node_addr: bytes | bytearray):
        # 상승 범프 온
        self.checksum_then_send(bytes(b"\x88" + node_addr + b"\x00\x03" + b"\x00\x00\x00\x01"))

    def bump_up_off(self, node_addr: bytes | bytearray):
        # 상승 범프 오프
        self.checksum_then_send(bytes(b"\x88" + node_addr + b"\x00\x03" + b"\x00\x00\x00\x00"))

    def bump_down_on(self, node_addr: bytes | bytearray):
        # 하강 범프 온
        self.checksum_then_send(bytes(b"\x88" + node_addr + b"\x00\x04" + b"\x00\x00\x00\x01"))

    def bump_down_off(self, node_addr: bytes | bytearray):
        # 하강 범프 오프
        self.checksum_then_send(bytes(b"\x88" + node_addr + b"\x00\x04" + b"\x00\x00\x00\x00"))

    def set_val(
        self,
        node_addr: bytes | bytearray,
        index_device: int,
        index_input: int,
        index_output: int,
        index_param: int,
        value: int,
    ):
        # 기기별 특화된 값 설정 루틴으로 분기
        if index_device == LondonDev.MIXER:
            self.set_mixer(node_addr, index_input, index_output, index_param, value)
            return
        elif index_device == LondonDev.ROOM_COMBINE:
            self.set_room_combine(node_addr, index_input, index_output, index_param, value)
            return
        # INPUT_CARD, OUTPUT_CARD는 바이트 2 위치에 값을 설정
        elif index_device in (LondonDev.OUTPUT_CARD, LondonDev.INPUT_CARD):
            event = b"\x8d"
            get_event = b"\x8e"
            s_v = self.get_sv(index_device, index_input, index_output, index_param)
            my_data = bytes([0x00, value, 0x00, 0x00])
        # 기타 기기는 바이트 4 위치에 값을 설정
        else:
            event = b"\x88"
            get_event = b"\x89"
            s_v = self.get_sv(index_device, index_input, index_output, index_param)
            my_data = bytes([0x00, 0x00, 0x00, value])
        if s_v:
            self.checksum_then_send(bytes(event + node_addr + s_v + my_data))
            # Set 후 Get 명령으로 현재값 확인
            self.checksum_then_send(bytes(get_event + node_addr + s_v + bytes([0x00, 0x00, 0x00, 0x00])))

    def set_mixer(self, node_addr: bytes | bytearray, index_input: int, index_output: int, index_param: int, value: int):
        # 믹서 파라미터 중 특정 파라미터는 바이트 2 위치에 설정
        if index_param in (LondonParam.PAN, LondonParam.OFF_GAIN, LondonParam.AUX_GAIN, LondonParam.GROUP_GAIN):
            event = b"\x8d"
            get_event = b"\x8e"
            s_v = self.get_sv(LondonDev.MIXER, index_input, index_output, index_param)
            my_data = bytes([0x00, value, 0x00, 0x00])
        else:
            event = b"\x88"
            get_event = b"\x89"
            s_v = self.get_sv(LondonDev.MIXER, index_input, index_output, index_param)
            my_data = bytes([0x00, 0x00, 0x00, value])
        if s_v:
            self.checksum_then_send(bytes(event + node_addr + s_v + my_data))
            self.checksum_then_send(bytes(get_event + node_addr + s_v + bytes([0x00, 0x00, 0x00, 0x00])))

    def set_room_combine(self, node_addr: bytes | bytearray, index_input: int, index_output: int, index_param: int, value: int):
        # 룸컴바인 파라미터 중 특정 파라미터는 바이트 2 위치에 설정
        if index_param in (LondonParam.SOURCE_GAIN, LondonParam.BGM_GAIN, LondonParam.MASTER_GAIN):
            event = b"\x8d"
            get_event = b"\x8e"
            s_v = self.get_sv(LondonDev.ROOM_COMBINE, index_input, index_output, index_param)
            my_data = bytes([0x00, value, 0x00, 0x00])
        else:
            event = b"\x88"
            get_event = b"\x89"
            s_v = self.get_sv(LondonDev.ROOM_COMBINE, index_input, index_output, index_param)
            my_data = bytes([0x00, 0x00, 0x00, value])
        if s_v:
            self.checksum_then_send(bytes(event + node_addr + s_v + my_data))
            self.checksum_then_send(bytes(get_event + node_addr + s_v + bytes([0x00, 0x00, 0x00, 0x00])))

    def set_gain(self, node_addr: bytes | bytearray, index_device: int, index_input: int, index_output: int, _: int, value: int):
        # 게인값은 4바이트 부호있는 정수로 설정
        event = b"\x88"
        get_event = b"\x89"
        s_v = self.get_sv(index_device, index_input, index_output, LondonParam.GAIN)
        my_data = value.to_bytes(4, "big", signed=True)
        if s_v:
            self.checksum_then_send(bytes(event + node_addr + s_v + my_data))
            self.checksum_then_send(bytes(get_event + node_addr + s_v + bytes([0x00, 0x00, 0x00, 0x00])))

    def set_preset(self, preset_type: int, preset_number: int):
        # 프리셋 타입에 따라 파라미터 또는 디바이스 프리셋 설정
        if preset_type == LondonParam.PARAMETER_PRESET:
            self.checksum_then_send(bytes([0x8C, 0x00, 0x00, 0x00, preset_number]))
        elif preset_type == LondonParam.DEVICE_PRESET:
            self.checksum_then_send(bytes([0x8B, 0x00, 0x00, 0x00, preset_number]))

    def subscribe(self, node_addr: bytes | bytearray, index_device: int, index_input: int, index_output: int, index_param: int):
        # 상태값 구독 설정 (메터는 주기설정, 기타는 0)
        event = b"\x89"
        s_v = self.get_sv(index_device, index_input, index_output, index_param)
        if not s_v:
            self.log_error("subscribe() : invalid s_v")
            return
        index_param = self.meter_subscription_rate if index_param == LondonParam.METER else 0
        my_data = bytes([0x00, 0x00, 0x00, index_param])
        # 초기 상태값 설정
        self.states.set_state(bytes(node_addr + s_v), int.from_bytes(my_data, "big", signed=True))
        # 구독 명령 전송
        self.checksum_then_send(bytes(event + node_addr + s_v + my_data))

    def unsubscribe(self, node_addr: bytes | bytearray, index_device: int, index_input: int, index_output: int, index_param: int):
        # 상태값 구독 해제
        event = b"\x8a"
        s_v = self.get_sv(index_device, index_input, index_output, index_param)
        if not s_v:
            self.log_error("unsubscribe() : invalid s_v")
            return
        index_param = self.meter_subscription_rate if index_param == LondonParam.METER else 0
        my_data = bytes([0x00, 0x00, 0x00, index_param])
        # 상태값 제거
        self.states.remove_state(bytes(node_addr + s_v))
        # 구독 해제 명령 전송
        self.checksum_then_send(bytes(event + node_addr + s_v + my_data))

    def get_sv(self, index_device, index_input, index_output, index_param):
        # 기기, 입출력, 파라미터 인덱스를 장비 SV(Sub-Verb) 값으로 변환
        try:
            sv = None
            # LOGIC_SOURCE: 로직 소스 SV 계산
            if index_device == LondonDev.LOGIC_SOURCE:
                if index_param == LondonParam.LOGIC_SOURCE:
                    sv = 1
            # LOGIC_END: 로직 엔드 SV 계산
            elif index_device == LondonDev.LOGIC_END:
                if index_param == LondonParam.LOGIC_END:
                    sv = 0
            # AUTOMIXER, MIXER: 입력 채널당 100 오프셋으로 파라미터별 SV 계산
            elif index_device == LondonDev.AUTOMIXER or index_device == LondonDev.MIXER:
                if index_input != 0 and index_output == 0:
                    if index_param == LondonParam.GAIN:
                        sv = (index_input - 1) * 100
                    elif index_param == LondonParam.MUTE:
                        sv = (index_input - 1) * 100 + 1
                    elif index_param == LondonParam.PAN:
                        sv = (index_input - 1) * 100 + 2
                    elif index_param == LondonParam.SOLO:
                        sv = (index_input - 1) * 100 + 4
                    elif index_param == LondonParam.OVERRIDE:
                        sv = (index_input - 1) * 100 + 5
                    elif index_param == LondonParam.OFF_GAIN:
                        sv = (index_input - 1) * 100 + 6
                    elif index_param == LondonParam.AUTO:
                        sv = (index_input - 1) * 100 + 7
                # 출력 채널(AUX/GROUP) SV 계산
                elif index_input == 0 and index_output != 0:
                    if index_param == LondonParam.GAIN:
                        sv = index_output + 20000 - 1
                    elif index_param == LondonParam.MUTE:
                        sv = index_output + 20000
                    elif index_param == LondonParam.AUX_GAIN:
                        sv = (index_output - 1) * 10 + 10001
                    elif index_param == LondonParam.AUX:
                        sv = (index_output - 1) * 10 + 10002
                    elif index_param == LondonParam.GROUP_GAIN:
                        sv = (index_output - 1) * 10 + 11000
                    elif index_param == LondonParam.GROUP:
                        sv = (index_output - 1) * 10 + 11001
                # 입출력 혼합: GROUP 파라미터
                elif index_param == LondonParam.GROUP:
                    sv = (index_input - 1) * 100 + (index_output - 1) + 40
            # ROOM_COMBINE: 복합 로직으로 SV 계산
            elif index_device == LondonDev.ROOM_COMBINE:
                if index_input != 0 and index_output == 0:
                    if index_param == LondonParam.PARTITION:
                        sv = index_input - 1
                    elif index_param == LondonParam.GROUP:
                        sv = (index_input - 1) * 50 + 250
                    elif index_param == LondonParam.SOURCE_GAIN:
                        sv = (index_input - 1) * 50 + 255
                    elif index_param == LondonParam.SOURCE_MUTE:
                        sv = (index_input - 1) * 50 + 256
                    elif index_param == LondonParam.BGM_GAIN:
                        sv = (index_input - 1) * 50 + 257
                    elif index_param == LondonParam.BGM_MUTE:
                        sv = (index_input - 1) * 50 + 258
                    elif index_param == LondonParam.BGM_SELECT:
                        sv = (index_input - 1) * 50 + 259
                elif index_input == 0 and index_output != 0:
                    if index_param == LondonParam.MASTER_GAIN:
                        sv = (index_output - 1) * 50 + 252
                    elif index_param == LondonParam.MASTER_MUTE:
                        sv = (index_output - 1) * 50 + 254
            # ROUTER, MATRIX_MIXER: 입출력 조합으로 SV 계산
            elif index_device == LondonDev.ROUTER or index_device == LondonDev.MATRIX_MIXER:
                if index_param == LondonParam.MUTE or index_param == LondonParam.UNMUTE:
                    sv = (index_input - 1) + ((index_output - 1) * 128)
                elif index_param == LondonParam.GAIN:
                    sv = (index_input + 16383) + ((index_output - 1) * 128)
            # N_GAIN: 입출력 채널별 게인 제어
            elif index_device == LondonDev.N_GAIN:
                if index_output == 0:
                    if index_param == LondonParam.MUTE or index_param == LondonParam.UNMUTE:
                        sv = (index_input - 1) + 32
                    elif index_param == LondonParam.GAIN:
                        sv = index_input - 1
                elif index_input == 0:
                    if index_param == LondonParam.GAIN:
                        sv = 96
                    elif index_param == LondonParam.MUTE or index_param == LondonParam.UNMUTE:
                        sv = 97
            # GAIN: 단일 게인 제어 기기
            elif index_device == LondonDev.GAIN:
                if index_output == 0 and index_input == 1:
                    if index_param == LondonParam.GAIN:
                        sv = 0
                    elif index_param == LondonParam.MUTE or index_param == LondonParam.UNMUTE:
                        sv = 1
                    elif index_param == LondonParam.POLARITY_ON or index_param == LondonParam.POLARITY_OFF:
                        sv = 2
                    elif index_param == LondonParam.BUMP_UP_ON or index_param == LondonParam.BUMP_UP_OFF:
                        sv = 3
                    elif index_param == LondonParam.BUMP_DOWN_ON or index_param == LondonParam.BUMP_DOWN_OFF:
                        sv = 4
            # SOURCE_SELECTOR: 소스 선택기
            elif index_device == LondonDev.SOURCE_SELECTOR:
                sv = 0
            # SOURCE_MATRIX: 소스 매트릭스
            elif index_device == LondonDev.SOURCE_MATRIX:
                sv = index_input - 1
            # INPUT_CARD: 입력 카드 채널별 파라미터
            elif index_device == LondonDev.INPUT_CARD:
                if index_param == LondonParam.GAIN:
                    if index_input == 1:
                        sv = 4
                    elif index_input == 2:
                        sv = 10
                    elif index_input == 3:
                        sv = 16
                    elif index_input == 4:
                        sv = 22
                elif index_param == LondonParam.METER:
                    sv = (index_input - 1) * 6
                elif index_param == LondonParam.REFERENCE:
                    sv = (index_input - 1) * 6 + 1
                elif index_param == LondonParam.ATTACK:
                    sv = (index_input - 1) * 6 + 2
                elif index_param == LondonParam.RELEASED:
                    sv = (index_input - 1) * 6 + 3
                elif index_param == LondonParam.PHANTOM:
                    sv = (index_input - 1) * 6 + 5
            # OUTPUT_CARD: 출력 카드 채널별 파라미터
            elif index_device == LondonDev.OUTPUT_CARD:
                if index_param == LondonParam.METER:
                    sv = (index_input - 1) * 4
                elif index_param == LondonParam.REFERENCE:
                    sv = (index_input - 1) * 4 + 1
                elif index_param == LondonParam.ATTACK:
                    sv = (index_input - 1) * 4 + 2
                elif index_param == LondonParam.RELEASED:
                    sv = (index_input - 1) * 4 + 3
            # METER: 메터 기기
            elif index_device == LondonDev.METER:
                if index_param == LondonParam.METER:
                    sv = 0
            # SV 값을 2바이트 부호있는 정수로 변환
            if sv is None or sv < 0:
                return None
            return sv.to_bytes(2, "big", signed=True)
        except Exception as e:
            self.log_error(f"get_sv() {e=}")
            return None

    def check_special_char(self, data: int) -> bool:
        # STX(0x02), ETX(0x03), ACK(0x06), NAK(0x15), ESC(0x1B) 특수문자 검사
        return data in (0x02, 0x03, 0x06, 0x15, 0x1B)

    def checksum_then_send(self, my_string: bytes | bytearray):
        # 체크섬 계산 및 특수문자 이스케이프 처리 후 전송
        try:
            send = bytearray()
            CS = 0
            # 체크섬 계산: XOR 연산으로 모든 바이트 누적
            for b in my_string:
                CS = CS ^ b
                # 특수문자는 ESC(0x1B) + (문자+128) 형식으로 변환
                if self.check_special_char(b):
                    send.extend([0x1B, (b + 128) & 0xFF])
                else:
                    send.extend([b])
            # 최종 메시지: STX + 데이터 + 체크섬 + ETX
            if self.check_special_char(CS):
                send = b"\x02" + send + bytes([0x1B, (CS + 128) & 0xFF]) + b"\x03"
            else:
                send = b"\x02" + send + bytes([CS]) + b"\x03"
            self.dv.send(send)
        except Exception as e:
            self.log_error(f"checksum_then_send() : {e=}")

    def parse_buffer(self):
        try:
            # 수신 버퍼 파싱: ACK, NAK, 메시지 처리
            if self.buffer.startswith(b"\x06"):
                # ACK(0x06) 처리
                while self.buffer and self.buffer[0] == 0x06:
                    self.buffer.pop(0)
            if self.buffer.startswith(b"\x15"):
                # NAK(0x15) 처리
                self.buffer.pop(0)
            if self.buffer.startswith(b"\x02"):
                # STX(0x02)로 시작하는 메시지 처리
                end_index = self.buffer.find(b"\x03")
                if end_index != -1:
                    # ETX(0x03) 발견: 완전한 메시지 추출
                    message = self.buffer[1:end_index]
                    self.buffer = self.buffer[end_index + 1 :]
                    self.log_debug(f"Message extracted: {message.hex()} Remaining buffer: {self.buffer.hex()}")
                    self.check_message_attempts = 0
                    # 이스케이프 시퀀스 복원: ESC + (문자+128) → 원본 문자
                    temp = bytearray(message)
                    i = 0
                    while i < len(temp):
                        if temp[i] == 0x1B and i + 1 < len(temp):
                            temp[i] = temp[i + 1] - 128
                            temp.pop(i + 1)
                        i += 1
                    # 체크섬 검증: 마지막 바이트 제외 모든 바이트 XOR
                    r_cs = 0
                    for b in temp[:-1]:
                        r_cs = r_cs ^ b
                    # 체크섬 일치 시 메시지 처리
                    if r_cs == temp[-1]:
                        self.process_feedback(temp[:-1])
                    else:
                        self.log_warn(f"parse_buffer() : checksum mismatch {r_cs=} expected={temp[-1]}")
                else:
                    # ETX 미발견: 재시도 횟수 증가
                    self.check_message_attempts += 1
                    if self.check_message_attempts > 5:
                        # 5회 이상 실패시 버퍼 초기화
                        self.buffer.clear()
                        self.check_message_attempts = 0
            elif self.buffer:
                self.log_error(f"parse_buffer() : unexpected start byte {self.buffer[0]:02x}")
                self.buffer.pop(0)
        except Exception as e:
            self.log_error(f"parse_buffer() : {e=}")
            self.buffer.clear()  # 예외 발생 시 클리어 추가

    def process_feedback(self, received_string: bytes | bytearray):
        # 수신한 피드백 메시지 처리 및 상태 업데이트
        try:
            if len(received_string) < 13:
                self.log_error(f"process_feedback() : message too short {len(received_string)=}")
                return
            event = bytes([received_string[0]])
            node = received_string[1:3]
            vd = bytes([received_string[3]])
            node_addr = received_string[4:7]
            s_v = received_string[7:9]
            my_data = received_string[-4:]
            self.log_debug(
                f"process_feedback() : event={event.hex()} node={node.hex()} vd={vd.hex()} node_addr={node_addr.hex()} s_v={s_v.hex()} my_data={my_data.hex()}"
            )
            # 등록된 상태값에만 업데이트
            if bytes(node + vd + node_addr + s_v) in self.states.get_all_states_keys():
                self.states.set_state(bytes(node + vd + node_addr + s_v), int.from_bytes(my_data, "big", signed=True))
        except Exception as e:
            self.log_error(f"process_feedback() : {e=}")

    def check_vol_range(self, val: float) -> bool:
        # 음량값이 설정된 범위 내인지 확인
        return val is not None and self.MIN_VAL <= val <= self.MAX_VAL

    def val_add_unit(self, val: int) -> int:
        # 현재값에서 1 단위만큼 증가 (범위 내일 때)
        val_db = round(self.convert_value_to_db(val) + self.UNIT_VAL)
        if self.MIN_VAL <= val_db <= self.MAX_VAL:
            return self.convert_db_to_value(val_db)
        elif val_db > self.MAX_VAL:
            return self.convert_db_to_value(self.MAX_VAL)
        else:
            return self.convert_db_to_value(self.MIN_VAL)

    def val_sub_unit(self, val: int) -> int:
        # 현재값에서 1 단위만큼 감소 (범위 내일 때)
        val_db = round(self.convert_value_to_db(val) - self.UNIT_VAL)
        if self.MIN_VAL <= val_db <= self.MAX_VAL:
            return self.convert_db_to_value(val_db)
        elif val_db > self.MAX_VAL:
            return self.convert_db_to_value(self.MAX_VAL)
        else:
            return self.convert_db_to_value(self.MIN_VAL)

    def val_toggle(self, val: int) -> int:
        # 이진값 토글: 0 ↔ 1
        if val == 0:
            return 1
        elif val == 1:
            return 0
        else:
            return val

    # 사용자 편의 함수
    def set_gain_up(self, node_addr, index_device, index_input, index_output, index_param):
        # 게인값 상향 조정 (1 단위)
        self.set_gain(
            node_addr,
            index_device,
            index_input,
            index_output,
            index_param,
            self.val_add_unit(self.get_val_by_node_sv(node_addr, index_device, index_input, index_output, index_param)),
        )

    def set_gain_down(self, node_addr, index_device, index_input, index_output, index_param):
        # 게인값 하향 조정 (1 단위)
        self.set_gain(
            node_addr,
            index_device,
            index_input,
            index_output,
            index_param,
            self.val_sub_unit(self.get_val_by_node_sv(node_addr, index_device, index_input, index_output, index_param)),
        )

    def set_value_toggle(self, node_addr, index_device, index_input, index_output, index_param):
        # 토글 타입 파라미터 반전 (0 ↔ 1)
        self.set_val(
            node_addr,
            index_device,
            index_input,
            index_output,
            index_param,
            self.val_toggle(self.get_val_by_node_sv(node_addr, index_device, index_input, index_output, index_param)),
        )

    def set_val_toggle(self, node_addr, index_device, index_input, index_output, index_param):
        self.set_value_toggle(node_addr, index_device, index_input, index_output, index_param)

    def set_value(self, node_addr, index_device, index_input, index_output, index_param, value=None):
        if value is not None:
            self.set_val(node_addr, index_device, index_input, index_output, index_param, value)

    def db_to_tp(self, x):
        # dB 값을 터치패널 0-255 범위로 선형 변환
        try:
            x_min = self.MIN_VAL
            x_max = self.MAX_VAL
            y_min = 0
            y_max = 255
            y = (x - x_min) * (y_max - y_min) / (x_max - x_min) + y_min
            return y
        except Exception as e:
            self.log_error(f"db_to_tp() : {e=}")
            return 0

    def tp_to_db(self, x):
        # 터치패널 0-255 값을 dB 범위로 선형 변환
        x_min = 0
        x_max = 255
        y_min = self.MIN_VAL
        y_max = self.MAX_VAL
        y = (x - x_min) * (y_max - y_min) / (x_max - x_min) + y_min
        return y
