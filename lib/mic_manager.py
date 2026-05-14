# 마지막 수정일 : 20260514
import threading

from lib.event_manager import EventManager
from lib.utility import CommonLogger


class MicManager(CommonLogger, EventManager):
    def __init__(self, max_mic_index=40, last_mic_enabled=True):
        super().__init__("mic_on", "mic_off", "mic_all_off")
        self.max_mic_index = max_mic_index
        self.last_mic_enabled = last_mic_enabled
        self.mics_on = [False] * self.max_mic_index
        self.last_on_mics = []
        self._lock = threading.Lock()
        self.reset_mic_state()

    def reset_mic_state(self):
        self.log_debug("reset_mic_state()")
        with self._lock:
            self.mics_on = [False] * self.max_mic_index
            self.last_on_mics = []

    # 사용자 입력 인덱스(1부터 시작)를 내부 배열 인덱스(0부터)로 변환
    def index_to_idx(self, mic_index):
        if isinstance(mic_index, int) and 1 <= mic_index <= self.max_mic_index:
            return mic_index - 1
        return None

    def get_last_mic_enabled(self) -> bool:
        return self.last_mic_enabled

    def set_last_mic_enabled(self, is_enabled: bool) -> bool:
        self.last_mic_enabled = is_enabled
        return self.get_last_mic_enabled()

    def turn_mic_on(self, mic_index):
        self.log_debug(f"turn_mic_on() {mic_index=}")
        self.handle_mic_on(mic_index)

    def turn_mic_off(self, mic_index):
        self.log_debug(f"turn_mic_off() {mic_index=}")
        self.handle_mic_off(mic_index)

    def turn_all_mic_off(self):
        self.log_debug("turn_all_mic_off()")
        self.handle_all_mic_off()

    def turn_last_mic_on(self):
        self.log_debug("turn_last_mic_on()")
        self.handle_last_mic_on()

    def mic_on(self, mic_index):
        self.log_debug(f"mic_on() {mic_index=}")
        self.handle_mic_on(mic_index)

    def mic_off(self, mic_index):
        self.log_debug(f"mic_off() {mic_index=}")
        self.handle_mic_off(mic_index)

    def all_mic_off(self):
        self.log_debug("all_mic_off()")
        self.handle_all_mic_off()

    def last_mic_on(self):
        self.log_debug("last_mic_on()")
        self.handle_last_mic_on()

    def handle_all_mic_off(self):
        self.log_debug("handle_all_mic_off()")
        self.reset_mic_state()
        self.emit("mic_all_off")

    def handle_last_mic_on(self):
        self.log_debug("handle_last_mic_on()")
        # 이전에 켜진 마이크 목록이 있으면 마지막 마이크를 다시 켬
        last_mic_index = self.get_last_on_mic()
        if last_mic_index:
            self.emit("mic_on", last_mic_index)

    def handle_mic_on(self, mic_index):
        self.log_debug(f"handle_mic_on() {mic_index=}")
        mic_idx = self.index_to_idx(mic_index)
        if mic_idx is None:
            self.log_error(f"handle_mic_on() : wrong index {mic_index=}")
            return
        with self._lock:
            was_on = self.mics_on[mic_idx]
            self.mics_on[mic_idx] = True
            # 이미 기록된 마이크면 위치 업데이트(최근에 켠 순서대로 정렬)
            if mic_idx in self.last_on_mics:
                self.last_on_mics.remove(mic_idx)
            self.last_on_mics.append(mic_idx)
        if not was_on:
            self.emit("mic_on", mic_index)

    def handle_mic_off(self, mic_index):
        self.log_debug(f"handle_mic_off() {mic_index=}")
        mic_idx = self.index_to_idx(mic_index)
        if mic_idx is None:
            self.log_error(f"handle_mic_off() : wrong index {mic_index=}")
            return
        with self._lock:
            if not self.mics_on[mic_idx]:
                return
            self.mics_on[mic_idx] = False
            if mic_idx in self.last_on_mics:
                self.last_on_mics.remove(mic_idx)
            last_mic_index = self.last_on_mics[-1] + 1 if self.last_on_mics else None
        # 모든 마이크가 꺼진 경우와 켜진 마이크가 남은 경우 처리
        if last_mic_index:
            self.emit("mic_off", mic_index)
            # 자동 마이크 전환 설정이 활성화되면 마지막 켜진 마이크로 자동 전환
            if self.last_mic_enabled:
                self.emit("mic_on", last_mic_index)
        else:
            # 켜진 마이크가 없으면 모든 마이크 꺼짐 이벤트 발생
            self.emit("mic_all_off")

    def get_mic_status(self, mic_index):
        mic_idx = self.index_to_idx(mic_index)
        # 유효한 범위의 인덱스인지 검증
        if isinstance(mic_idx, int) and 0 <= mic_idx < self.max_mic_index:
            with self._lock:
                return self.mics_on[mic_idx]
        self.log_error(f"get_mic_status() : wrong index {mic_index=}")
        return None

    # 마지막으로 켜진 마이크의 사용자 인덱스 반환(내부 인덱스 + 1)
    def get_last_on_mic(self):
        with self._lock:
            return self.last_on_mics[-1] + 1 if self.last_on_mics else None
