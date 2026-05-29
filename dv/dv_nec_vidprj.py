# 마지막 수정일 : 20260526
from lib.event_manager import EventManager
from lib.scheduler import Scheduler
from lib.utility import CommonLogger, handle_exception


# todo 기능 더 추가해야 됨
class NecVidprj(CommonLogger, EventManager):
    CMD_QUERY_POWER = b"\x00\x85\x00\x00\x01\x01"
    CMD_QUERY_MUTE = b"\x00\x85\x00\x00\x01\x03"

    def __init__(self, dv):
        super().__init__("power", "poweron", "poweroff", "mute", "muted", "unmuted", "poll")
        self.dv = dv
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.power = False
        self.mute = False
        self.buffer = bytearray()
        self.last_send_command = bytearray()
        self.poll = Scheduler()

    @handle_exception
    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.start_poll()
        # self.dv.online(lambda *_args, **_kwargs: self.start_poll())
        # self.dv.offline(lambda *_args, **_kwargs: self.poll.shutdown())

    @handle_exception
    def send(self, msg):
        self.last_send_command = bytearray(msg)
        chksum = sum(msg) & 0xFF
        self.log_debug(f"send() msg={msg.hex(' ')} cks={chksum:02x}")
        self.dv.send(msg + bytes([chksum]))

    @handle_exception
    def start_poll(self, *args):
        def query_power():
            self.send(self.CMD_QUERY_POWER)

        def query_mute():
            self.send(self.CMD_QUERY_MUTE)

        self.poll.set_timeout(1.0, lambda: self.poll.set_interval(10.0, query_power))
        self.poll.set_timeout(3.0, lambda: self.poll.set_interval(10.0, query_mute))

    def _get_next_message(self):
        while self.buffer and self.buffer[0] not in (0x20, 0x21, 0x22, 0x23, 0xA0, 0xA1, 0xA2, 0xA3):
            dropped = self.buffer.pop(0)
            self.log_debug(f"parse_response() dropped stray byte {dropped:02x}")

        if len(self.buffer) < 5:
            return None

        data_length = self.buffer[4]
        message_length = 5 + data_length + 1
        if len(self.buffer) < message_length:
            return None

        message = self.buffer[:message_length]
        del self.buffer[:message_length]
        return message

    def _is_valid_checksum(self, message):
        return bool(message) and (sum(message[:-1]) & 0xFF) == message[-1]

    @handle_exception
    def parse_response(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"Received response is in an invalid format. {args=}")
        else:
            try:
                data = args[0].arguments["data"]
                if isinstance(data, str):
                    data = data.encode()

                self.buffer += data
                self.log_debug(f"parse_response() received={bytes(data).hex(' ')} buffer={self.buffer.hex(' ')}")

                while True:
                    message = self._get_next_message()
                    if message is None:
                        return

                    self.log_debug(f"parse_response() message={message.hex(' ')} last={self.last_send_command.hex(' ')}")

                    if not self._is_valid_checksum(message):
                        self.log_error(f"parse_response() invalid checksum message={message.hex(' ')}")
                        continue

                    if message[0] & 0x80:
                        self.log_error(f"parse_response() command failed message={message.hex(' ')}")
                        self.last_send_command.clear()
                        continue

                    if message[0] != 0x20 or message[1] != 0x85 or message[4] != 0x10:
                        self.log_debug(f"parse_response() ack/ignored message={message.hex(' ')}")
                        self.last_send_command.clear()
                        continue

                    if self.CMD_QUERY_POWER == bytes(self.last_send_command):
                        power_status = message[7]
                        if power_status == 0x01:
                            self.power = True
                        elif power_status == 0x00:
                            self.power = False
                        else:
                            continue
                        self.emit("power", value=self.power)
                    elif self.CMD_QUERY_MUTE == bytes(self.last_send_command):
                        picture_mute = message[5]
                        if picture_mute == 0x01:
                            self.mute = True
                        elif picture_mute == 0x00:
                            self.mute = False
                        else:
                            continue
                        self.emit("mute", value=self.mute)

                    self.last_send_command.clear()
            except (AttributeError, KeyError, TypeError, IndexError) as e:
                self.log_error(f"Error decoding data {e=}")

    @handle_exception
    def set_power(self, value):
        self.send(b"\x02\x00\x00\x00\x00" if value else b"\x02\x01\x00\x00\x00")
        self.power = value
        self.emit("power", value=self.power)

    @handle_exception
    def power_on(self):
        self.set_power(True)
        self.mute = False
        self.emit("mute", value=self.mute)

    @handle_exception
    def power_off(self):
        self.set_power(False)
        self.mute = False
        self.emit("mute", value=self.mute)

    @handle_exception
    def set_mute(self, value):
        self.send(b"\x02\x10\x00\x00\x00" if value else b"\x02\x11\x00\x00\x00")
        self.mute = value
        self.emit("mute", value=self.mute)

    @handle_exception
    def mute_on(self):
        self.set_mute(True)

    @handle_exception
    def mute_off(self):
        self.set_mute(False)
