# ---------------------------------------------------------------------------- #
from eventmanager import EventManager
from lib_yeoul import print_with_name


# ---------------------------------------------------------------------------- #
class MicManager(EventManager):
    def __init__(self, max_mic_idx, last_mic_enabled=True):
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
        # 마지막으로 켜진 마이크를 다시 켭니다.
        if self.last_on_mics:
            last_mic = self.last_on_mics[-1]
            self.turn_mic_on(last_mic)
        else:
            print_with_name("No last mic to turn on.")
            # self.trigger_event("all_off")

    def turn_mic_on(self, mic_id: int):
        if 0 <= mic_id <= self.max_mic_idx:
            self.mics_on[mic_id] = True
            print_with_name(f"{mic_id=} is on.")
            # 마지막으로 켜진 마이크 순서 업데이트
            if mic_id in self.last_on_mics:
                self.last_on_mics.remove(mic_id)
            self.last_on_mics.append(mic_id)
            # ---------------------------------------------------------------------------- #
            if self.isLastMicEnabled:
                self.trigger_event("on", mic_id)
        else:
            print_with_name(f"{mic_id=} is already on or does not exist.")
        print_with_name(self.get_all_mic_status())

    def turn_mic_off(self, mic_id: int):
        # self.mics_on에 mic_id가 존재하는지 확인
        if 0 <= mic_id <= self.max_mic_idx:
            self.mics_on[int(mic_id)] = False
            print_with_name(f"{mic_id=} is off.")
            # 마이크가 꺼지면 리스트에서 제거
            if mic_id in self.last_on_mics:
                self.last_on_mics.remove(mic_id)
            # ---------------------------------------------------------------------------- #
            if self.last_on_mics:
                print_with_name(f"last mic is {self.get_last_on_mic()=}")
                self.trigger_event("off", mic_id)
                if self.isLastMicEnabled:
                    self.trigger_event("on", mic_id, self.get_last_on_mic())
            else:
                print_with_name("No mics are currently on.")
            if not self.last_on_mics:
                self.trigger_event("all_off")
        else:
            print_with_name(f"mic {mic_id} is already off or does not exist.")

        print_with_name(f"current mic status : {self.get_all_mic_status()}")

    def get_mic_status(self, mic_id: int):
        return self.mics_on[mic_id]

    def get_all_mic_status(self):
        return self.mics_on

    def get_last_on_mic(self):
        # 마지막으로 켜진 마이크의 인덱스 반환
        if self.last_on_mics:
            return self.last_on_mics[-1]
        else:
            return None  # 모든 마이크가 꺼져있는 경우


# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
