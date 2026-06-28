# 마지막 수정일 : 20260627
from lib.event_manager import EventManager
from lib.utility import CommonLogger


class MicManager(CommonLogger, EventManager):
    def __init__(self, max_mic_index=40, last_mic_enabled=True, max_mics=0):
        super().__init__("mic_on", "mic_off", "mic_all_off", "last_mic_on")
        self.max_mic_index = max_mic_index
        self.last_mic_enabled = last_mic_enabled
        self.max_mics = max_mics  # 0 또는 -1이면 제한 없음
        self.vip_mics = set()  # 꺼지면 안 되는 VIP 마이크 인덱스
        self.last_on_mics = []

    def is_mic_on(self, mic_index):
        return mic_index in self.last_on_mics

    def get_last_on_mic(self):
        return self.last_on_mics[-1] if self.last_on_mics else None

    def get_last_mic_enabled(self) -> bool:
        return self.last_mic_enabled

    def set_last_mic_enabled(self, is_enabled: bool) -> bool:
        self.last_mic_enabled = is_enabled
        return self.get_last_mic_enabled()

    # ---------------------------------------------------------------------------- #
    def set_vip_mic(self, mic_index):
        self.log_debug(f"set_vip_mic() {mic_index=}")
        self.vip_mics.add(mic_index)

    def unset_vip_mic(self, mic_index):
        self.log_debug(f"unset_vip_mic() {mic_index=}")
        self.vip_mics.discard(mic_index)

    def is_vip_mic(self, mic_index):
        return mic_index in self.vip_mics

    def set_max_mics(self, max_mics):
        self.log_debug(f"set_max_mics() {max_mics=}")
        self.max_mics = max_mics
        self.last_on_mics.clear()
        self.emit("mic_all_off")

    # ---------------------------------------------------------------------------- #
    def notify_mic_on(self, mic_index):
        self.log_debug(f"notify_mic_on() {mic_index=}")
        if mic_index in self.last_on_mics:
            self.last_on_mics.remove(mic_index)
        self.last_on_mics.append(mic_index)
        # max_mics 가 유효한 경우에만 초과 마이크 끄기 (VIP 제외)
        if self.max_mics > 0:
            non_vip = [m for m in self.last_on_mics if m not in self.vip_mics]
            while len(non_vip) > self.max_mics:
                oldest = non_vip.pop(0)
                self.last_on_mics.remove(oldest)
                self.log_debug(f"notify_mic_on() : max_mics exceeded, turning off {oldest=} {self.last_on_mics=}")
                self.emit("mic_off", oldest)
        self.emit("mic_on", mic_index)

    def notify_mic_off(self, mic_index):
        self.log_debug(f"notify_mic_off() {mic_index=}")
        if mic_index not in self.last_on_mics:
            return
        self.last_on_mics.remove(mic_index)
        if self.last_on_mics:
            self.emit("mic_off", mic_index)
            if self.last_mic_enabled:
                self.emit("last_mic_on", self.last_on_mics[-1])
        else:
            self.emit("mic_all_off")

    def notify_all_mic_off(self):
        self.log_debug("notify_all_mic_off()")
        self.last_on_mics.clear()
        self.emit("mic_all_off")
