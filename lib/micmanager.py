from lib.eventmanager import EventManager


# ---------------------------------------------------------------------------- #
class MicManager(EventManager):
    def __init__(self, max_mic_index=40, last_mic_enabled=True):
        super().__init__("on", "off", "all_off")  # EventManager의 생성자 호출
        self.max_mic_index = max_mic_index
        self.mics_on = [False] * max_mic_index
        self.last_on_mics = []  # 마지막으로 켜진 마이크의 순서를 저장하는 리스트
        self.last_mic_enabled = last_mic_enabled

    def index_to_idx(self, mic_index):
        if 0 < mic_index <= self.max_mic_index:
            return mic_index - 1
        return None

    def get_last_mic_enabled(self) -> bool:
        return self.last_mic_enabled

    def set_last_mic_enabled(self, is_enabled: bool) -> bool:
        self.last_mic_enabled = is_enabled
        return self.get_last_mic_enabled()

    # ---------------------------------------------------------------------------- #
    def turn_mic_on(self, mic_index):
        self.handle_mic_on(mic_index)

    def turn_mic_off(self, mic_index):
        self.handle_mic_off(mic_index)

    def turn_all_mic_off(self):
        self.handle_all_mic_off()

    def turn_last_mic_on(self):
        self.handle_list_mic_on()

    # ---------------------------------------------------------------------------- #
    def handle_all_mic_off(self):
        for idx in range(self.max_mic_index):
            self.handle_mic_off(idx)

    def handle_last_mic_on(self):
        if self.last_on_mics:
            last_mic = self.last_on_mics[-1]
            self.handle_mic_on(last_mic)

    def handle_mic_on(self, mic_index):
        mic_idx = self.index_to_idx(mic_index)
        if mic_idx is not None:
            self.mics_on[mic_idx] = True
            # 마지막으로 켜진 마이크 순서 업데이트
            if mic_idx in self.last_on_mics:
                self.last_on_mics.remove(mic_idx)
            self.last_on_mics.append(mic_idx)
            self.trigger_event("on", mic_index)

    def handle_mic_off(self, mic_index):
        mic_idx = self.index_to_idx(mic_index)
        if mic_idx is not None:
            self.mics_on[mic_idx] = False
            # 마이크가 꺼지면 리스트에서 제거
            if mic_idx in self.last_on_mics:
                self.last_on_mics.remove(mic_idx)
            # ---------------------------------------------------------------------------- #
            if self.last_on_mics:
                self.trigger_event("off", mic_index)
                if self.last_mic_enabled:
                    last_mic_index = self.get_last_on_mic()
                    if last_mic_index:
                        self.trigger_event("on", last_mic_index)
            if not self.last_on_mics:
                self.trigger_event("all_off")

    def get_mic_status(self, mic_index):
        mic_idx = self.index_to_idx(mic_index)
        if mic_idx is not None:
            return self.mics_on[mic_idx]

    def get_last_on_mic(self):
        return self.last_on_mics[-1] + 1 if self.last_on_mics else None
