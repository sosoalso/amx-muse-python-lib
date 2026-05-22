# 마지막 수정일 : 20260521
from lib.event_manager import EventManager
from lib.scheduler import Scheduler
from lib.utility import CommonLogger


# todo 기능 더 추가해야 됨
class NecVidprj(CommonLogger, EventManager):
    def __init__(self, dv):
        super().__init__("power", "poweron", "poweroff", "mute", "muted", "unmuted", "poll")
        self.dv = dv
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.power = False
        self.mute = False
        self.buffer = bytearray()
        self.last_send_command = bytearray()
        self.poll = Scheduler()

    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.start_poll()
        # self.dv.online(lambda *_args, **_kwargs: self.start_poll())
        # self.dv.offline(lambda *_args, **_kwargs: self.poll.shutdown())

    def send(self, msg):
        self.last_send_command = bytearray(msg)
        chksum = sum(c for c in msg) % 255
        self.dv.send(msg + bytes([chksum]))

    def start_poll(self, *args):
        def query_power():
            self.send(b"\x00\x85\x00\x00\x01\x01")

        def query_mute():
            self.send(b"\x00\x85\x00\x00\x01\x03")

        self.poll.set_timeout(1.0, lambda: self.poll.set_interval(10.0, query_power))
        self.poll.set_timeout(3.0, lambda: self.poll.set_interval(10.0, query_mute))

    def parse_response(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"Received response is in an invalid format. {args=}")
        else:
            try:
                data_text = args[0].arguments["data"]
                self.buffer += data_text

                # Check for end marker \xc0
                if b"\xc0" not in self.buffer:
                    return

                # Extract complete message up to \xc0
                end_index = self.buffer.find(b"\xc0")
                message = self.buffer[: end_index + 1]
                self.buffer = self.buffer[end_index + 1 :]

                if len(message) < 10:
                    return
                if message[0] != 0x20 or message[1] != 0x85 or message[4] == 0x10:
                    return

                # power
                if b"\x00\x85\x00\x00\x01\x01" == self.last_send_command:
                    if message[7] == 0x01:
                        self.power = True
                        self.emit("power", value=self.power)
                    elif message[7] == 0x00:
                        self.power = False
                        self.emit("power", value=self.power)
                elif b"\x00\x85\x00\x00\x01\x03" == self.last_send_command:
                    if message[5] == 0x01:
                        self.mute = True
                        self.emit("mute", value=self.mute)
                    elif message[5] == 0x00:
                        self.mute = False
                        self.emit("mute", value=self.mute)
                self.last_send_command.clear()
            except (AttributeError, KeyError, UnicodeDecodeError, IndexError) as e:
                self.log_error(f"Error decoding data {e=}")

    def set_power(self, value):
        self.send(b"\x02\x00\x00\x00\x00" if value else b"\x02\x01\x00\x00\x00")
        self.power = value
        self.emit("power", value=self.power)

    def power_on(self):
        self.set_power(True)
        self.mute = False
        self.emit("mute", value=self.mute)

    def power_off(self):
        self.set_power(False)
        self.mute = False
        self.emit("mute", value=self.mute)

    def set_mute(self, value):
        self.send(b"\x02\x10\x00\x00\x00" if value else b"\x02\x11\x00\x00\x00")
        self.mute = value
        self.emit("mute", value=self.mute)

    def mute_on(self):
        self.set_mute(True)

    def mute_off(self):
        self.set_mute(False)
