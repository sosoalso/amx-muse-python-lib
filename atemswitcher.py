from mojo import context

from lib.eventmanager import EventManager
from lib.networkmanager import UdpClient


# ---------------------------------------------------------------------------- #
class ATEMSwitcher(EventManager):
    ATEM_PORT = 9910
    HEADERCMD_ACKREQUEST = 0x01
    HEADERCMD_HELLOPACKET = 0x02
    HEADERCMD_RESEND = 0x04
    HEADERCMD_REQUESTNEXTAFTER = 0x08
    HEADERCMD_ACK = 0x10
    ATEM_NO_INPUT = 0xFFFF
    MAX_INIT_PACKAGE_COUNT = 40

    def __init__(self, ip):
        super().__init__("pgm_switched", "aux_switched", "pvw_switched", "cut", "auto", "connected", "disconnected")
        self.debug = False
        self.ip = ip
        self.dv = UdpClient(self.ip, self.ATEM_PORT, buffer_size=2048, connection_timeout=10)
        # ---------------------------------------------------------------------------- #
        self.program_input = 0
        self.preview_input = 0
        self.aux_inputs = [0] * 8
        # ---------------------------------------------------------------------------- #
        self.packet_buffer = bytearray(96)
        self.initial_buffer = bytearray(96)
        # ---------------------------------------------------------------------------- #
        self.input_count = 0
        self.local_packet_id_counter = 0
        self.init_payload_sent = False
        self.initialized = False
        self.session_id = 0x53AB
        self.missed_initialization_packages = [0xFF] * 6
        self.init_payload_sent_at_packet_id = self.MAX_INIT_PACKAGE_COUNT
        self.last_remote_packet_id = 0
        # ---------------------------------------------------------------------------- #
        self.return_package_length = 0
        # ---------------------------------------------------------------------------- #
        self.connected = False
        self.initialized = False
        self.waiting_for_incoming = False
        self.add_event()
        self.init()

    def init(self):
        self.packet_buffer = bytearray(96)
        self.initial_buffer = bytearray(96)
        # ---------------------------------------------------------------------------- #
        self.input_count = 0
        self.local_packet_id_counter = 0
        self.init_payload_sent = False
        self.initialized = False
        self.session_id = 0x53AB
        self.missed_initialization_packages = [0xFF] * 6
        self.init_payload_sent_at_packet_id = self.MAX_INIT_PACKAGE_COUNT
        # ---------------------------------------------------------------------------- #
        self.connected = False
        self.initialized = False
        self.waiting_for_incoming = False
        # ---------------------------------------------------------------------------- #

    def add_event(self):
        def on_dv_receive(data):
            self.debug_print("received", data)
            self.parse_data(data)

        def on_dev_connect():
            self.init()
            self.say_hello()

        self.dv.on("connected", on_dev_connect)
        self.dv.receive.listen(lambda evt: on_dv_receive(evt.arguments["data"]))

    def connect(self):
        self.init()
        self.dv.connect()

    def disconnect(self):
        self.dv.disconnect()

    def say_hello(self):
        self.clear_packet_buffer()
        self.create_command_header(self.HEADERCMD_HELLOPACKET, 20)
        self.packet_buffer[12] = 0x01
        self.packet_buffer[9] = 0x03
        self.send_packet_buffer(20)

    def parse_data(self, data):
        self.waiting_for_incoming = False
        packet_size = len(data)
        packet_length = (data[0] & 0x07) << 8 | data[1]
        self.session_id = data[2] << 8 | data[3]
        header = data[0] >> 3
        self.last_remote_packet_id = data[10] << 8 | data[11]
        context.log.debug(
            f"{self.__class__.__name__} parse_data() {packet_size=} {packet_length=} {self.session_id=:04x} {self.last_remote_packet_id=:04x}"
        )
        # ---------------------------------------------------------------------------- #
        # note 1
        if self.last_remote_packet_id < self.MAX_INIT_PACKAGE_COUNT:
            self.missed_initialization_packages[self.last_remote_packet_id >> 3] = self.missed_initialization_packages[
                self.last_remote_packet_id >> 3
            ] & ~(1 << (self.last_remote_packet_id & 0x07))
        # note 2
        if header & self.HEADERCMD_RESEND:
            context.log.debug(f"{self.__class__.__name__} resent packet")
        # ---------------------------------------------------------------------------- #
        # note 3
        if header & self.HEADERCMD_HELLOPACKET:
            context.log.debug(f"{self.__class__.__name__} parse_data() hello packet received")
            self.connected = True
            self.clear_packet_buffer()
            if data[12] == 0x04:
                context.log.debug(f"{self.__class__.__name__} parse_data() disconnect requested")
                self.disconnect()
            else:
                self.create_command_header(self.HEADERCMD_ACK, 12)
                self.packet_buffer[9] = 0x03
                self.send_packet_buffer(12)
        # ---------------------------------------------------------------------------- #
        # note 4
        if not self.init_payload_sent and packet_size == 12 and self.last_remote_packet_id > 1:
            self.init_payload_sent = True
            self.init_payload_sent_at_packet_id = self.last_remote_packet_id
        # ---------------------------------------------------------------------------- #
        # note 5
        if (
            not self.init_payload_sent
            and not (header & self.HEADERCMD_HELLOPACKET)
            and not (header & self.HEADERCMD_RESEND)
            and packet_size > 12
        ):
            self.initial_buffer.extend(data[12:packet_size])
        # ---------------------------------------------------------------------------- #
        # note 6
        if (
            self.init_payload_sent
            and (header & self.HEADERCMD_ACKREQUEST)
            and (self.initialized or not (header & self.HEADERCMD_RESEND))
        ):
            self.clear_packet_buffer()
            self.create_command_header_id(self.HEADERCMD_ACK, 12, self.last_remote_packet_id)
            self.packet_buffer[9] = 0x47
            if header & self.HEADERCMD_RESEND:
                self.debug_print("resend ack: ", self.packet_buffer)
            self.send_packet_buffer(12)
        # ---------------------------------------------------------------------------- #
        # note 7
        if (
            self.initialized
            and not (header & self.HEADERCMD_HELLOPACKET)
            and not (header & self.HEADERCMD_RESEND)
            and packet_length > 12
        ):
            self.parse_packet(data[12:packet_size])
        # ---------------------------------------------------------------------------- #
        # note 8
        if not self.initialized and self.init_payload_sent and not self.waiting_for_incoming:
            for packet_id in range(self.init_payload_sent_at_packet_id):
                if self.missed_initialization_packages[packet_id >> 3] & (0x01 << (packet_id & 0x07)):
                    self.clear_packet_buffer()
                    self.create_command_header(self.HEADERCMD_REQUESTNEXTAFTER, 12)
                    if packet_id > -1:
                        self.packet_buffer[5] = packet_id - 1 >> 8
                        self.packet_buffer[6] = packet_id - 1 & 0xFF
                        self.packet_buffer[7] = 0x01
                        self.send_packet_buffer(12)
                        self.waiting_for_incoming = True
                        break
            if not self.waiting_for_incoming:
                self.parse_packet(self.initial_buffer)
                self.initialized = True
                self.waiting_for_incoming = True
                self.initial_buffer = bytearray(96)
                self.emit("connected")
            context.log.debug(f"{self.__class__.__name__} parse_data() atem initialized")

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
                command_length = (data[index_pointer] << 8) | data[index_pointer + 1]
                context.log.debug(
                    f"{self.__class__.__name__} {index_pointer=} {len_data=} {counter=} {command_length=}"
                )
                if command_length > 8:
                    command_string = data[index_pointer + 4 : index_pointer + 4 + 4]
                    context.log.debug(f"{command_length=} {command_string=}")
                    decoded_command = command_string.decode(errors="ignore")
                    if decoded_command.find("PrgI") != -1:
                        self.program_input = data[index_pointer + 10] << 8 | data[index_pointer + 11]
                        context.log.debug(
                            f"{self.__class__.__name__} Program Input:",
                            self.program_input,
                        )
                        self.emit("pgm_switched", self.program_input)
                    elif decoded_command.find("PrvI") != -1:
                        self.preview_input = data[index_pointer + 10] << 8 | data[index_pointer + 11]
                        context.log.debug(
                            f"{self.__class__.__name__} Preview Input:",
                            self.preview_input,
                        )
                        self.emit("pvw_switched", self.preview_input)
                    elif decoded_command.find("AuxS") != -1:
                        aux_index = int(data[9])
                        if 0 <= aux_index <= 7:
                            self.aux_inputs[aux_index] = data[index_pointer + 11] << 8 | data[index_pointer + 12]
                            context.log.debug(
                                f"{self.__class__.__name__} Aux Input {aux_index}: {self.aux_inputs[aux_index]}"
                            )
                            self.emit("aux_switched", self.aux_inputs[aux_index])
                    elif decoded_command.find("InPr") != -1:
                        # todo 이름 가져오기 구현
                        pass
                    # elif decoded_command.find("DCut") != -1:
                    #     context.log.debug(f"{self.__class__.__name__} Cut!")
                    #     self.emit("cut")
                    # elif decoded_command.find("DAut") != -1:
                    #     context.log.debug(f"{self.__class__.__name__} Auto!")
                    #     self.emit("auto")
                else:
                    break
                index_pointer += command_length
                counter += 1
        except Exception as e:
            context.log.error(f"{self.__class__.__name__} parse_packet error.. {e=}")
        finally:
            counter = 0
            index_pointer = 0

    def clear_packet_buffer(self):
        self.packet_buffer = bytearray(96)
        for i in range(96):
            self.packet_buffer[i] = 0

    def create_command_header(self, header_command, data_length):
        self.create_command_header_id(header_command, data_length, 0)

    def create_command_header_id(self, header_command, data_length, remote_packet_id):
        context.log.debug(f"{self.__class__.__name__} create_command_header_id() {remote_packet_id=}")
        self.packet_buffer[0] = (header_command << 3) | ((data_length >> 8) & 0x07)  # cmd mask
        self.packet_buffer[1] = data_length & 0xFF  # length LSB
        self.packet_buffer[2] = self.session_id >> 8  # Session ID
        self.packet_buffer[3] = self.session_id & 0xFF  # Session ID
        self.packet_buffer[4] = remote_packet_id >> 8  # Remote Packet ID, MSB
        self.packet_buffer[5] = remote_packet_id & 0xFF  # Remote Packet ID, LSB
        if not (header_command & (self.HEADERCMD_HELLOPACKET | self.HEADERCMD_ACK | self.HEADERCMD_REQUESTNEXTAFTER)):
            # if not header_command in (self.HEADERCMD_HELLOPACKET, self.HEADERCMD_ACK, self.HEADERCMD_REQUESTNEXTAFTER):
            self.local_packet_id_counter += 1
            self.packet_buffer[10] = self.local_packet_id_counter >> 8  # Local Packet ID, MSB
            self.packet_buffer[11] = self.local_packet_id_counter & 0xFF  # Local Packet ID, LSB

    def prepare_command_packet(self, command_string: str):
        self.clear_packet_buffer()
        self.return_package_length = 12 + 4 + 4 + len(command_string)
        context.log.debug(f"{self.__class__.__name__} prepare_command_packet() {self.return_package_length=}")
        self.packet_buffer[12] = 0
        self.packet_buffer[13] = 4 + 4 + len(command_string)
        if len(command_string) == 4:
            self.packet_buffer[16] = ord(command_string[0])
            self.packet_buffer[17] = ord(command_string[1])
            self.packet_buffer[18] = ord(command_string[2])
            self.packet_buffer[19] = ord(command_string[3])
        context.log.debug(f"{self.__class__.__name__} prepare_command_packet() {self.packet_buffer[16:20]=}")
        self.debug_print("prepare_command_packet()", self.packet_buffer)

    def finish_command_packet(self):
        self.create_command_header(self.HEADERCMD_ACKREQUEST, self.return_package_length)
        self.debug_print("finish_command_packet()", self.packet_buffer)
        self.send_packet_buffer(self.return_package_length)
        self.return_package_length = 0

    def send_packet_buffer(self, return_package_length):
        self.debug_print("send_packet_buffer()", self.packet_buffer[:return_package_length])
        self.dv.send(self.packet_buffer[:return_package_length])

    # ---------------------------------------------------------------------------- #
    def debug_print(self, str_message, bytes_message):
        if not self.debug:
            return
        context.log.debug(f"{self.__class__.__name__} DEBUG:", str_message, " LENGTH:", len(bytes_message))
        # context.log.debug("BYTE:", bytes_message)
        context.log.debug(f"{self.__class__.__name__} Hex:", " ".join(f"{b:02x}" for b in bytes_message))
        # context.log.debug(f"{self.__class__.__name__} ASCII:", "".join(chr(b) if 32 <= b <= 126 else "." for b in bytes_message))

    # ---------------------------------------------------------------------------- #
    def set_program_input(self, input_id):
        self.program_input = input_id
        self.prepare_command_packet("CPgI")
        self.packet_buffer[12 + 4 + 4 + 0] = 0
        self.packet_buffer[12 + 4 + 4 + 2] = (input_id >> 8) & 0xFF
        self.packet_buffer[12 + 4 + 4 + 3] = input_id & 0xFF
        self.finish_command_packet()
        self.program_input = input_id

    def set_preview_input(self, input_id):
        self.prepare_command_packet("CPvI")
        self.packet_buffer[12 + 4 + 4 + 0] = 0
        self.packet_buffer[12 + 4 + 4 + 2] = (input_id >> 8) & 0xFF
        self.packet_buffer[12 + 4 + 4 + 3] = input_id & 0xFF
        self.finish_command_packet()
        self.preview_input = input_id

    def set_aux_input(self, aux_index, input_id):
        if 0 <= aux_index < 8:
            self.aux_inputs[aux_index] = input_id
            self.prepare_command_packet("CAuS")
            self.packet_buffer[12 + 4 + 4 + 0] = 0
            self.packet_buffer[12 + 4 + 4 + 1] = aux_index - 1
            self.packet_buffer[12 + 4 + 4 + 2] = input_id >> 8
            self.packet_buffer[12 + 4 + 4 + 3] = input_id & 0xFF
            self.finish_command_packet()

    def perform_cut(self):
        self.prepare_command_packet("DCut")
        self.finish_command_packet()

    def perform_auto(self):
        self.prepare_command_packet("DAut")
        self.finish_command_packet()


# ---------------------------------------------------------------------------- #
# 사용 예시
# if __name__ == "__main__":
#     atem_switcher = ATEMSwitcher("10.20.0.88")
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
