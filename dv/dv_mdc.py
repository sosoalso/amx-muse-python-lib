# 마지막 수정일 : 20260625
from lib.event_manager import EventManager
from lib.scheduler import Scheduler
from lib.utility import CommonLogger, handle_exception


class Mdc(CommonLogger, EventManager):
    DEFAULT_PORT = 1515
    DEFAULT_ID = 1
    ID_ALL = 0xFE

    CMD_PWR = 0x11
    CMD_INPT_SRC = 0x14
    CMD_BRIGHTNESS = 0x38

    HEADER = 0xAA
    RESPONSE_CMD = 0xFF
    ACK = ord("A")
    GET = ord("g")

    def __init__(self, dv, id_mdc=DEFAULT_ID, name=None):
        super().__init__("power", "power_on", "power_off", "input", "poll")
        self.dv = dv
        self.id_mdc = id_mdc
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.power = False
        self.source = 0
        self.buffer = bytearray()
        self.poll = Scheduler()

    @handle_exception
    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.dv.online(lambda *_, **__: self.start_poll())
        self.dv.offline(lambda *_, **__: self.poll.shutdown())

    def _checksum(self, data):
        return sum(data) & 0xFF

    def _build_command(self, cmd, data=None):
        if data is None:
            payload = bytes([cmd, self.id_mdc, 0x00])
        else:
            payload = bytes([cmd, self.id_mdc, 0x01, data])
        return bytes([self.HEADER]) + payload + bytes([self._checksum(payload)])

    @handle_exception
    def send(self, cmd, data=None):
        msg = self._build_command(cmd, data)
        self.log_debug(f"send() msg={msg.hex(' ')}")
        self.dv.send(msg)

    @handle_exception
    def start_poll(self, *_):
        def query_power():
            self.send(self.CMD_PWR, self.GET)

        def query_input():
            self.send(self.CMD_INPT_SRC, self.GET)

        self.poll.set_timeout(1.0, lambda: self.poll.set_interval(10.0, query_power))
        self.poll.set_timeout(3.0, lambda: self.poll.set_interval(10.0, query_input))

    def _get_next_message(self):
        while self.buffer and self.buffer[0] != self.HEADER:
            dropped = self.buffer.pop(0)
            self.log_debug(f"_get_next_message() dropped stray byte {dropped:02x}")

        # packet: HEADER(1) + CMD(1) + ID(1) + LENGTH(1) + data(LENGTH) + CHKSUM(1)
        if len(self.buffer) < 4:
            return None

        length = self.buffer[3]
        message_length = 4 + length + 1
        if len(self.buffer) < message_length:
            return None

        message = bytes(self.buffer[:message_length])
        del self.buffer[:message_length]
        return message

    def _is_valid_checksum(self, message):
        return bool(message) and (sum(message[1:-1]) & 0xFF) == message[-1]

    @handle_exception
    def parse_response(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"Received response is in an invalid format. {args=}")
            return

        data = args[0].arguments["data"]
        if isinstance(data, str):
            data = data.encode("latin-1")

        self.buffer += data
        self.log_debug(f"parse_response() received={bytes(data).hex(' ')} buffer={self.buffer.hex(' ')}")

        while True:
            message = self._get_next_message()
            if message is None:
                return

            self.log_debug(f"parse_response() message={message.hex(' ')}")

            if len(message) < 8:
                self.log_error(f"parse_response() message too short message={message.hex(' ')}")
                continue

            if not self._is_valid_checksum(message):
                self.log_error(f"parse_response() invalid checksum message={message.hex(' ')}")
                continue

            if message[1] != self.RESPONSE_CMD:
                self.log_debug(f"parse_response() not a response frame, ignored message={message.hex(' ')}")
                continue

            if message[4] != self.ACK:
                self.log_error(f"parse_response() NAK received message={message.hex(' ')}")
                continue

            r_cmd = message[5]
            val = message[6]

            if r_cmd == self.CMD_PWR:
                self.power = bool(val)
                # emit: power(value: bool)
                self.emit("power", value=self.power)
            elif r_cmd == self.CMD_INPT_SRC:
                self.source = val
                # emit: input(value: int)
                self.emit("input", value=self.source)

    @handle_exception
    def set_power(self, value):
        self.send(self.CMD_PWR, 0x01 if value else 0x00)
        self.send(self.CMD_PWR, self.GET)
        self.power = value
        # emit: power(value: bool)
        self.emit("power", value=self.power)

    @handle_exception
    def power_on(self):
        self.set_power(True)

    @handle_exception
    def power_off(self):
        self.set_power(False)

    @handle_exception
    def set_input(self, source):
        self.send(self.CMD_INPT_SRC, source)
        self.send(self.CMD_INPT_SRC, self.GET)
        self.source = source
        # emit: input(value: int)
        self.emit("input", value=self.source)

    # @handle_exception
    # def set_brightness(self, value):
    #     self.send(self.CMD_BRIGHTNESS, value)
