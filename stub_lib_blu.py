# 상수 정의
BLU_CONNECT_DELAY = 100

BLU_CHAR_STX = 0x02
BLU_CHAR_ETX = 0x03
BLU_CHAR_ACK = 0x06
BLU_CHAR_NAK = 0x15
BLU_CHAR_ESC = 0x1B
BLU_CHAR_ET = 0x88

# 디바이스 상수
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

# 파라미터 상수
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
BLU_PARAM_LOGIC_SOURCE = 0
BLU_PARAM_LOGIC_END = 1

# 믹서 파라미터 상수
BLU_PARAM_SOLO = 13
BLU_PARAM_GROUP = 14
BLU_PARAM_AUX = 15
BLU_PARAM_OVERRIDE = 16
BLU_PARAM_AUTO = 17
BLU_PARAM_AUX_GAIN = 18
BLU_PARAM_PAN = 19
BLU_PARAM_OFF_GAIN = 20
BLU_PARAM_GROUP_GAIN = 21

# 룸 컴바인 파라미터 상수
BLU_PARAM_SOURCE_MUTE = 30
BLU_PARAM_BGM_MUTE = 31
BLU_PARAM_MASTER_MUTE = 32
BLU_PARAM_SOURCE_GAIN = 33
BLU_PARAM_BGM_GAIN = 34
BLU_PARAM_MASTER_GAIN = 35
BLU_PARAM_BGM_SELECT = 36
BLU_PARAM_PARTITION = 37

# 전화 파라미터 상수
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

# 프리셋 파라미터 상수
BLU_PARAM_DEVICE_PRESET = 1
BLU_PARAM_PARAMETER_PRESET = 2

# 입력 카드 및 출력 카드 파라미터 상수
BLU_PARAM_PHANTOM = 22
BLU_PARAM_REFERENCE = 23
BLU_PARAM_ATTACK = 24
BLU_PARAM_RELEASED = 25

# 일반 형식 상수
BLU_PARAM_A = 1
BLU_PARAM_B = 2
BLU_PARAM_C = 3
BLU_PARAM_D = 4

# 입력 카드 표기
BLU_PARAM_L = 1
BLU_PARAM_R = 3


