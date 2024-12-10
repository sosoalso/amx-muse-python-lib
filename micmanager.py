# ---------------------------------------------------------------------------- #
from eventmanager import EventManager


# ---------------------------------------------------------------------------- #
class MicManager(EventManager):
    def __init__(self, max_mic_idx: int = 40, last_mic_enabled: bool = True):
        super().__init__("on", "off", "all_off")  # EventManager의 생성자 호출
        self.max_mic_idx = max_mic_idx
        self.mics_on = [False] * max_mic_idx
        self.last_on_mics = []  # 마지막으로 켜진 마이크의 순서를 저장하는 리스트
        self.isLastMicEnabled = last_mic_enabled

    def get_last_mic_enabled(self) -> bool:
        return self.isLastMicEnabled

    def set_last_mic_enabled(self, is_enabled: bool) -> bool:
        self.isLastMicEnabled = is_enabled
        return self.get_last_mic_enabled()

    def turn_all_mic_off(self):
        for i in range(self.max_mic_idx):
            self.turn_mic_off(i)

    def turn_last_mic_on(self):
        if self.last_on_mics:
            last_mic = self.last_on_mics[-1]
            self.turn_mic_on(last_mic)
        else:
            pass
            # print("turn_last_mic_on() No last mic to turn on.")
            # self.trigger_event("all_off")

    def turn_mic_on(self, mic_id: int):
        if 0 <= mic_id <= self.max_mic_idx:
            self.mics_on[mic_id] = True
            # print(f"{mic_id=} is on.")
            # 마지막으로 켜진 마이크 순서 업데이트
            if mic_id in self.last_on_mics:
                self.last_on_mics.remove(mic_id)
            self.last_on_mics.append(mic_id)
            # ---------------------------------------------------------------------------- #
            if self.isLastMicEnabled:
                self.trigger_event("on", mic_id)
        else:
            pass
            # print(f"turn_mic_on() {mic_id=} is already on or does not exist.")

    def turn_mic_off(self, mic_id: int):
        # self.mics_on에 mic_id가 존재하는지 확인
        if 0 <= mic_id <= self.max_mic_idx:
            self.mics_on[int(mic_id)] = False
            # print(f"{mic_id=} is off.")
            # 마이크가 꺼지면 리스트에서 제거
            if mic_id in self.last_on_mics:
                self.last_on_mics.remove(mic_id)
            # ---------------------------------------------------------------------------- #
            if self.last_on_mics:
                # print(f"last mic is {self.get_last_on_mic()=}")
                self.trigger_event("off", mic_id)
                if self.isLastMicEnabled:
                    self.trigger_event("on", mic_id, self.get_last_on_mic())
            else:
                pass
                # print("turn_mic_off() No mics are currently on.")
            if not self.last_on_mics:
                self.trigger_event("all_off")
        else:
            pass
            # print(f"turn_mic_off() mic {mic_id} is already off or does not exist.")

    def get_mic_status(self, mic_id: int):
        return self.mics_on[mic_id]

    def get_last_on_mic(self):
        return self.last_on_mics[-1] if self.last_on_mics else None


# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
