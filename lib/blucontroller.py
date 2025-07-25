from typing import Sequence, Union

from lib.lib_yeoul import handle_exception, log_debug, log_error

# ---------------------------------------------------------------------------- #
VERSION = "2025.07.04"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
MIN_VAL = -60  # 최소 값
MAX_VAL = 6  # 최대 값
UNIT_VAL = 1  # 단위 값


# ---------------------------------------------------------------------------- #
class BluObserver:
    # 옵저버 리스트 초기화
    def __init__(self):
        self._observers = []

    # 옵저버 추가
    @handle_exception
    def subscribe(self, observer):
        self._observers.append(observer)

    # 옵저버 제거
    @handle_exception
    def unsubscribe(self, observer):
        self._observers.remove(observer)

    # 모든 옵저버에게 알림
    @handle_exception
    def notify(self, *args, **kwargs):
        for observer in self._observers:
            observer(*args, **kwargs)


# ---------------------------------------------------------------------------- #
class BluState:
    # 상태 저장 딕셔너리 초기화
    def __init__(self):
        self._states = {}
        self._event = BluObserver()  # 이벤트 옵저버 초기화

    # 상태 가져오기
    @handle_exception
    def get_state(self, key):
        return self._states.get(key, None)
        # 상태 설정

    @handle_exception
    def set_state(self, key, val):
        self._states[key] = val

    @handle_exception
    def update_state(self, key, val):
        self.set_state(key, val)  # 상태 업데이트
        self._event.notify(key)  # 상태 변경 알림

    # 상태 변경 강제 알림
    @handle_exception
    def override_notify(self, key):
        self._event.notify(key)

    # 옵저버 추가
    @handle_exception
    def subscribe(self, observer):
        self._event.subscribe(observer)

    # 옵저버 제거
    @handle_exception
    def unsubscribe(self, observer):
        self._event.unsubscribe(observer)


# ---------------------------------------------------------------------------- #
class BluController:
    def __init__(self, dv, states=None, min_val=MIN_VAL, max_val=MAX_VAL, unit_val=UNIT_VAL, debug=False):
        self.dv = dv  # 장치 설정
        self.states = BluState() if states is None else states  # 컴포넌트 상태 설정
        self.MIN_VAL = min_val  # 최소 값 설정
        self.MAX_VAL = max_val  # 최대 값 설정
        self.UNIT_VAL = unit_val  # 볼륨 조절 단위 값 설정
        self.debug = debug

    def blu_log_debug(self, message):
        if self.debug:
            log_debug(message)

    # NOTE : dB 값을 터치패널 0-255 값으로 변환
    @handle_exception
    def db_to_tp(self, x):
        x_min = self.MIN_VAL
        x_max = self.MAX_VAL
        y_min = 0
        y_max = 255
        y = (x - x_min) * (y_max - y_min) / (x_max - x_min) + y_min
        return y

    # NOTE : 터치패널 0-255 값을 dB 값으로 변환
    @handle_exception
    def tp_to_db(self, x):
        x_min = 0
        x_max = 255
        y_min = self.MIN_VAL
        y_max = self.MAX_VAL
        y = (x - x_min) * (y_max - y_min) / (x_max - x_min) + y_min
        return y

    @handle_exception
    def init(self, *path_lists: Sequence[Union[list[str], tuple[str, ...]]]):
        for path_list in path_lists:
            if not isinstance(path_list, (list, tuple)):
                log_error(
                    "BluController init() 에러 : path_lists 의 개별 요소는 path str 으로 구성된 list 나 tuple 이어야 합니다."
                )
                raise TypeError
            for path in path_list:
                if not isinstance(path, tuple):
                    log_error("BluController init() 에러 : 각각의 path 는 path str 으로 구성된 tuple 이어야 합니다.")
                    raise TypeError
                component = self.get_component(path)
                if component is not None:
                    self.states.update_state(path, component.value)
                    component.watch(lambda evt, path=path: self.states.update_state(path, evt.value))
                    self.states.override_notify(path)

    @handle_exception
    def subscribe(self, observer):
        self.states.subscribe(observer)

    # NOTE : 컴포넌트 가져오기
    @handle_exception
    def get_component(self, path: tuple[str, ...]):
        if not isinstance(path, tuple):
            log_error(
                "BluController get_component() 에러 : path 의 개별 요소는 는 tuple 로 둘러쌓여진 str 으로 구성돼야합니다."
            )
            raise TypeError
        nested_component = self.dv  # Logic 때문에 self.dv 에서 시작
        for p in path:
            nested_component = nested_component[p]
        return nested_component

    @handle_exception
    def get_state(self, path: tuple[str, ...]):
        if not isinstance(path, tuple):
            log_error(
                "BluController get_state() 에러 : path 의 개별 요소는 는 tuple 로 둘러쌓여진 str 으로 구성돼야합니다."
            )
            raise TypeError
        return self.states.get_state(path)

    # NOTE : 컴포넌트 값 업데이트
    @handle_exception
    def update_state(self, path: tuple[str, ...], new_value: Union[str, float]):
        if self.dv.isOnline():
            component = self.get_component(path)
            if component is not None:
                component.value = new_value

    # INFO : 사용자 함수
    def check_val_convert_float(self, val):
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @handle_exception
    def vol_up(self, path):
        self.blu_log_debug(f"BluController vol_up() {path=}")
        val = self.check_val_convert_float(self.states.get_state(path))
        if val is not None and val <= self.MAX_VAL - self.UNIT_VAL:
            self.update_state(path, round(val + self.UNIT_VAL))

    @handle_exception
    def vol_down(self, path):
        self.blu_log_debug(f"BluController vol_down() {path=}")
        val = self.check_val_convert_float(self.states.get_state(path))
        if val is not None and val >= self.MIN_VAL + self.UNIT_VAL:
            self.update_state(path, round(val - self.UNIT_VAL))

    @handle_exception
    def set_vol(self, path, val: float):
        self.blu_log_debug(f"BluController set_vol() {path=} {val=}")
        if val is not None and self.MIN_VAL <= val <= self.MAX_VAL:
            self.update_state(path, round(val))

    @handle_exception
    def toggle_on_off(self, path, *args):
        self.blu_log_debug(f"BluController toggle_on_off() {path=}")
        val = self.states.get_state(path)
        val_str = "Off" if val == "On" else "Off"
        self.update_state(path, val_str)

    @handle_exception
    def set_on(self, path):
        self.blu_log_debug(f"BluController set_on() {path=}")
        self.update_state(path, "On")

    @handle_exception
    def set_off(self, path):
        self.blu_log_debug(f"BluController set_off() {path=}")
        self.update_state(path, "Off")

    @handle_exception
    def toggle_muted_unmuted(self, path):
        self.blu_log_debug(f"BluController toggle_muted_unmuted() {path=}")
        val = self.states.get_state(path)
        val_str = "Unmuted" if val == "Muted" else "Muted"
        self.update_state(path, val_str)

    @handle_exception
    def set_muted(self, path):
        self.blu_log_debug(f"BluController set_muted() {path=}")
        self.update_state(path, "Muted")

    @handle_exception
    def set_unmuted(self, path):
        self.blu_log_debug(f"BluController set_unmuted() {path=}")
        self.update_state(path, "Unmuted")
