from mojo import context
from typing import Sequence, Union

from lib.networkmanager import TcpClient
from lib.lib_yeoul import handle_exception

# ---------------------------------------------------------------------------- #
program_name = "bss_soundweb_london_mod_v17"
# ---------------------------------------------------------------------------- #
BLU_CHAR_STX = 0x02
BLU_CHAR_ETX = 0x03
BLU_CHAR_ACK = 0x06
BLU_CHAR_NAK = 0x15
BLU_CHAR_ESC = 0x1B
BLU_CHAR_ET = 0x88
# ---------------------------------------------------------------------------- #
# NOTE - DEVICE CONSTANTS FOR <DEVICE> FUNCTION PARAMETER
BLU_DEV_AUTOMIXER = 1
BLU_DEV_MIXER = 2
BLU_DEV_GAIN = 3
BLU_DEV_MM = 4
BLU_DEV_ROUTER = 6
BLU_DEV_METER = 7
BLU_DEV_SOURCE_SELECTOR = 8
BLU_DEV_SOURCE_MATRIX = 9
BLU_DEV_N_GAIN = 10
BLU_DEV_INPUT_CARD = 11
BLU_DEV_OUTPUT_CARD = 12
BLU_DEV_ROOM_COMBINE = 26
BLU_DEV_TELEPHONE = 27
BLU_DEV_LOGIC_SOURCE = 1
BLU_DEV_LOGIC_END = 0
# ---------------------------------------------------------------------------- #
# NOTE - PARAMETER CONSTANTS <PARAM> FUNCTION PARAMETER
BLU_PARAM_METER = 7
BLU_PARAM_UNMUTE = 0
BLU_PARAM_MUTE = 1
BLU_PARAM_ROUTE = 1
BLU_PARAM_GAIN = 3
BLU_PARAM_UNROUTE = 0
BLU_PARAM_POLARITY_ON = 1
BLU_PARAM_POLARITY_OFF = 0
BLU_PARAM_BUMP_UP_ON = 3
BLU_PARAM_BUMP_UP_OFF = 2
BLU_PARAM_BUMP_DOWN_ON = 5
BLU_PARAM_BUMP_DOWN_OFF = 4
BLU_PARAM_LOGIC_SOURCE = 1
BLU_PARAM_LOGIC_END = 0
# ---------------------------------------------------------------------------- #
# NOTE - PARAMETER CONSTANTS SPECIFICALLY FOR 'SET_MIXER' <PARAM> FUNCTION PARAMETER*/
BLU_PARAM_SOLO = 13
BLU_PARAM_GROUP = 14
BLU_PARAM_AUX = 15
BLU_PARAM_OVERRIDE = 16
BLU_PARAM_AUTO = 17
BLU_PARAM_AUX_GAIN = 18
BLU_PARAM_PAN = 19
BLU_PARAM_OFF_GAIN = 20
BLU_PARAM_GROUP_GAIN = 21
# ---------------------------------------------------------------------------- #
# NOTE - PARAMETER CONSTANTS SPECIFICALLY FOR 'SET_ROOMCOMBINE' <PARAM> FUNCTION PARAMETER
BLU_PARAM_SOURCE_MUTE = 30
BLU_PARAM_BGM_MUTE = 31
BLU_PARAM_MASTER_MUTE = 32
BLU_PARAM_SOURCE_GAIN = 33
BLU_PARAM_BGM_GAIN = 34
BLU_PARAM_MASTER_GAIN = 35
BLU_PARAM_BGM_SELECT = 36
BLU_PARAM_PARTITION = 37
# ---------------------------------------------------------------------------- #
# NOTE - PARAMETER CONSTANTS SPECIFICALLY FOR 'SET_TELEPHONE' <PARAM> FUNCTION PARAMETER
BLU_PARAM_BUTTON_0 = 38
BLU_PARAM_BUTTON_1 = 39
BLU_PARAM_BUTTON_2 = 40
BLU_PARAM_BUTTON_3 = 41
BLU_PARAM_BUTTON_4 = 42
BLU_PARAM_BUTTON_5 = 43
BLU_PARAM_BUTTON_6 = 44
BLU_PARAM_BUTTON_7 = 45
BLU_PARAM_BUTTON_8 = 46
BLU_PARAM_BUTTON_9 = 47
BLU_PARAM_T_PAUSE = 48
BLU_PARAM_CLEAR = 49
BLU_PARAM_INTERNATIONAL = 50
BLU_PARAM_BACKSPACE = 51
BLU_PARAM_REDIAL = 52
BLU_PARAM_FLASH = 53
BLU_PARAM_SPEED_DIAL_STORE_SELECT = 54
BLU_PARAM_SPEED_DIAL_SELECT = 55
BLU_PARAM_TX_MUTE = 56
BLU_PARAM_RX_MUTE = 57
BLU_PARAM_DIAL_HANGUP = 58
BLU_PARAM_AUTO_ANSWER = 59
BLU_PARAM_TX_GAIN = 60
BLU_PARAM_RX_GAIN = 61
BLU_PARAM_DTMF_GAIN = 62
BLU_PARAM_DIAL_TONE_GAIN = 63
BLU_PARAM_RING_GAIN = 64
BLU_PARAM_TELEPHONE_NUMBER = 65
BLU_PARAM_INCOMING_CALL = 66
BLU_PARAM_ASTERISK = 67
BLU_PARAM_POUND = 68
# ---------------------------------------------------------------------------- #
# NOTE - PARAMETER CONSTANTS SPECIFICALLY FOR 'SET_PRESET' <PARAM> FUNCTION PARAMETER
BLU_PARAM_DEVICE_PRESET = 1
BLU_PARAM_PARAMETER_PRESET = 2
# NOTE - PARAMETER CONSTANTS ONLY WHEN <DEVICE> = = INPUT_CARD || OUTPUT_CARD
# NOTE - GAIN IS ALSO VALID BUT ALREADY DEFINED ABOVE
BLU_PARAM_PHANTOM = 22
BLU_PARAM_REFERENCE = 23
BLU_PARAM_ATTACK = 24
BLU_PARAM_RELEASED = 25
# NOTE - GENERAL FORMAT CONSTANTS
# NOTE - INPUT_CARD DENOTIONS
BLU_PARAM_A = 1
BLU_PARAM_B = 2
BLU_PARAM_C = 3
BLU_PARAM_D = 4
# NOTE - LEFT CHANNEL, RIGHT CHANNEL FOR MIXERS/AUTOMIXERS
BLU_PARAM_L = 1
BLU_PARAM_R = 3
# ---------------------------------------------------------------------------- #


