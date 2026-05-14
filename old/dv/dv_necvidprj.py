from lib.eventmanager import EventManager
from lib.scheduler import Scheduler
from lib.utility import CommonLogger


# todo 기능 더 추가해야 됨
class NecVidprj(CommonLogger, EventManager):
    def __init__(self, dv):
        super().__init__("power", "poweron", "poweroff", "mute", "muted", "unmuted", "poll")
        self.dv = dv
        self.power = False
        self.mute = False
        self.poll = Scheduler(name=self.__class__.__name__ + " poll")
        self.buffer = bytearray()
        # ---------------------------------------------------------------------------- #
        self.last_send_command = bytearray()
        self.init()

    def log_debug(self, message):
        if self.debug:
            print(f"{self.__class__.__name__} (DEBUG) -- {message}")

    def log_error(self, message):
        print(f"{self.__class__.__name__} (ERROR) -- {message}")

    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.dv.connect()
        self.start_poll()

    def send(self, msg):
        if self.dv.connected:
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

                # power
                if b"\x00\x85\x00\x00\x01\x01" == self.last_send_command:
                    if message[7] == 0x01 or message[10] == 0x04:
                        self.power = True
                    elif message[7] == 0x00 or message[10] == 0x04 or message[10] == 0x00 or message[10] == 0x06:
                        self.power = False
                    else:
                        return
                    self.trigger_event("power", value=self.power)
                elif b"\x00\x85\x00\x00\x01\x03" == self.last_send_command:
                    if message[5] == 0x01:
                        self.mute = True
                    elif message[5] == 0x00:
                        self.mute = False
                    else:
                        return
                    self.trigger_event("mute", value=self.mute)
                self.last_send_command.clear()
            except (AttributeError, KeyError, UnicodeDecodeError, IndexError) as e:
                self.log_error(f"Error decoding data {e=}")

    def set_power(self, value):
        self.send(b"\x02\x00\x00\x00\x00" if value else b"\x02\x01\x00\x00\x00")
        self.power = value
        self.trigger_event("power", value=value)

    def power_on(self):
        self.set_power(True)

    def power_off(self):
        self.set_power(False)

    # blank 임 eiki 명령어집에서는
    def set_mute(self, value):
        self.send(b"\x02\x10\x00\x00\x00" if value else b"\x02\x11\x00\x00\x00")
        self.mute = value
        self.trigger_event("mute", value=value)

    def mute_on(self):
        self.set_mute(True)

    def mute_off(self):
        self.set_mute(False)
