# 마지막 수정일 : 20260514
from lib.event_manager import EventManager
from lib.network_manager import DEFAULT_UDP_CLIENT_RECONNECT_TIME, UdpClient
from lib.utility import CommonLogger, handle_exception


# todo : 입/출력 인덱스 ENUM 만들기
class AtemSwitcher(CommonLogger, EventManager):
    DEFAULT_PORT = 9910
    HEADERCMD_ACKREQUEST = 0x01
    HEADERCMD_HELLOPACKET = 0x02
    HEADERCMD_RESEND = 0x04
    HEADERCMD_REQUESTNEXTAFTER = 0x08
    HEADERCMD_ACK = 0x10
    ATEM_NO_INPUT = 0xFFFF
    MAX_INIT_PACKAGE_COUNT = 40

    def __init__(self, ip, port=DEFAULT_PORT, reconnect_time=DEFAULT_UDP_CLIENT_RECONNECT_TIME):
        super().__init__("pgm_switched", "aux_switched", "pvw_switched", "cut", "auto", "connected", "disconnected")
        self.dv = UdpClient(ip, port, reconnect_time=reconnect_time)
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.program_input = 0
        self.preview_input = 0
        self.aux_inputs = [0] * 8
        self.packet_buffer = bytearray(96)
        self.initial_buffer = bytearray()
        self.input_count = 0
        self.local_packet_id_counter = 0
        self.init_payload_sent = False
        self.initialized = False
        self.session_id = 0x53AB
        self.missed_initialization_packages = [0xFF] * 6
        self.init_payload_sent_at_packet_id = self.MAX_INIT_PACKAGE_COUNT
        self.last_remote_packet_id = 0
        self.return_package_length = 0
        self.connected = False
        self.initialized = False
        self.waiting_for_incoming = False
        self._init_done = False

    @handle_exception
    def _reset_connection_state(self):
        self.packet_buffer = bytearray(96)
        self.initial_buffer = bytearray()
        self.input_count = 0
        self.local_packet_id_counter = 0
        self.init_payload_sent = False
        self.initialized = False
        self.session_id = 0x53AB
        self.missed_initialization_packages = [0xFF] * 6
        self.init_payload_sent_at_packet_id = self.MAX_INIT_PACKAGE_COUNT
        self.connected = False
        self.initialized = False
        self.waiting_for_incoming = False

    @handle_exception
    def init(self):
        if self._init_done:
            return
        self._init_done = True
        self.dv.on("connected", self._handle_dv_connected)
        self.dv.on("disconnected", self._handle_dv_disconnected)
        self.dv.receive.listen(self._handle_dv_receive)
        self.dv.connect()

    @handle_exception
    def _handle_dv_connected(self, *_args, **_kwargs):
        self._reset_connection_state()
        self.say_hello()

    @handle_exception
    def _handle_dv_disconnected(self, *_args, **_kwargs):
        was_connected = self.connected
        self._reset_connection_state()
        if was_connected:
            self.emit("disconnected")

    @handle_exception
    def _handle_dv_receive(self, evt):
        data = evt.arguments.get("data", b"")
        self.log_debug(f"received {data}")
        self.parse_data(data)

    @handle_exception
    def say_hello(self):
        self.clear_packet_buffer()
        self.create_command_header(self.HEADERCMD_HELLOPACKET, 20)
        self.packet_buffer[12] = 0x01
        self.packet_buffer[9] = 0x03
        self.send_packet_buffer(20)

    @handle_exception
    def parse_data(self, data):
        if len(data) < 12:
            self.log_debug(f"parse_data() : packet too short {len(data)=}")
            return
        self.waiting_for_incoming = False
        packet_size = len(data)
        packet_length = (data[0] & 0x07) << 8 | data[1]
        if packet_length > packet_size:
            self.log_debug(f"parse_data() : incomplete packet {packet_size=} {packet_length=}")
            return
        self.session_id = data[2] << 8 | data[3]
        header = data[0] >> 3
        self.last_remote_packet_id = data[10] << 8 | data[11]
        self.log_debug(f"parse_data() : {packet_size=} {packet_length=} {self.session_id=:04x} {self.last_remote_packet_id=:04x}")
        # note : phase 1
        if self.last_remote_packet_id < self.MAX_INIT_PACKAGE_COUNT:
            self.missed_initialization_packages[self.last_remote_packet_id >> 3] = self.missed_initialization_packages[
                self.last_remote_packet_id >> 3
            ] & ~(1 << (self.last_remote_packet_id & 0x07))
        # note : phase 2
        if header & self.HEADERCMD_RESEND:
            self.log_debug("parse_data() : resent packet")
        # note : phase 3
        if header & self.HEADERCMD_HELLOPACKET:
            self.log_debug("parse_data() : hello packet received")
            self.connected = True
            self.clear_packet_buffer()
            if packet_size > 12 and data[12] == 0x04:
                self.log_debug("parse_data() : disconnect requested")
                self.dv.disconnect()
            else:
                self.create_command_header(self.HEADERCMD_ACK, 12)
                self.packet_buffer[9] = 0x03
                self.send_packet_buffer(12)
        # note : phase 4
        if not self.init_payload_sent and packet_size == 12 and self.last_remote_packet_id > 1:
            self.init_payload_sent = True
            self.init_payload_sent_at_packet_id = self.last_remote_packet_id
        # note : phase 5
        if not self.init_payload_sent and not (header & self.HEADERCMD_HELLOPACKET) and not (header & self.HEADERCMD_RESEND) and packet_size > 12:
            self.initial_buffer.extend(data[12:packet_size])
        # note : phase 6
        if self.init_payload_sent and (header & self.HEADERCMD_ACKREQUEST) and (self.initialized or not (header & self.HEADERCMD_RESEND)):
            self.clear_packet_buffer()
            self.create_command_header_id(self.HEADERCMD_ACK, 12, self.last_remote_packet_id)
            self.packet_buffer[9] = 0x47
            if header & self.HEADERCMD_RESEND:
                self.debug_print("resend ack: ", self.packet_buffer)
            self.send_packet_buffer(12)
        # note : phase 7
        if self.initialized and not (header & self.HEADERCMD_HELLOPACKET) and not (header & self.HEADERCMD_RESEND) and packet_length > 12:
            self.parse_packet(data[12:packet_size])
        # note : phase 8
        if not self.initialized and self.init_payload_sent and not self.waiting_for_incoming:
            for packet_id in range(self.init_payload_sent_at_packet_id):
                if self.missed_initialization_packages[packet_id >> 3] & (0x01 << (packet_id & 0x07)):
                    self.clear_packet_buffer()
                    self.create_command_header(self.HEADERCMD_REQUESTNEXTAFTER, 12)
                    previous_packet_id = (packet_id - 1) & 0xFFFF
                    self.packet_buffer[5] = previous_packet_id >> 8
                    self.packet_buffer[6] = previous_packet_id & 0xFF
                    self.packet_buffer[7] = 0x01
                    self.send_packet_buffer(12)
                    self.waiting_for_incoming = True
                    break
            if not self.waiting_for_incoming:
                self.parse_packet(self.initial_buffer)
                self.initialized = True
                self.waiting_for_incoming = True
                self.initial_buffer = bytearray()
                self.emit("connected")
            self.log_debug("parse_data() : atem initialized")

    @handle_exception
    def parse_packet(self, data):
        counter = 0
        try:
            len_data = len(data)
            index_pointer = 0
            command_string = ""
            command_length = 0
            # input_port_id = 0
            # packet_id = 0
            # switcher_input_long_name = ""
            # switcher_input_short_name = ""
            # temp_input_count = 0
            # print(f"{len(command_string)=}, {command_string= } {command_string.decode()=}")
            while index_pointer < len_data and counter < 99:
                if index_pointer + 2 > len_data:
                    break
                command_length = (data[index_pointer] << 8) | data[index_pointer + 1]
                self.log_debug(f"{index_pointer=} {len_data=} {counter=} {command_length=}")
                if command_length <= 8 or index_pointer + command_length > len_data:
                    break
                if command_length > 8:
                    command_string = data[index_pointer + 4 : index_pointer + 4 + 4]
                    self.log_debug(f"{command_length=} {command_string=}")
                    decoded_command = command_string.decode(errors="ignore")
                    if decoded_command.find("PrgI") != -1 and command_length >= 12:
                        self.program_input = data[index_pointer + 10] << 8 | data[index_pointer + 11]
                        self.log_debug(f"parse_packet() : Program Input: {self.program_input}")
                        self.emit("pgm_switched", self.program_input)
                    elif decoded_command.find("PrvI") != -1 and command_length >= 12:
                        self.preview_input = data[index_pointer + 10] << 8 | data[index_pointer + 11]
                        self.log_debug(f"parse_packet() : {self.preview_input=}")
                        self.emit("pvw_switched", self.preview_input)
                    elif decoded_command.find("AuxS") != -1 and command_length >= 13:
                        aux_index = int(data[index_pointer + 8])
                        if 0 <= aux_index <= 7:
                            self.aux_inputs[aux_index] = data[index_pointer + 11] << 8 | data[index_pointer + 12]
                            self.log_debug(f"parse_packet() : Aux Input {aux_index}: {self.aux_inputs[aux_index]}")
                            self.emit("aux_switched", self.aux_inputs[aux_index])
                    elif decoded_command.find("InPr") != -1:
                        # todo 이름 가져오기 구현
                        pass
                    # elif decoded_command.find("DCut") != -1:
                    #     self.log_debug(f"Cut!")
                    #     self.emit("cut")
                    # elif decoded_command.find("DAut") != -1:
                    #     self.log_debug(f"Auto!")
                    #     self.emit("auto")
                else:
                    break
                index_pointer += command_length
                counter += 1
        except Exception as e:
            self.log_error(f"parse_packet error.. {e=}")
        finally:
            counter = 0
            index_pointer = 0

    @handle_exception
    def clear_packet_buffer(self):
        self.packet_buffer = bytearray(96)
        for i in range(96):
            self.packet_buffer[i] = 0

    @handle_exception
    def create_command_header(self, header_command, data_length):
        self.create_command_header_id(header_command, data_length, 0)

    @handle_exception
    def create_command_header_id(self, header_command, data_length, remote_packet_id):
        self.log_debug(f"create_command_header_id() : {remote_packet_id=}")
        self.packet_buffer[0] = (header_command << 3) | ((data_length >> 8) & 0x07)  # cmd mask
        self.packet_buffer[1] = data_length & 0xFF  # length LSB
        self.packet_buffer[2] = self.session_id >> 8  # Session ID
        self.packet_buffer[3] = self.session_id & 0xFF  # Session ID
        self.packet_buffer[4] = remote_packet_id >> 8  # Remote Packet ID, MSB
        self.packet_buffer[5] = remote_packet_id & 0xFF  # Remote Packet ID, LSB
        if not (header_command & (self.HEADERCMD_HELLOPACKET | self.HEADERCMD_ACK | self.HEADERCMD_REQUESTNEXTAFTER)):
            self.local_packet_id_counter += 1
            self.packet_buffer[10] = self.local_packet_id_counter >> 8  # Local Packet ID, MSB
            self.packet_buffer[11] = self.local_packet_id_counter & 0xFF  # Local Packet ID, LSB

    @handle_exception
    def prepare_command_packet(self, command_string: str):
        if len(command_string) != 4:
            self.log_error(f"prepare_command_packet() : command must be 4 chars {command_string=}")
            return
        self.clear_packet_buffer()
        self.return_package_length = 12 + 4 + 4 + len(command_string)
        self.log_debug(f"prepare_command_packet() :     {self.return_package_length=}")
        self.packet_buffer[12] = 0
        self.packet_buffer[13] = 4 + 4 + len(command_string)
        self.packet_buffer[16] = ord(command_string[0])
        self.packet_buffer[17] = ord(command_string[1])
        self.packet_buffer[18] = ord(command_string[2])
        self.packet_buffer[19] = ord(command_string[3])
        self.log_debug(f"prepare_command_packet() : {self.packet_buffer[16:20]=}")
        self.debug_print("prepare_command_packet()", self.packet_buffer)

    @handle_exception
    def finish_command_packet(self):
        self.create_command_header(self.HEADERCMD_ACKREQUEST, self.return_package_length)
        self.debug_print("finish_command_packet()", self.packet_buffer)
        self.send_packet_buffer(self.return_package_length)
        self.return_package_length = 0

    @handle_exception
    def send_packet_buffer(self, return_package_length):
        self.debug_print("send_packet_buffer()", self.packet_buffer[:return_package_length])
        self.dv.send(self.packet_buffer[:return_package_length])

    @handle_exception
    def debug_print(self, str_message, bytes_message):
        self.log_debug(f"{str_message=} LENGTH: {len(bytes_message)}")
        self.log_debug(f"Hex: {' '.join(f'{b:02x}' for b in bytes_message)}")

    def _is_valid_input_id(self, input_id):
        return isinstance(input_id, int) and 0 <= input_id <= self.ATEM_NO_INPUT

    @handle_exception
    def set_program_input(self, input_id):
        if not self._is_valid_input_id(input_id):
            self.log_error(f"set_program_input() : invalid {input_id=}")
            return
        self.program_input = input_id
        self.prepare_command_packet("CPgI")
        self.packet_buffer[12 + 4 + 4 + 0] = 0
        self.packet_buffer[12 + 4 + 4 + 2] = (input_id >> 8) & 0xFF
        self.packet_buffer[12 + 4 + 4 + 3] = input_id & 0xFF
        self.finish_command_packet()
        self.program_input = input_id

    @handle_exception
    def set_preview_input(self, input_id):
        if not self._is_valid_input_id(input_id):
            self.log_error(f"set_preview_input() : invalid {input_id=}")
            return
        self.prepare_command_packet("CPvI")
        self.packet_buffer[12 + 4 + 4 + 0] = 0
        self.packet_buffer[12 + 4 + 4 + 2] = (input_id >> 8) & 0xFF
        self.packet_buffer[12 + 4 + 4 + 3] = input_id & 0xFF
        self.finish_command_packet()
        self.preview_input = input_id

    @handle_exception
    def set_aux_input(self, aux_index, input_id):
        if not (isinstance(aux_index, int) and 1 <= aux_index <= 8):
            self.log_error(f"set_aux_input() : invalid {aux_index=}")
            return
        if not self._is_valid_input_id(input_id):
            self.log_error(f"set_aux_input() : invalid {input_id=}")
            return
        internal_aux_index = aux_index - 1
        self.aux_inputs[internal_aux_index] = input_id
        self.prepare_command_packet("CAuS")
        self.packet_buffer[12 + 4 + 4 + 0] = 0
        self.packet_buffer[12 + 4 + 4 + 1] = internal_aux_index
        self.packet_buffer[12 + 4 + 4 + 2] = input_id >> 8
        self.packet_buffer[12 + 4 + 4 + 3] = input_id & 0xFF
        self.finish_command_packet()

    @handle_exception
    def perform_cut(self):
        self.prepare_command_packet("DCut")
        self.finish_command_packet()

    @handle_exception
    def perform_auto(self):
        self.prepare_command_packet("DAut")
        self.finish_command_packet()


