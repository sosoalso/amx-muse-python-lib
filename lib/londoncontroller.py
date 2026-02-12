import math
from enum import IntEnum

from _mojo import context

# ---------------------------------------------------------------------------- #
VERSION = "2026.02.12"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
MIN_VAL = -60  # 최소 값
MAX_VAL = 10  # 최대 값
UNIT_VAL = 1  # 단위 값


class LondonObserver:
    def __init__(self):
        self._observers = []

    def subscribe(self, observer):
        self._observers.append(observer)

    def unsubscribe(self, observer):
        self._observers.remove(observer)

    def notify(self, *args, **kwargs):
        for observer in self._observers:
            observer(*args, **kwargs)


class LondonState:
    def __init__(self):
        self._states = {}
        self._event = LondonObserver()

    def get_all_states_keys(self):
        return list(self._states.keys())

    def get_state(self, key):
        return self._states.get(key, None)

    def set_state(self, key, value):
        self._states[key] = value
        self._event.notify(key, value)

    def remove_state(self, key):
        self._event.unsubscribe(key)
        self._states.pop(key)

    # def set_state(self, key, value):
    #     self.set_state(key, value)

    def override_notify(self, key, *args, **kwargs):
        self._event.notify(key, *args, **kwargs)

    def subscribe(self, observer):
        self._event.subscribe(observer)

    def unsubscribe(self, observer):
        self._event.unsubscribe(observer)


# ---------------------------------------------------------------------------- #
# STX = 0x02
# ETX = 0x03
# ACK = 0x06
# NAK = 0x15
# ESC = 0x1B
# ET = 0x88


# ---------------------------------------------------------------------------- #
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
    # ---------------------------------------------------------------------------- #
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
    # ---------------------------------------------------------------------------- #
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
    # GAIN IS ALSO VALID BUT ALREADY DEFINED ABOVE
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


# ---------------------------------------------------------------------------- #
BLU_IP_PORT = 1023


