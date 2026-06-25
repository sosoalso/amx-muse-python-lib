# 마지막 수정일 : 20260626
import json

from lib.event_manager import EventManager
from lib.network_manager import DEFAULT_UDP_CLIENT_RECONNECT_TIME, UdpClient
from lib.utility import CommonLogger, handle_exception


class NovastarH9(CommonLogger, EventManager):
    DEFAULT_PORT = 6000

    def __init__(self, ip, port=DEFAULT_PORT, reconnect_time=DEFAULT_UDP_CLIENT_RECONNECT_TIME):
        super().__init__("connected", "disconnected", "received")
        self.dv = UdpClient(ip, port, reconnect_time=reconnect_time)
        self.name = f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        # key: (screen_id, layer_id), value: input_id
        self.layer_inputs: dict[tuple[int, int], int] = {}

    @handle_exception
    def init(self):
        self.dv.receive.listen(self._on_receive)
        self.dv.online(lambda *_, **__: self.emit("connected"))
        self.dv.offline(lambda *_, **__: self.emit("disconnected"))
        self.dv.connect()

    def _send(self, cmd: list):
        msg = json.dumps(cmd)
        self.dv.send(msg)
        self.log_debug(f"_send() : {msg}")

    @handle_exception
    def _on_receive(self, *args):
        if not args or not hasattr(args[0], "arguments") or "data" not in args[0].arguments:
            self.log_error(f"_on_receive() : {args=}")
            return
        data = args[0].arguments["data"]
        self.log_debug(f"_on_receive() : {data=}")
        self.emit("received", data=data)

    # ------------------------------------------------------------------ #
    # INFO - Preset Recall
    # cmd: W0605
    # ------------------------------------------------------------------ #
    @handle_exception
    def recall_preset(self, device_id: int, screen_id: int, preset_id: int):
        """프리셋 불러오기 (presetId는 0-based)"""
        cmd = [{"cmd": "W0605", "deviceId": device_id, "screenId": screen_id, "presetId": preset_id}]
        self._send(cmd)
        self.log_info(f"recall_preset() : {device_id=} {screen_id=} {preset_id=}")

    # ------------------------------------------------------------------ #
    # INFO - Freeze
    # cmd: W041A
    # ------------------------------------------------------------------ #
    @handle_exception
    def set_freeze(self, screen_id: int, enable: bool):
        cmd = [{"cmd": "W041A", "screenId": screen_id, "enable": 1 if enable else 0}]
        self._send(cmd)
        self.log_info(f"set_freeze() : {screen_id=} {enable=}")

    # # ------------------------------------------------------------------ #
    # # cmd: W0506
    # # ------------------------------------------------------------------ #
    # @handle_exception
    # def set_layer_input(
    #     self,
    #     device_id: int,
    #     screen_id: int,
    #     layer_id: int,
    #     input_id: int,
    #     interface_type: int,
    #     source_type: int = 0,
    #     slot_id: int = 0,
    #     crop_id: int = 255,
    #     channel_id: int = 0,
    #     stream_index: int = 0,
    #     template_id: int = 0,
    # ):
    #     """레이어 입력 소스 설정
    #     interface_type: 입력 커넥터 타입
    #     input_id: 입력 소스 ID
    #     crop_id: 255 = 크롭 없이 원본 소스 사용
    #     """
    #     cmd = [
    #         {
    #             "cmd": "W0506",
    #             "deviceId": device_id,
    #             "screenId": screen_id,
    #             "layerId": layer_id,
    #             "sourceType": source_type,
    #             "interfaceType": interface_type,
    #             "inputId": input_id,
    #             "slotId": slot_id,
    #             "cropId": crop_id,
    #             "channelId": channel_id,
    #             "streamIndex": stream_index,
    #             "templateId": template_id,
    #         }
    #     ]
    #     self._send(cmd)
    #     self.layer_inputs[(screen_id, layer_id)] = input_id
    #     self.log_info(f"set_layer_input() : {device_id=} {screen_id=} {layer_id=} {input_id=} {interface_type=}")
    # ------------------------------------------------------------------ #
    # INFO - Get Preset List
    # cmd: R0606
    # ------------------------------------------------------------------ #
    @handle_exception
    def get_preset_list(self, device_id: int, screen_id: int, preset_groups: list[dict] | None = None):
        """화면의 프리셋 목록 요청
        preset_groups: [{"name": "group1", "presetGroupId": 0}, ...] 형식
                       None이면 빈 리스트로 전송
        """
        cmd = [
            {
                "cmd": "R0606",
                "deviceId": device_id,
                "screenId": screen_id,
                "presetGroups": preset_groups if preset_groups is not None else [],
            }
        ]
        self._send(cmd)
        self.log_info(f"get_preset_list() : {device_id=} {screen_id=} {preset_groups=}")
