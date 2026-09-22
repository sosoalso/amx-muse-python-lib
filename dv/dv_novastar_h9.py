# 마지막 수정일 : 20260713
import json

from lib.event_manager import EventManager
from lib.network_manager import DEFAULT_UDP_CLIENT_RECONNECT_TIME, UdpClient
from lib.utility import CommonLogger, handle_exception


class NovastarH9(CommonLogger, EventManager):
    DEFAULT_PORT = 6000
    DEFAULT_BUFFER_SIZE = 65535

    def __init__(self, ip, port=DEFAULT_PORT, reconnect_time=DEFAULT_UDP_CLIENT_RECONNECT_TIME, buffer_size=DEFAULT_BUFFER_SIZE, device_id=0):
        super().__init__("connected", "disconnected", "received")
        self.dv = UdpClient(ip, port, reconnect_time=reconnect_time, buffer_size=buffer_size)
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.device_id = device_id
        # key: (screen_id, layer_id), value: input_id
        self.layer_inputs: dict[tuple[int, int], int] = {}

    @handle_exception
    def init(self):
        self.dv.receive.listen(self._on_receive)
        # emit: connected()
        self.dv.online(lambda *args, **kwargs: self.emit("connected"))
        # emit: disconnected()
        self.dv.offline(lambda *args, **kwargs: self.emit("disconnected"))
        self.dv.connect()

    def _send(self, cmd: list):
        msg = json.dumps(cmd)
        self.dv.send(msg)
        self.log_debug(f"_send() : {msg}")

    @handle_exception
    def _on_receive(self, evt):
        data = evt.arguments.get("data", b"")
        if not data:
            self.log_error(f"_on_receive() : {evt=}")
            return
        self.log_debug(f"_on_receive() : {data=}")
        # emit: received(data: bytes)
        self.emit("received", data=data)

    # ------------------------------------------------------------------ #
    # INFO - Preset Recall
    # cmd: W0605
    # ------------------------------------------------------------------ #
    @handle_exception
    def recall_preset(self, screen_id, preset_id):
        """프리셋 불러오기 (presetId는 0-based)"""
        self.log_debug(f"recall_preset() : {self.device_id=} {screen_id=} {preset_id=}")
        cmd = [{"cmd": "W0605", "deviceId": self.device_id, "screenId": screen_id, "presetId": preset_id}]
        self._send(cmd)

    # ------------------------------------------------------------------ #
    # INFO - Freeze
    # cmd: W041A
    # ------------------------------------------------------------------ #
    @handle_exception
    def set_freeze(self, screen_id, enable: bool):
        self.log_debug(f"set_freeze() : {screen_id=} {enable=}")
        cmd = [{"cmd": "W041A", "screenId": screen_id, "enable": 1 if enable else 0}]
        self._send(cmd)

    # ---------------------------------------------------------------------------- #
    # # cmd: W0506
    # ---------------------------------------------------------------------------- #
    def set_layer_input(self, screen_id, layer_id, source_type, interface_type, input_id, slot_id, crop_id, channel_id, stream_index, template_id):
        cmd = [
            {
                "cmd": "W0506",
                "deviceId": self.device_id,
                "screenId": screen_id,
                "layerId": layer_id,
                "sourceType": source_type,
                "interfaceType": interface_type,
                "inputId": input_id,
                "slotId": slot_id,
                "cropId": crop_id,
                "channelId": channel_id,
                "streamIndex": stream_index,
                "templateId": template_id,
            }
        ]
        self.log_debug(f"set_layer_input() : {cmd=}")
        self._send(cmd)

    # ------------------------------------------------------------------ #
    # INFO - Get Screen Layer Enum
    # cmd: R0500
    # ------------------------------------------------------------------ #
    @handle_exception
    def get_layer_enum(self, screen_id):
        cmd = [{"cmd": "R0500", "param0": self.device_id, "param1": screen_id}]
        self._send(cmd)
        self.log_debug(f"get_layer_enum() : {json.dumps(cmd, indent=2)}")

    # ------------------------------------------------------------------ #
    # INFO - Get Screen Layer Details
    # cmd: R0501
    # ------------------------------------------------------------------ #
    @handle_exception
    def get_layer_details(self, screen_id, layer_id: int):
        cmd = [{"cmd": "R0501", "param0": self.device_id, "param1": screen_id, "param2": layer_id}]
        self.log_debug(f"get_layer_details() : {json.dumps(cmd, indent=2)}")
        self._send(cmd)


"""
When "cropId" is 255, the original source (not cropped source) will be used.
When changing IPC source,
  "slotId": 255,
  "inputId": 255,
  "interfaceType": 13,
  "sourceType": 3,
  "channelId": 3, // ID of the stream to be changed,
  "streamIndex": 0,
  "templateId": 65535,
"""
