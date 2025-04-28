import socket
import threading
import time

from lib.networkmanager import TcpClient


def is_range(val, low, high):
    return low <= val <= high


def remove_txt_strip_chars(s, target):
    idx = s.find(target)
    if idx == -1 or len(s) <= len(target):
        return ""
    return s[: idx + len(target)]


def remove_str_strip_chars(s, target):
    idx = s.find(target)
    if idx == -1 or len(s) <= len(target):
        return ""
    result = s[: idx + len(target)]
    s = s[idx + len(target) :]
    return result


def remove_txt(s, target):
    idx = s.find(target)
    if idx == -1 or len(s) <= len(target):
        return ""
    return s[: idx + len(target)]


def remove_str(s, target):
    idx = s.find(target)
    if idx == -1 or len(s) <= len(target):
        return ""
    result = s[: idx + len(target)]
    s = s[idx + len(target) :]
    return result


def find_str(s, target):
    return target in s


# PROGRAM_NAME = "large_hall_yamaha"
# NUM_CH = 36
# IP_YAMAHA = "192.168.1.14"
# PORT_YAMAHA = 49280
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


class YamahaController:
    CMD_RES_OK = "OK"
    CMD_RES_OKM = "OKm"
    CMD_RES_NOTIFY = "NOTIFY"
    CMD_PREFIX = "MIXER:Current/"
    CMD_TYPE_GAIN = "Level"
    CMD_TYPE_MUTE = "On"

    def __init__(self, name, ip, port=49280):
        self.enabled_log = True
        self.ch_address_list = []
        self.yamahaGain = []
        self.yamahaMute = []
        self.online = False
        self.buffer = ""
        # 소켓 통신을 위한 속성 (필요에 따라 구현)
        self.name = name
        self.ip = ip
        self.port = port
        self.client = TcpClient(self.name, self.ip, self.port)

    # 시작 시 호출하는 함수 (연결 및 버퍼 생성 등)
    def init(self):
        self.client.add_event_handler("received", self.parse_response)
        self.client.connect()

    def log_yamaha(self, *args):
        if self.enabled_log:
            print("[YamahaController Log]:", *args)

    # ---------------------------------------------------------------------------- #
    def compare_value_with_lut(self, arr, val):
        n = len(arr)
        if n < 2:
            return 1
        if val <= arr[0]:
            self.log_yamaha("compare_value_with_lut() :: value is below than idx 1")
            return 1
        if val >= arr[-1]:
            self.log_yamaha("compare_value_with_lut() :: value is upper than idx max")
            return n
        low = 0
        high = n - 1
        while low <= high:
            mid = (low + high) // 2
            if val < arr[mid]:
                high = mid - 1
            elif val >= arr[mid] and val < arr[mid + 1]:
                self.log_yamaha("result=", mid + 1)
                return mid + 1  # 1-based index
            elif val >= arr[mid + 1]:
                low = mid + 1
        return 0

    def connect(self):
        self.log_yamaha(f"Opening connection: {self.ip}:{self.port}")
        # 예시: TCP 소켓 생성 (필요 시 예외 처리 추가)
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect((self.ip, self.port))
            self.online = True
            self.thread_receive_loop = threading.Thread(target=self.receive_loop, daemon=True)
            self.thread_receive_loop.init()
            self.log_yamaha("연결 성공")
        except Exception as e:
            self.online = False
            self.log_yamaha("연결 실패:", e)

    def addr_to_idx(self, address: str):
        if address in self.ch_address_list:
            idx = self.ch_address_list.index(address)
            self.log_yamaha("address의 인덱스는:", idx)
            return idx

    def idx_to_addr(self, idx: int):
        try:
            return self.ch_address_list[idx - 1]
        except IndexError as e:
            self.log_yamaha("idx_to_addr() :: IndexError for idx", idx, ":", e)

    # def ch_to_type(self, idxch: int):
    #     if is_range(idxch, 1, self.NUM_CH):
    #         return "InCh/Fader/"
    #     else:
    #         return "\n"
    def send(self, data: str):
        msg = f"set {self.CMD_PREFIX}{data}\n"
        self.log_yamaha(f"send() :: {msg=}")
        self.client.send(msg.encode())

    def set_gain(self, idx: int, val: int):
        self.log_yamaha(f"set_gain() {idx=} {val=}")
        if is_range(val, 1, 100):
            # self.yamahaGain[idx] = val
            gain_db = YAMAHA_GAIN_LUT[val - 1]  # 1-based idx_val -> 0-based index
            msg = f"{self.idx_to_addr(idx)} {self.CMD_TYPE_GAIN} 0 {str(gain_db)}"
            self.send(msg)

    def set_mute(self, idx: int, val: int):
        self.log_yamaha(f"set_mute() {idx=} {val=}")
        # self.yamahaMute[idx] = bool(val)
        # 반전 값을 전송 (원본 코드에서 itoa(!val))
        mute_val = 0 if val else 1
        msg = f"{self.idx_to_addr(idx)} {self.CMD_TYPE_MUTE} 0 {mute_val}"
        self.send(msg)

    # ---------------------------------------------------------------------------- #
    def parse_response(self, evt):
        # ---------------------------------------------------------------------------- #
        data = evt.arguments["data"].decode().split()
        self.log_yamaha(f"parse_response() :: {data=} {type(data)=}")

        for i in range(len(data)):
            print(data[i])
        # # str_ack = remove_str_strip_chars(msg, "$20")
        # if data[0] not in [self.CMD_RES_OK, self.CMD_RES_NOTIFY]:
        #     return
        # # ---------------------------------------------------------------------------- #
        # if data[1] != "set":
        #     return
        # if remove_str(msg, self.CMD_PREFIX) != self.CMD_PREFIX:
        #     return
        # # # 스테레오 채널 제외 처리 예시
        # # if find_str(msg, "St/"):
        # #     return
        # # ch_type = remove_str_strip_chars(msg, "/Fader/")
        # # idxch = self.addr_to_idx(ch_type)
        # # ctrl_type 추출 (공백 제거 후 남은 문자열)
        # ctrl_type = remove_str_strip_chars(msg, "$20")
        # # 채널 인덱스 보정 (단순 예시)
        # try:
        #     extra_idx = int(remove_str_strip_chars(msg, "$20"))
        # except:
        #     extra_idx = 0
        # idxch = idxch + extra_idx
        # if remove_str_strip_chars(msg, "$20") != "0":
        #     return
        # if not idxch or idxch > self.NUM_CH:
        #     return
        # try:
        #     raw_val = int(remove_str_strip_chars(msg, "$20"))
        # except:
        #     raw_val = 0
        # if ctrl_type == self.CMD_TYPE_GAIN:
        #     idx_val = self.compare_value_with_lut(YAMAHA_GAIN_LUT, raw_val)
        #     if idx_val:
        #         self.yamahaGain[idxch] = idx_val
        #         self.log_yamaha("parse_response() :: gain idx_val ::", idx_val)
        # elif ctrl_type == self.CMD_TYPE_MUTE:
        #     if raw_val == 1:
        #         self.yamahaMute[idxch] = False
        #         self.log_yamaha("parse_response() :: mute val ::", raw_val)
        #     elif raw_val == 0:
        #         self.yamahaMute[idxch] = True
        #         self.log_yamaha("parse_response() :: mute val ::", raw_val)

    def create_buffer(self):
        self.buffer = ""

    def clear_buffer(self):
        self.buffer = ""

    def receive_loop(self):
        # 실제 소켓에서 데이터 수신하는 루프 (예시)
        while True:
            print("receive loop")
            if self.client:
                try:
                    data = self.client.recv(2048)
                    if not data:
                        self.handle_offline()
                        break
                    # 수신된 데이터를 문자열로 변환하여 버퍼에 추가
                    self.buffer += data.decode()
                    # "$0A" 단위로 메시지를 파싱 (라인 피드 기준)
                    print(self.buffer)
                    while "0x0A" in self.buffer:
                        msg, self.buffer = self.buffer.split("0x0A")
                        self.parse_response(msg)
                except Exception as e:
                    self.log_yamaha("receive_loop 에러:", e)
                    self.handle_error()
            time.sleep(0.05)


# 테스트 실행 예시
if __name__ == "__main__":
    controller = YamahaController("yamaha_controller", "10.20.0.107")
    controller.ch_address_list.append("St/Fader/ 0")
    controller.init()
    # 임시 테스트: 게인 및 뮤트 설정
    controller.set_gain(1, 10)
    controller.set_mute(1, 1)
    # 연결 및 데이터 수신이 비동기로 동작하므로 메인 스레드는 대기
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("종료합니다.")