# 사용 예시
# if __name__ == "__main__":
#     atem_switcher = AtemSwitcher("10.20.0.88")
#     TP = context.devices.get("AMX-10001")
#     atem_switcher.connect()
#     # atem_switcher.set_program_input(1)
#     # atem_switcher.set_preview_input(2)
#     # atem_switcher.set_aux_input(1, 3)
#     # atem_switcher.perform_cut()
#     # atem_switcher.perform_auto()
#     add_btn(TP, 1, 1, "push", atem_switcher.perform_cut)
#     add_btn(TP, 1, 1, "release", lambda: atem_switcher.emit("cut"))
#     add_btn(TP, 1, 2, "push", atem_switcher.perform_auto)
#     for idx in range(5):
#         add_btn(TP, 1, 11 + idx, "push", lambda idx=idx: atem_switcher.set_program_input(idx))
#         add_btn(TP, 1, 21 + idx, "push", lambda idx=idx: atem_switcher.set_preview_input(idx))
#     def handle_pgm_switched(*args):
#         tp_set_btn(TP, 1, 11, args[0] == 0)
#         tp_set_btn(TP, 1, 12, args[0] == 1)
#         tp_set_btn(TP, 1, 13, args[0] == 2)
#         tp_set_btn(TP, 1, 14, args[0] == 3)
#     def handle_pvw_switched(*args):
#         tp_set_btn(TP, 1, 21, args[0] == 0)
#         tp_set_btn(TP, 1, 22, args[0] == 1)
#         tp_set_btn(TP, 1, 23, args[0] == 2)
#         tp_set_btn(TP, 1, 24, args[0] == 3)
#     atem_switcher.on("pgm_switched", handle_pgm_switched)
#     atem_switcher.on("pvw_switched", handle_pvw_switched)
#     def cut_btn_effect():
#         print("cut btn effect !")
#         def off_cut_btn():
#             tp_set_btn(TP, 1, 1, False)
#         @pulse(0.4, off_cut_btn)
#         def on_cut_btn():
#             tp_set_btn(TP, 1, 1, True)
#         on_cut_btn()
#     atem_switcher.on("cut", cut_btn_effect)