# ---------------------------------------------------------------------------- #
class LondonController:
    def __init__(self, dv, min_val=MIN_VAL, max_val=MAX_VAL, unit_val=UNIT_VAL, debug=False):
        # ---------------------------------------------------------------------------- #
        self.dv = dv
        self.buffer = bytearray()
        self.states = LondonState()
        # ---------------------------------------------------------------------------- #
        self.meter_subscription_rate = 250
        self.check_message_attemps = 0
        # ---------------------------------------------------------------------------- #
        self.MAX_VAL = max_val
        self.MIN_VAL = min_val
        self.UNIT_VAL = unit_val
        # ---------------------------------------------------------------------------- #
        self.debug = debug
        self._init()
        # ---------------------------------------------------------------------------- #

    def log_debug(self, message):
        if self.debug:
            context.log.debug(f"LondonController: {message}")

    def log_error(self, message):
        context.log.error(f"LondonController: {message}")

    def online(self, callback):
        self.dv.online(callback)

    # ---------------------------------------------------------------------------- #
    def parse(self, data: bytes | bytearray):
        self.buffer.extend(data)
        while self.buffer:
            self.parse_buffer()

    def _init(self):
        self.dv.receive.listen(lambda event: self.parse(event.arguments["data"]))

    # ---------------------------------------------------------------------------- #
    def add_path_event(self, observer):
        self.states.subscribe(observer)

    # ---------------------------------------------------------------------------- #

    # ---------------------------------------------------------------------------- #
    def set_meter_subscription_rate(self, rate: int):
        self.meter_subscription_rate = rate

    # ---------------------------------------------------------------------------- #
    def get_key(self, node_addr, index_device, index_input, index_output, index_param) -> bytes:
        return bytes(node_addr + self.get_sv(index_device, index_input, index_output, index_param))

    # ---------------------------------------------------------------------------- #
    def get_val(self, key: bytes | bytearray) -> int:
        return self.states.get_state(key) or 0

    def get_val_by_node_sv(self, *node_sv) -> int:
        return self.get_val(self.get_key(*node_sv))

    def convert_db_to_value(self, db_value: float) -> int:
        return int(db_value * 10000 if db_value >= -10 else (-math.log10(abs(db_value / 10)) * 200000) - 100000)

    def convert_value_to_db(self, int_value: int) -> float:
        return float(int_value / 10000) if int_value >= -100000 else float(-10 * (10 ** ((-int_value - 100000) / 200000)))

    # ---------------------------------------------------------------------------- #
    def bump_up_on(self, node_addr: bytes | bytearray):
        self.checksum_then_send(bytes(b"\x88" + node_addr + b"\x00\x03" + b"\x00\x00\x00\x01"))

    def bump_up_off(self, node_addr: bytes | bytearray):
        self.checksum_then_send(bytes(b"\x88" + node_addr + b"\x00\x03" + b"\x00\x00\x00\x00"))

    def bump_down_on(self, node_addr: bytes | bytearray):
        self.checksum_then_send(bytes(b"\x88" + node_addr + b"\x00\x04" + b"\x00\x00\x00\x01"))

    def bump_down_off(self, node_addr: bytes | bytearray):
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
        if index_device == LondonDev.MIXER:
            self.set_mixer(node_addr, index_input, index_output, index_param, value)
            return
        elif index_device == LondonDev.ROOM_COMBINE:
            self.set_room_combine(node_addr, index_input, index_output, index_param, value)
            return
        # ---------------------------------------------------------------------------- #
        elif index_device in (LondonDev.OUTPUT_CARD, LondonDev.INPUT_CARD):
            event = b"\x8d"
            get_event = b"\x8e"
            s_v = self.get_sv(index_device, index_input, index_output, index_param)
            my_data = bytes([0x00, value, 0x00, 0x00])
        else:
            event = b"\x88"
            get_event = b"\x89"
            s_v = self.get_sv(index_device, index_input, index_output, index_param)
            my_data = bytes([0x00, 0x00, 0x00, value])
        if s_v != -1:
            self.checksum_then_send(bytes(event + node_addr + s_v + my_data))
            self.checksum_then_send(bytes(get_event + node_addr + s_v + bytes([0x00, 0x00, 0x00, 0x00])))

    def set_mixer(self, node_addr: bytes | bytearray, index_input: int, index_output: int, index_param: int, value: int):
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
        if s_v != -1:
            self.checksum_then_send(bytes(event + node_addr + s_v + my_data))
            self.checksum_then_send(bytes(get_event + node_addr + s_v + bytes([0x00, 0x00, 0x00, 0x00])))

    def set_room_combine(self, node_addr: bytes | bytearray, index_input: int, index_output: int, index_param: int, value: int):
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
        if s_v != -1:
            self.checksum_then_send(bytes(event + node_addr + s_v + my_data))
            self.checksum_then_send(bytes(get_event + node_addr + s_v + bytes([0x00, 0x00, 0x00, 0x00])))

    # ---------------------------------------------------------------------------- #
    def set_gain(self, node_addr: bytes | bytearray, index_device: int, index_input: int, index_output: int, _: int, value: int):
        event = b"\x88"
        get_event = b"\x89"
        s_v = self.get_sv(index_device, index_input, index_output, LondonParam.GAIN)
        my_data = value.to_bytes(4, "big", signed=True)
        if s_v != -1:
            self.checksum_then_send(bytes(event + node_addr + s_v + my_data))
            self.checksum_then_send(bytes(get_event + node_addr + s_v + bytes([0x00, 0x00, 0x00, 0x00])))

    # ---------------------------------------------------------------------------- #
    def set_preset(self, preset_type: int, preset_number: int):
        if preset_type == LondonParam.PARAMETER_PRESET:
            self.checksum_then_send(bytes([0x8C, 0x00, 0x00, 0x00, preset_number]))
        elif preset_type == LondonParam.DEVICE_PRESET:
            self.checksum_then_send(bytes([0x8B, 0x00, 0x00, 0x00, preset_number]))

    def subscribe(self, node_addr: bytes | bytearray, index_device: int, index_input: int, index_output: int, index_param: int):
        event = b"\x89"
        s_v = self.get_sv(index_device, index_input, index_output, index_param)
        index_param = self.meter_subscription_rate if index_param == LondonParam.METER else 0
        my_data = bytes([0x00, 0x00, 0x00, index_param])
        # ---------------------------------------------------------------------------- #
        self.states.set_state(bytes(node_addr + s_v), int.from_bytes(my_data, "big", signed=True))
        # ---------------------------------------------------------------------------- #
        if s_v != -1:
            self.checksum_then_send(bytes(event + node_addr + s_v + my_data))

    def unsubscribe(self, node_addr: bytes | bytearray, index_device: int, index_input: int, index_output: int, index_param: int):
        event = b"\x8a"
        s_v = self.get_sv(index_device, index_input, index_output, index_param)
        index_param = self.meter_subscription_rate if index_param == LondonParam.METER else 0
        my_data = bytes([0x00, 0x00, 0x00, index_param])
        # ---------------------------------------------------------------------------- #
        self.states.remove_state(bytes(node_addr + s_v))
        # ---------------------------------------------------------------------------- #
        if s_v != -1:
            self.checksum_then_send(bytes(event + node_addr + s_v + my_data))

    # def _unsubscribe_percent(self, node_addr: bytes | bytearray, index_device: int, index_input: int, index_output: int, index_param: int):
    #     event = b"\x8f"
    #     s_v = self.get_sv(index_device, index_input, index_output, index_param)
    #     index_param = self.meter_subscription_rate if index_param == LondonParam.METER else 0
    #     my_data = bytes([0x00, 0x00, 0x00, index_param])
    #     # ---------------------------------------------------------------------------- #
    #     # self.feedback[] = None
    #     self.states.remove_state(bytes(node_addr + s_v))
    #     # ---------------------------------------------------------------------------- #
    #     if s_v != -1:
    #         self.checksum_then_send(bytes(event + node_addr + s_v + my_data))
    # ---------------------------------------------------------------------------- #
    def get_sv(self, index_device, index_input, index_output, index_param) -> bytes:
        sv = -1
        # ---------------------------------------------------------------------------- #
        if index_device == LondonDev.LOGIC_SOURCE:
            if index_param == LondonParam.LOGIC_SOURCE:
                sv = 1
        # ---------------------------------------------------------------------------- #
        elif index_device == LondonDev.LOGIC_END:
            if index_param == LondonParam.LOGIC_END:
                sv = 0
        # ---------------------------------------------------------------------------- #
        elif index_device == LondonDev.AUTOMIXER or index_device == LondonDev.MIXER:
            #
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
            elif index_param == LondonParam.GROUP:
                sv = (index_input - 1) * 100 + (index_output - 1) + 40
        # ---------------------------------------------------------------------------- #
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
        # ---------------------------------------------------------------------------- #
        elif index_device == LondonDev.ROUTER or index_device == LondonDev.MATRIX_MIXER:
            if index_param == LondonParam.MUTE or index_param == LondonParam.UNMUTE:
                sv = (index_input - 1) + ((index_output - 1) * 128)
            elif index_param == LondonParam.GAIN:
                sv = (index_input + 16383) + ((index_output - 1) * 128)
        # ---------------------------------------------------------------------------- #
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
        # ---------------------------------------------------------------------------- #
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
        # ---------------------------------------------------------------------------- #
        elif index_device == LondonDev.SOURCE_SELECTOR:
            sv = 0
        # ---------------------------------------------------------------------------- #
        elif index_device == LondonDev.SOURCE_MATRIX:
            sv = index_input - 1
        # ---------------------------------------------------------------------------- #
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
        # ---------------------------------------------------------------------------- #
        elif index_device == LondonDev.OUTPUT_CARD:
            if index_param == LondonParam.METER:
                sv = (index_input - 1) * 4
            elif index_param == LondonParam.REFERENCE:
                sv = (index_input - 1) * 4 + 1
            elif index_param == LondonParam.ATTACK:
                sv = (index_input - 1) * 4 + 2
            elif index_param == LondonParam.RELEASED:
                sv = (index_input - 1) * 4 + 3
        # ---------------------------------------------------------------------------- #
        elif index_device == LondonDev.METER:
            if index_param == LondonParam.METER:
                sv = 0
        # ---------------------------------------------------------------------------- #
        return sv.to_bytes(2, "big")

    # ---------------------------------------------------------------------------- #
    def check_special_char(self, data: int) -> bool:
        return data in (0x02, 0x03, 0x06, 0x15, 0x1B)

    def checksum_then_send(self, my_string: bytes | bytearray):
        try:
            send = bytearray()
            CS = 0
            for b in my_string:
                CS = CS ^ b
                if self.check_special_char(b):
                    send.extend([0x1B, (b + 128) & 0xFF])
                else:
                    send.extend([b])
            # ---------------------------------------------------------------------------- #
            if self.check_special_char(CS):
                send = b"\x02" + send + bytes([0x1B, (CS + 128) & 0xFF]) + b"\x03"
            else:
                send = b"\x02" + send + bytes([CS]) + b"\x03"
            self.dv.send(send)
        except Exception as e:
            self.log_error(f"checksum_then_send exception: {e}")

    def parse_buffer(self):
        if self.buffer.startswith(b"\x06"):
            while self.buffer and self.buffer[0] == 0x06:
                self.buffer.pop(0)
        elif self.buffer.startswith(b"\x15"):
            self.buffer.pop(0)
        elif self.buffer.startswith(b"\x02"):
            end_index = self.buffer.find(b"\x03")
            if end_index != -1:
                message = self.buffer[1:end_index]
                self.buffer = self.buffer[end_index + 1 :]  # Remove the processed message from the self.buffer
                self.log_debug(f"Message extracted: {message.hex()} Remaining buffer: {self.buffer.hex()}")
                self.check_message_attemps = 0
                # ---------------------------------------------------------------------------- #
                temp = bytearray(message)
                i = 0
                # ---------------------------------------------------------------------------- #
                while i < len(temp):
                    if temp[i] == 0x1B and i + 1 < len(temp):
                        temp[i] = temp[i + 1] - 128
                        temp.pop(i + 1)
                    i += 1
                # ---------------------------------------------------------------------------- #
                r_cs = 0
                for b in temp[:-1]:
                    r_cs = r_cs ^ b
                # ---------------------------------------------------------------------------- #
                if r_cs == temp[-1]:
                    self.process_feedback(temp[:-1])  # chksum 빼고 나머지 전달
            else:
                self.check_message_attemps += 1
                if self.check_message_attemps > 5:
                    self.buffer.clear()
                    self.check_message_attemps = 0

    def process_feedback(self, received_string: bytes | bytearray):
        event = bytes([received_string[0]])
        node = received_string[1:3]
        vd = bytes([received_string[3]])
        node_addr = received_string[4:7]
        s_v = received_string[7:9]
        my_data = received_string[-4:]
        self.log_debug(
            f"process_feedback() event={event.hex()} node={node.hex()} vd={vd.hex()} node_addr={node_addr.hex()} s_v={s_v.hex()} my_data={my_data.hex()}"
        )
        if bytes(node + vd + node_addr + s_v) in self.states.get_all_states_keys():
            self.states.set_state(bytes(node + vd + node_addr + s_v), int.from_bytes(my_data, "big", signed=True))

    # ---------------------------------------------------------------------------- #
    def check_vol_range(self, val: float) -> bool:
        return val is not None and self.MIN_VAL <= val <= self.MAX_VAL

    def val_add_unit(self, val: int) -> int:
        val_db = self.convert_value_to_db(val)
        return self.convert_db_to_value(round(val_db + self.UNIT_VAL)) if self.check_vol_range(val_db) else val

    def val_sub_unit(self, val: int) -> int:
        val_db = self.convert_value_to_db(val)
        return self.convert_db_to_value(round(val_db - self.UNIT_VAL)) if self.check_vol_range(val_db) else val

    def val_toggle(self, val: int) -> int:
        if val == 0:
            return 1
        elif val == 1:
            return 0
        else:
            return val

    # ---------------------------------------------------------------------------- #
    # 사용자 함수

    def set_gain_up(self, node_addr, index_device, index_input, index_output, index_param):
        self.set_gain(
            node_addr,
            index_device,
            index_input,
            index_output,
            index_param,
            self.val_add_unit(self.get_val_by_node_sv(node_addr, index_device, index_input, index_output, index_param)),
        )

    def set_gain_down(self, node_addr, index_device, index_input, index_output, index_param):
        self.set_gain(
            node_addr,
            index_device,
            index_input,
            index_output,
            index_param,
            self.val_sub_unit(self.get_val_by_node_sv(node_addr, index_device, index_input, index_output, index_param)),
        )

    def set_val_toggle(self, node_addr, index_device, index_input, index_output, index_param):
        self.set_val(
            node_addr,
            index_device,
            index_input,
            index_output,
            index_param,
            self.val_toggle(self.get_val_by_node_sv(node_addr, index_device, index_input, index_output, index_param)),
        )


if __name__ == "__main__":
    pass