class BLU:
    def __init__(self, ip_address):
        # 메시지 처리 시도 횟수
        self.message_attemps = 0
        # 디버그 플래그
        self.debug = 0
        # 통신 포트 버퍼
        self.buffer = bytearray(10000)
        # ---------------------------------------------------------------------------- #
        self.subscribed = False
        # ---------------------------------------------------------------------------- #
        self.data = None
        # ---------------------------------------------------------------------------- #
        self.socket = None

        # ---------------------------------------------------------------------------- #
        def get_sv(self, device, input, output, param):
            def error_message():
                print(
                    "BLU_ERROR :: Set Val - PARAM TYPE NOT FOUND FOR DEVICE. SEE HELP FILE FOR SUPPORTED MESSAGE TYPES"
                )
                return 65535

            param_map = {
                BLU_DEV_LOGIC_SOURCE: {BLU_PARAM_LOGIC_SOURCE: 1},
                BLU_DEV_LOGIC_END: {BLU_PARAM_LOGIC_END: 0},
                BLU_DEV_AUTOMIXER: {
                    BLU_PARAM_MUTE: 1 + ((input - 1) * 100) if input != 0 and output == 0 else 20000 + output,
                    BLU_PARAM_GAIN: (input - 1) * 100 if input != 0 and output == 0 else 20000 + output - 1,
                    BLU_PARAM_SOLO: (input - 1) * 100 + 4,
                    BLU_PARAM_OVERRIDE: (input - 1) * 100 + 5,
                    BLU_PARAM_AUTO: (input - 1) * 100 + 7,
                    BLU_PARAM_PAN: (input - 1) * 100 + 2,
                    BLU_PARAM_OFF_GAIN: (input - 1) * 100 + 6,
                    BLU_PARAM_AUX: (output - 1) * 10 + 10002,
                    BLU_PARAM_GROUP: (output - 1) * 10 + 11001,
                    BLU_PARAM_AUX_GAIN: (output - 1) * 10 + 10001,
                    BLU_PARAM_GROUP_GAIN: (output - 1) * 10 + 11000,
                },
                BLU_DEV_ROOM_COMBINE: {
                    BLU_PARAM_SOURCE_MUTE: (input - 1) * 50 + 256,
                    BLU_PARAM_BGM_MUTE: (input - 1) * 50 + 258,
                    BLU_PARAM_SOURCE_GAIN: (input - 1) * 50 + 255,
                    BLU_PARAM_BGM_GAIN: (input - 1) * 50 + 257,
                    BLU_PARAM_BGM_SELECT: (input - 1) * 50 + 259,
                    BLU_PARAM_PARTITION: input - 1,
                    BLU_PARAM_GROUP: (input - 1) * 50 + 250,
                    BLU_PARAM_MASTER_MUTE: (output - 1) * 50 + 254,
                    BLU_PARAM_MASTER_GAIN: (output - 1) * 50 + 252,
                },
                BLU_DEV_ROUTER: {
                    BLU_PARAM_MUTE: (input - 1) + ((output - 1) * 128),
                    BLU_PARAM_UNMUTE: (input - 1) + ((output - 1) * 128),
                    BLU_PARAM_GAIN: (input + 16383) + ((output - 1) * 128),
                },
                BLU_DEV_MM: {
                    BLU_PARAM_MUTE: (input - 1) + ((output - 1) * 128),
                    BLU_PARAM_UNMUTE: (input - 1) + ((output - 1) * 128),
                    BLU_PARAM_GAIN: (input + 16383) + ((output - 1) * 128),
                },
                BLU_DEV_N_GAIN: {
                    BLU_PARAM_MUTE: (input - 1) + 32 if output == 0 else 97,
                    BLU_PARAM_UNMUTE: (input - 1) + 32 if output == 0 else 97,
                    BLU_PARAM_GAIN: input - 1 if output == 0 else 96,
                },
                BLU_DEV_GAIN: {
                    BLU_PARAM_MUTE: 1,
                    BLU_PARAM_UNMUTE: 1,
                    BLU_PARAM_GAIN: 0,
                    BLU_PARAM_POLARITY_ON: 2,
                    BLU_PARAM_POLARITY_OFF: 2,
                    BLU_PARAM_BUMP_UP_ON: 3,
                    BLU_PARAM_BUMP_UP_OFF: 3,
                    BLU_PARAM_BUMP_DOWN_ON: 4,
                    BLU_PARAM_BUMP_DOWN_OFF: 4,
                },
                BLU_DEV_SOURCE_SELECTOR: {BLU_PARAM_A: 0},
                BLU_DEV_SOURCE_MATRIX: {BLU_PARAM_A: input - 1},
                BLU_DEV_INPUT_CARD: {
                    BLU_PARAM_GAIN: {1: 4, 2: 10, 3: 16, 4: 22}.get(input, error_message()),
                    BLU_PARAM_METER: (input - 1) * 6,
                    BLU_PARAM_PHANTOM: (input - 1) * 6 + 5,
                    BLU_PARAM_REFERENCE: (input - 1) * 6 + 1,
                    BLU_PARAM_ATTACK: (input - 1) * 6 + 2,
                    BLU_PARAM_RELEASED: (input - 1) * 6 + 3,
                },
                BLU_DEV_OUTPUT_CARD: {
                    BLU_PARAM_METER: (input - 1) * 4,
                    BLU_PARAM_REFERENCE: (input - 1) * 4 + 1,
                    BLU_PARAM_ATTACK: (input - 1) * 4 + 2,
                    BLU_PARAM_RELEASED: (input - 1) * 4 + 3,
                },
                BLU_DEV_METER: {BLU_PARAM_METER: 0},
                BLU_DEV_TELEPHONE: {
                    BLU_PARAM_BUTTON_0: 104,
                    BLU_PARAM_BUTTON_1: 105,
                    BLU_PARAM_BUTTON_2: 106,
                    BLU_PARAM_BUTTON_3: 107,
                    BLU_PARAM_BUTTON_4: 108,
                    BLU_PARAM_BUTTON_5: 109,
                    BLU_PARAM_BUTTON_6: 110,
                    BLU_PARAM_BUTTON_7: 111,
                    BLU_PARAM_BUTTON_8: 112,
                    BLU_PARAM_BUTTON_9: 113,
                    BLU_PARAM_T_PAUSE: 116,
                    BLU_PARAM_CLEAR: 118,
                    BLU_PARAM_INTERNATIONAL: 117,
                    BLU_PARAM_BACKSPACE: 119,
                    BLU_PARAM_REDIAL: 120,
                    BLU_PARAM_FLASH: 123,
                    BLU_PARAM_TX_MUTE: 140,
                    BLU_PARAM_TX_GAIN: 141,
                    BLU_PARAM_RX_MUTE: 143,
                    BLU_PARAM_RX_GAIN: 144,
                    BLU_PARAM_DTMF_GAIN: 146,
                    BLU_PARAM_DIAL_TONE_GAIN: 148,
                    BLU_PARAM_RING_GAIN: 147,
                    BLU_PARAM_DIAL_HANGUP: 121,
                    BLU_PARAM_AUTO_ANSWER: 124,
                    BLU_PARAM_INCOMING_CALL: 122,
                    BLU_PARAM_ASTERISK: 115,
                    BLU_PARAM_POUND: 114,
                },
            }

            return param_map.get(device, {}).get(param, error_message())

    def check_special_char(self, special_char):
        special_chars = {0x02, 0x03, 0x06, 0x15, 0x1B}
        return special_char in special_chars

    def get_hi_byte(self, ibyte):
        return (ibyte >> 8) & 0xFF

    def get_low_byte(self, ibyte):
        return ibyte & 0xFF

    def scale_range(self, num_in, min_in, max_in, min_out, max_out):
        val_in = num_in / 65536
        if val_in == min_in:
            num_out = min_out
        elif val_in == max_in:
            num_out = max_out
        else:
            range_in = max_in - min_in
            range_out = max_out - min_out
            val_in = val_in - min_in
            num_out = val_in * range_out
            num_out = num_out / range_in
            num_out = num_out + min_out
            whole_num = int(num_out)
            if num_out >= 0 and ((num_out - whole_num) * 100.0) >= 50.0:
                num_out += 1
            elif num_out < 0 and ((num_out - whole_num) * 100.0) <= -50.0:
                num_out -= 1
        return int(num_out)

    def blu_set_val(self, obj, device, input, output, param, value):
        def blu_checksum_then_send(my_string):
            # Placeholder for checksum and send function
            pass

        if device in [BLU_DEV_OUTPUT_CARD, BLU_DEV_INPUT_CARD]:
            event = 0x8D
            get_event = 0x8E
            s_v = self.get_sv(device, input, output, param)
            s_vlow = self.get_low_byte(s_v)
            s_vhigh = self.get_hi_byte(s_v)
            my_data = bytearray([0x00, value, 0x00, 0x00])
        else:
            event = 0x88
            get_event = 0x89
            s_v = self.get_sv(device, input, output, param)
            s_vlow = self.get_low_byte(s_v)
            s_vhigh = self.get_hi_byte(s_v)
            my_data = bytearray([0x00, 0x00, 0x00, value])

        if s_v != 65535:
            my_string = bytearray([event]) + obj + bytearray([s_vhigh, s_vlow]) + my_data
            blu_checksum_then_send(my_string)
            my_string = bytearray([get_event]) + obj + bytearray([s_vhigh, s_vlow, 0x00, 0x00, 0x00, 0x00])
            blu_checksum_then_send(my_string)
        else:
            print("BLU_ERROR :: Set Val - SV incorrect. MESSAGE NOT SENT. SEE HELP FILE FOR SUPPORTED MESSAGE TYPES")

    def set_gain_percent(self, obj, device, input, output, percent):
        event = 0x8D
        param = BLU_PARAM_GAIN
        s_v = self.get_sv(device, input, output, param)
        s_vlow = self.get_low_byte(s_v)
        s_vhigh = self.get_hi_byte(s_v)
        my_data = bytearray([0x00, percent, 0x00, 0x00])

        if s_v != 65535:
            my_string = bytearray([event]) + obj + bytearray([s_vhigh, s_vlow]) + my_data
            self.blu_checksum_then_send(my_string)
            # THESE STATEMENTS ARE ESSENTIALLY A 'GET' STATEMENT. AFTER SENDING STRING GET_VALUE.
            # UNCOMENT NEXT TWO LINES IF THE PROGRAMMER WISHES TO RECEIVE A RESPONSE TO EVERY GAIN STRING SENT.
            my_string = bytearray([0x8E]) + obj + bytearray([s_vhigh, s_vlow, 0x00, 0x00, 0x00, 0x00])
            self.blu_checksum_then_send(my_string)
        else:
            print("BLU_ERROR :: Set Gain% - SV incorrect. MESSAGE NOT SENT. SEE HELP FILE FOR SUPPORTED MESSAGE TYPES")

    def blu_parse_buffer(self):
        GOT_ESCAPE = False
        receive = bytearray()
        r_cs = 0
        bluSixReceived = False

        if self.buffer[0] == BLU_CHAR_ACK:
            while BLU_CHAR_ACK in self.buffer:
                self.buffer.pop(0)
            if self.debug == 2:
                print("ACK")
            bluSixReceived = True
            return True

        elif self.buffer[0] == BLU_CHAR_NAK:
            self.buffer.pop(0)
            if self.debug == 2:
                print("NAK")
            return True

        elif self.buffer[0] == BLU_CHAR_STX and BLU_CHAR_ETX in self.buffer:
            self.message_attemps = 0
            temp = self.buffer[: self.buffer.index(BLU_CHAR_ETX)]
            self.buffer = self.buffer[self.buffer.index(BLU_CHAR_ETX) + 1 :]
            got_esc = False
            r_cs = ""
            t_cs = ""
            temp = temp[1:]
            if temp[-1] == BLU_CHAR_ESC:
                t_cs = temp[-1] - 128
                temp = temp[:-2]
            else:
                t_cs = temp[-1]
                temp = temp[:-1]

            for byte in temp:
                if got_esc:
                    R_SP = byte - 128
                    r_cs ^= R_SP
                    receive.append(R_SP)
                    got_esc = False
                elif byte == BLU_CHAR_ESC:
                    got_esc = True
                else:
                    r_cs ^= byte
                    receive.append(byte)

            if r_cs == t_cs:
                self.process_feedback(receive)
            elif self.debug == 2:
                print("BAD CHECKSUM OR MESSAGE LENGTH")
            return True

        elif self.buffer[0] == BLU_CHAR_STX:
            self.message_attemps += 1
            if self.message_attemps >= 5:
                self.message_attemps = 0
                self.buffer.clear()
                print("ONLY STX RECEIVED: Partial Message DUMPED")
            return False

        else:
            self.message_attemps = 0
            if len(self.buffer):
                print("UNRECOGNIZED REPLY DUMPED")
                print("LAST BLUBUFFER MESSAGE:", self.buffer)
                self.buffer.clear()
            return False
