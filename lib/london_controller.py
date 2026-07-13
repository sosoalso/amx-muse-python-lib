# 마지막 수정일 : 20260713
"""BSS Soundweb London 오디오 DSP 를 London DI(Direct Inject) 프로토콜로 제어하는 모듈.
게인/뮤트/소스선택 등 state variable(SV)을 읽고 쓰며, 구독(subscribe)한 SV 의
변경 피드백을 받아 내부 상태 저장소(LondonState)에 반영한다.
회의실/강당 AV 제어에서 믹서, 룸컴바인, 소스 셀렉터 같은 DSP 오브젝트를
터치패널과 연동할 때 사용한다.

AMX 공식 BSS NetLinx Module 을 파이썬으로 포팅한 것으로, 전화(telephone/paging) 등 일부 기능은
제외되어 있다 (정확히 어떤 기능들이 빠졌는지는 원본 모듈과 대조가 필요함).
"""

import math
import threading
from enum import IntEnum

from lib.utility import CommonLogger, handler_loc

MIN_VAL = -60  # 최소 값
MAX_VAL = 10  # 최대 값
UNIT_VAL = 1  # 단위 값2


class LondonObserver:
    """옵저버(콜백) 목록을 스레드 안전하게 관리하는 단순 pub-sub 헬퍼.
    subscribe/unsubscribe 로 콜백을 등록/해제하고, notify 가 호출되면 등록된
    모든 콜백을 실행한다. 개별 콜백에서 예외가 나도 로그만 남기고 나머지는 계속 실행한다.
    """

    def __init__(self, owner):
        self._observers = []
        self._lock = threading.Lock()
        self.owner = owner

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
                self.owner.log_error(f"LondonObserver notify() {handler_loc(observer)} {e=}")


class LondonState:
    """장비 상태값 저장소 (key → value).
    key 는 노드주소+VD+오브젝트주소+SV 를 이어붙인 bytes, value 는 장비 원시값(int).
    set_state 시 등록된 옵저버들에게 (key, value) 형태로 변경을 통지한다.
    """

    def __init__(self, owner):
        self.owner = owner
        self._states = {}
        self._event = LondonObserver(self.owner)
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
    """London DI 프로토콜의 가상 디바이스(DSP 오브젝트) 종류 상수.
    get_sv() 에서 이 값에 따라 SV 번호 계산 방식이 달라진다.
    """

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
    """디바이스별 파라미터 종류 상수.
    같은 숫자가 디바이스에 따라 다른 의미로 재사용된다
    (예: MUTE=1 과 ROUTE=1). 실제 의미는 get_sv() 의 디바이스별 분기에서 결정된다.
    """

    # <PARAM> 함수 파라미터의 일반 파라미터 상수들
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
    # 'SET_MIXER' <PARAM> 함수 파라미터에만 해당하는 파라미터 상수들
    SOLO = 13
    GROUP = 14
    AUX = 15
    OVERRIDE = 16
    AUTO = 17
    AUX_GAIN = 18
    PAN = 19
    OFF_GAIN = 20
    GROUP_GAIN = 21
    # 'SET_ROOMCOMBINE' <PARAM> 함수 파라미터에만 해당하는 파라미터 상수들
    SOURCE_MUTE = 30
    BGM_MUTE = 31
    MASTER_MUTE = 32
    SOURCE_GAIN = 33
    BGM_GAIN = 34
    MASTER_GAIN = 35
    BGM_SELECT = 36
    PARTITION = 37
    # 'SET_PRESET' <PARAM> 함수 파라미터에만 해당하는 파라미터 상수들
    DEVICE_PRESET = 1
    PARAMETER_PRESET = 2
    # <DEVICE> == INPUT_CARD || OUTPUT_CARD 일 때만 해당하는 파라미터 상수들
    PHANTOM = 22
    REFERENCE = 23
    ATTACK = 24
    RELEASED = 25
    # 일반 포맷 상수들
    A = 1
    B = 2
    C = 3
    D = 4
    # INPUT_CARD 표기
    L = 1
    R = 3


# London DI 프로토콜 기본 TCP 포트
BLU_IP_PORT = 1023