# ---------------------------------------------------------------------------- #
MIN_VAL = -60  # 최소 값
MAX_VAL = 6  # 최대 값
UNIT_VAL = 1  # 단위 값


# ---------------------------------------------------------------------------- #
class BluObserver:
    # 옵저버 리스트 초기화
    def __init__(self):
        self._observers = []

    # 옵저버 추가
    @handle_exception
    def subscribe(self, observer):
        self._observers.append(observer)

    # 옵저버 제거
    @handle_exception
    def unsubscribe(self, observer):
        self._observers.remove(observer)

    # 모든 옵저버에게 알림
    @handle_exception
    def notify(self, *args, **kwargs):
        for observer in self._observers:
            observer(*args, **kwargs)


# ---------------------------------------------------------------------------- #
class BluState:
    # 상태 저장 딕셔너리 초기화
    def __init__(self):
        self._states = {}
        self._event = BluObserver()  # 이벤트 옵저버 초기화

    # 상태 가져오기
    @handle_exception
    def get_state(self, key):
        return self._states.get(key, None)
        # 상태 설정

    @handle_exception
    def set_state(self, key, val):
        self._states[key] = val

    @handle_exception
    def update_state(self, key, val):
        self.set_state(key, val)  # 상태 업데이트
        self._event.notify(key)  # 상태 변경 알림

    # 상태 변경 강제 알림
    @handle_exception
    def override_notify(self, key):
        self._event.notify(key)

    # 옵저버 추가
    @handle_exception
    def subscribe(self, observer):
        self._event.subscribe(observer)

    # 옵저버 제거
    @handle_exception
    def unsubscribe(self, observer):
        self._event.unsubscribe(observer)
