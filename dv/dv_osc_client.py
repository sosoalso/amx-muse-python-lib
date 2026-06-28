# 마지막 수정일 : 20260629
import struct
from lib.event_manager import EventManager
from lib.utility import CommonLogger, handle_exception
from lib.network_manager import DEFAULT_UDP_CLIENT_RECONNECT_TIME, UdpClient

try:
    from pythonosc.osc_message import OscMessage
    from pythonosc.osc_message_builder import OscMessageBuilder
except ModuleNotFoundError:

    def _pad4(length):
        return (4 - (length % 4)) % 4

    def _pack_padded_string(value):
        data = value.encode("utf-8") + b"\x00"
        return data + (b"\x00" * _pad4(len(data)))

    def _unpack_padded_string(data, start):
        end = data.find(b"\x00", start)
        if end < 0:
            raise ValueError("Invalid OSC packet: null terminator missing")
        text = data[start:end].decode("utf-8")
        size = (end - start) + 1
        next_pos = end + 1 + _pad4(size)
        return text, next_pos

    class OscMessage:
        def __init__(self, dgram):
            self.dgram = dgram
            self.address = ""
            self.params = []
            self._parse()

        def _parse(self):
            self.address, idx = _unpack_padded_string(self.dgram, 0)
            if idx >= len(self.dgram):
                return
            tags, idx = _unpack_padded_string(self.dgram, idx)
            if not tags.startswith(","):
                return
            for tag in tags[1:]:
                if tag == "i":
                    self.params.append(struct.unpack(">i", self.dgram[idx : idx + 4])[0])
                    idx += 4
                elif tag == "f":
                    self.params.append(struct.unpack(">f", self.dgram[idx : idx + 4])[0])
                    idx += 4
                elif tag == "s":
                    text, idx = _unpack_padded_string(self.dgram, idx)
                    self.params.append(text)
                elif tag == "b":
                    size = struct.unpack(">i", self.dgram[idx : idx + 4])[0]
                    idx += 4
                    blob = self.dgram[idx : idx + size]
                    idx += size + _pad4(size)
                    self.params.append(blob)
                elif tag == "T":
                    self.params.append(True)
                elif tag == "F":
                    self.params.append(False)
                elif tag == "N":
                    self.params.append(None)

    class _BuiltOscMessage:
        def __init__(self, dgram):
            self.dgram = dgram

    class OscMessageBuilder:
        def __init__(self, address):
            self.address = address
            self._args = []

        def add_arg(self, arg_value, arg_type=None):
            tag = arg_type
            if tag is None:
                if isinstance(arg_value, bool):
                    tag = "T" if arg_value else "F"
                elif isinstance(arg_value, int):
                    tag = "i"
                elif isinstance(arg_value, float):
                    tag = "f"
                elif isinstance(arg_value, (bytes, bytearray)):
                    tag = "b"
                elif arg_value is None:
                    tag = "N"
                else:
                    tag = "s"
            self._args.append((tag, arg_value))

        def build(self):
            dgram = bytearray()
            dgram.extend(_pack_padded_string(self.address))
            dgram.extend(_pack_padded_string("," + "".join(tag for tag, _ in self._args)))
            for tag, value in self._args:
                if tag == "i":
                    dgram.extend(struct.pack(">i", int(value)))
                elif tag == "f":
                    dgram.extend(struct.pack(">f", float(value)))
                elif tag == "s":
                    dgram.extend(_pack_padded_string(str(value)))
                elif tag == "b":
                    payload = bytes(value)
                    dgram.extend(struct.pack(">i", len(payload)))
                    dgram.extend(payload)
                    dgram.extend(b"\x00" * _pad4(len(payload)))
                elif tag in ("T", "F", "N"):
                    continue
                else:
                    dgram.extend(_pack_padded_string(str(value)))
            return _BuiltOscMessage(bytes(dgram))


class OscClient(CommonLogger, EventManager):
    def __init__(self, ip, port, bound_port=None, reconnect_time=DEFAULT_UDP_CLIENT_RECONNECT_TIME):
        super().__init__()
        self.dv = UdpClient(ip=ip, port=port, bound_port=bound_port, reconnect_time=reconnect_time)
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"

    @handle_exception
    def handle_receive(self, datagram):
        parsed_osc_message = OscMessage(datagram)
        self.log_debug(f"{parsed_osc_message.address=}, {parsed_osc_message.params=}")
        self.emit(parsed_osc_message.address, params=parsed_osc_message.params)

    @handle_exception
    def init(self):
        self.dv.receive.listen(lambda evt: self.handle_receive(evt.arguments["data"]))
        self.dv.connect()

    @handle_exception
    def send(self, address, value, value_type=None):
        builder = OscMessageBuilder(address=address)
        builder.add_arg(arg_value=value, arg_type=value_type if value_type else None)
        message = builder.build()
        self.dv.send(message.dgram)
        self.log_debug(f"{message.dgram=}")