class LondonController(CommonLogger):
    """BSS Soundweb London DSP 컨트롤러.
    - dv(TCP/시리얼 디바이스)의 수신 이벤트를 받아 DI 프로토콜 프레임을 파싱하고,
      구독 중인 SV 의 피드백을 states 에 반영한다.
    - set_val/set_gain/subscribe 등으로 SV 설정·구독 명령을 조립해 전송한다.
    - 대표 사용 흐름: subscribe() 로 관심 SV 구독 → add_path_event() 로 상태 변경
      콜백 등록 → set_gain_db()/set_value_toggle() 등으로 제어.
    - 게인은 dB ↔ 장비 원시값 변환(convert_db_to_value 등)을 거친다.
    """

    DEFAULT_PORT = BLU_IP_PORT

    def __init__(self, dv, min_val=MIN_VAL, max_val=MAX_VAL, unit_val=UNIT_VAL):
        """dv 는 send()/receive/online 을 제공하는 통신 디바이스.
        min_val/max_val/unit_val 은 dB 편의 함수(set_gain_up 등)에서 쓰는
        음량 범위와 증감 단위(dB).
        """
        self.dv = dv
        self.buffer = bytearray()
        self.states = LondonState(self)
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
        """수신 바이트를 내부 버퍼에 쌓고 완전한 토큰 단위로 반복 파싱한다.
        parse_buffer 가 진행을 못 하면(같은 버퍼 길이 유지) 맨 앞 바이트를 버려
        파싱이 무한 루프에 빠지지 않게 한다.
        """
        # 수신 데이터를 버퍼에 추가하고 파싱
        with self._buffer_lock:
            self.buffer.extend(data)
            while self.buffer:
                before_len = len(self.buffer)
                if not self.parse_buffer():
                    # 불완전 메시지(ETX 미도착) - 다음 수신 때 이어서 파싱
                    break
                if len(self.buffer) == before_len:
                    self.log_error(f"parse() : parser made no progress, dropping byte {self.buffer[0]:02x}")
                    self.buffer.pop(0)

    def _init(self):
        # 디바이스 수신 이벤트 리스너 등록
        self.dv.receive.listen(lambda evt: self.parse(evt.arguments.get("data", b"")))

    def add_path_event(self, observer):
        # 상태 변경 옵저버 등록
        self.states.subscribe(observer)

    def set_meter_subscription_rate(self, rate: int):
        # 메터 구독 주기 설정 (ms 단위, 0 ~ 65535)
        rate = int(rate)
        if not 0 <= rate <= 0xFFFF:
            self.log_warn(f"set_meter_subscription_rate() : rate out of range, clamped {rate=}")
            rate = max(0, min(rate, 0xFFFF))
        self.meter_subscription_rate = rate

    def get_key(self, node_addr, index_device, index_input, index_output, index_param) -> bytes:
        """상태 저장소 키(노드주소 + SV) 생성. SV 매핑 실패 시 빈 bytes 반환."""
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
        """dB(float) → London 게인 원시값(int) 변환.
        London DI 게인 SV 포맷: -10dB 이상은 dB x 10000 선형 스케일,
        -10dB 미만은 로그 스케일로 인코딩된다.
        """
        # dB 값을 장비 컨트롤 값으로 변환
        # -10dB 이상: 선형 변환, 미만: 로그 변환
        return int(db_value * 10000 if db_value >= -10 else (-math.log10(abs(db_value / 10)) * 200000) - 100000)

    def convert_value_to_db(self, int_value: int) -> float:
        """London 게인 원시값(int) → dB(float) 역변환. convert_db_to_value 의 역함수.
        -100000(= -10dB) 이상은 선형, 그 미만은 로그 스케일 복원.
        """
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
        """SV 에 값을 쓰고 곧바로 Get 을 보내 피드백으로 상태를 갱신한다.
        디바이스 종류에 따라 SET_PERCENT(0x8d, 바이트2 위치)와
        SET(0x88, 바이트4 위치) 중 어떤 이벤트를 쓸지 갈린다.
        """
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
        """믹서 전용 값 설정. 파라미터 종류에 따라 이벤트(0x88/0x8d)와 값 위치가 달라진다."""
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
        """룸컴바인 전용 값 설정. 게인류 파라미터는 0x8d 이벤트로, 나머지는 0x88 로 보낸다."""
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
        """게인 SV 설정. value 는 convert_db_to_value 로 변환된 원시값(4바이트 signed).
        다섯 번째 인자(_)는 다른 set 계열과 시그니처를 맞추기 위한 자리로, 무시하고
        파라미터는 항상 GAIN 으로 고정한다.
        """
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
        """SV 구독 요청. 이후 값 변화가 피드백으로 수신되어 states 에 반영된다.
        부수효과: 해당 key 를 states 에 미리 등록한다. process_feedback 은
        등록된 key 만 갱신하므로, 구독한 SV 만 상태 추적 대상이 된다.
        """
        # 상태값 구독 설정 (메터는 주기설정, 기타는 0)
        event = b"\x89"
        s_v = self.get_sv(index_device, index_input, index_output, index_param)
        if not s_v:
            self.log_error("subscribe() : invalid s_v")
            return
        # 메터 구독 주기는 dword(4바이트)로 인코딩 (0 ~ 65535ms)
        rate = self.meter_subscription_rate if index_param == LondonParam.METER else 0
        my_data = rate.to_bytes(4, "big")
        # 초기 상태값 설정
        self.states.set_state(bytes(node_addr + s_v), int.from_bytes(my_data, "big", signed=True))
        # 구독 명령 전송
        self.checksum_then_send(bytes(event + node_addr + s_v + my_data))

    def unsubscribe(self, node_addr: bytes | bytearray, index_device: int, index_input: int, index_output: int, index_param: int):
        """SV 구독 해제. states 에서 해당 key 도 함께 제거해 피드백 반영을 막는다."""
        # 상태값 구독 해제
        event = b"\x8a"
        s_v = self.get_sv(index_device, index_input, index_output, index_param)
        if not s_v:
            self.log_error("unsubscribe() : invalid s_v")
            return
        # 메터 구독 주기는 dword(4바이트)로 인코딩 (0 ~ 65535ms)
        rate = self.meter_subscription_rate if index_param == LondonParam.METER else 0
        my_data = rate.to_bytes(4, "big")
        # 상태값 제거
        self.states.remove_state(bytes(node_addr + s_v))
        # 구독 해제 명령 전송
        self.checksum_then_send(bytes(event + node_addr + s_v + my_data))

    def get_sv(self, index_device, index_input, index_output, index_param):
        """(디바이스, 입력, 출력, 파라미터) 조합을 SV 번호로 매핑한다.
        반환: 2바이트 big-endian signed bytes, 매핑 불가 시 None.
        SV 번호 체계는 London DI 스펙의 디바이스별 주소 배치를 그대로 옮긴 것
        (예: 믹서 입력 채널당 100 간격, 매트릭스 출력당 128 간격).
        """
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
        """본문에 체크섬을 붙이고 프레임으로 감싸 전송한다.
        프레임: STX(0x02) + 이스케이프된 본문 + 체크섬 + ETX(0x03).
        체크섬은 이스케이프 전 원본 바이트 전체의 XOR 이며,
        체크섬 자체가 특수문자면 그것도 이스케이프한다.
        """
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

    def parse_buffer(self) -> bool:
        # 버퍼 앞의 토큰 하나를 처리. 데이터가 더 필요해서 다음 수신을 기다려야 하면 False 반환
        try:
            # 수신 버퍼 파싱: ACK, NAK, 메시지 처리
            if self.buffer.startswith(b"\x06"):
                # ACK(0x06) 처리
                while self.buffer and self.buffer[0] == 0x06:
                    self.buffer.pop(0)
                return True
            if self.buffer.startswith(b"\x15"):
                # NAK(0x15) 처리
                self.buffer.pop(0)
                return True
            if self.buffer.startswith(b"\x02"):
                # STX(0x02)로 시작하는 메시지 처리
                end_index = self.buffer.find(b"\x03")
                if end_index == -1:
                    # ETX 미발견: 불완전 메시지 - 다음 수신을 기다림 (수신마다 재시도 횟수 증가)
                    self.check_message_attempts += 1
                    if self.check_message_attempts > 5:
                        # 5회 이상 수신에도 ETX가 없으면 쓰레기로 판단하고 버퍼 초기화
                        self.buffer.clear()
                        self.check_message_attempts = 0
                    return False
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
                return True
            if self.buffer:
                self.log_error(f"parse_buffer() : unexpected start byte {self.buffer[0]:02x}")
                self.buffer.pop(0)
            return True
        except Exception as e:
            self.log_error(f"parse_buffer() : {e=}")
            self.buffer.clear()  # 예외 발생 시 클리어 추가
            return True

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
            key = bytes(node + vd + node_addr + s_v)
            if self.states.get_state(key) is not None:
                self.states.set_state(key, int.from_bytes(my_data, "big", signed=True))
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
    def set_gain_db(self, node_addr, index_device, index_input, index_output, index_param, value_db_float):
        # dB 값을 받아 범위 검증 후 장비 컨트롤 값으로 변환하여 설정
        if not self.check_vol_range(value_db_float):
            self.log_error(f"set_gain_db() : value out of range {value_db_float=} but applying value anyway")
        self.set_gain(node_addr, index_device, index_input, index_output, index_param, self.convert_db_to_value(value_db_float))

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