MIN_VAL = -60  # 최소 값
MAX_VAL = 6  # 최대 값
UNIT_VAL = 1  # 단위 값

# ---------------------------------------------------------------------------- #
class BssSoundweb(ip, name,  min_val=MIN_VAL, max_val=MAX_VAL, ):
    def __init__(self, ip, name):
        self.ip = ip
        self.name = name
        self.MIN_VAL = min_val  # 최소 값 설정
        self.MAX_VAL = max_val  # 최대 값 설정
        self.UNIT_VAL = unit_val  # 볼륨 조절 단위 값 설정
        self.dv = TcpClient(self.name, ip, 1023)
        self.states = BluState() if states is None else states  # 컴포넌트 상태 설정
        self.check_message_attempts = 0
        self.debug_flag = 0
        self.buffer = bytearray(10000)
        self.is_initiating = False
        self.six_received = 0
        self.feedback_list = []
        self.dv.connect()
        self.states = BluState() if states is None else states  # 컴포넌트 상태 설정

    def get_sv(self, device, idx_in, idx_out, param):
        int_sv = -1
        # ---------------------------------------------------------------------------- #
        if device == BLU_DEV_LOGIC_SOURCE:
            if param == BLU_PARAM_LOGIC_SOURCE:
                int_sv = 1
        elif device == BLU_DEV_LOGIC_END:
            if param == BLU_PARAM_LOGIC_END:
                int_sv = 0
            # ---------------------------------------------------------------------------- #
            # OUTPUT FIELD = 0 SO MEANS ADJUST INPUT VALUES
            if idx_in != 0 and idx_out == 0:
                if param == BLU_PARAM_SOURCE_MUTE:
                    int_sv = (idx_in - 1) * 50 + 256
                elif param == BLU_PARAM_BGM_MUTE:
                    int_sv = (idx_in - 1) * 50 + 258
                elif param == BLU_PARAM_SOURCE_GAIN:
                    int_sv = (idx_in - 1) * 50 + 255
                elif param == BLU_PARAM_BGM_GAIN:
                    int_sv = (idx_in - 1) * 50 + 257
                elif param == BLU_PARAM_BGM_SELECT:
                    int_sv = (idx_in - 1) * 50 + 259
                # BACKGROUND MUSIC
                elif param == BLU_PARAM_PARTITION:
                    int_sv = idx_in - 1
                elif param == BLU_PARAM_GROUP:
                    int_sv = (idx_in - 1) * 50 + 250
                # ERROR MESSAGE TO CONSOLE
            elif idx_in == 0 and idx_out != 0:
                if param == BLU_PARAM_MASTER_MUTE:
                    int_sv = (idx_out - 1) * 50 + 254
                elif param == BLU_PARAM_MASTER_GAIN:
                    int_sv = (idx_out - 1) * 50 + 252
        # ---------------------------------------------------------------------------- #

    def set_val(self, obj, device, idx_in, idx_out, param, value):
        if device == BLU_DEV_OUTPUT_CARD or device == BLU_DEV_INPUT_CARD:
            event = 0x8D
            get_event = 0x8E
            s_v = self.get_sv(device, idx_in, idx_out, param)

    def bump_up_on(self, obj):
        event = 0x88
        s_v = 0x03
        s_vlow = s_v & 0xFF
        s_vhigh = (s_v >> 8) & 0xFF
        my_data = bytearray([0x00, 0x00, 0x00, 0x00])
        send = bytearray(event.to_bytes(1, "big"))
        if isinstance(obj, (bytes, bytearray)):
            send += obj
        else:
            raise TypeError("obj must be a bytes or bytearray object")
        send += s_vhigh.to_bytes(1, "big")
        send += s_vlow.to_bytes(1, "big")
        send += my_data
        self.checksum_then_send(send)

    def checksum_then_send(self, send):
        cs = 0
        send = bytearray()
        for s in send:
            cs ^= s
            if check_special_char


    def check_special_char(self, s):
        return


# ...existing code...
