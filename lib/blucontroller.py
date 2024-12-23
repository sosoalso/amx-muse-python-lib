# ---------------------------------------------------------------------------- #
from typing import Union

MIN_VAL = -60  # 최소 값
MAX_VAL = 6  # 최대 값
UNIT_VAL = 1  # 단위 값


# ---------------------------------------------------------------------------- #
def handle_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Exception occurred in {func.__name__}: {e}")
            return None

    return wrapper


# ---------------------------------------------------------------------------- #
class BluSimpleObserver:
    # 옵저버 리스트 초기화
    def __init__(self):
        self._observers = []

    @handle_exception
    # 옵저버 추가
    def subscribe(self, observer):
        self._observers.append(observer)

    @handle_exception
    # 옵저버 제거
    def unsubscribe(self, observer):
        self._observers.remove(observer)

    @handle_exception
    # 모든 옵저버에게 알림
    def notify(self, *args, **kwargs):
        for observer in self._observers:
            observer(*args, **kwargs)


# ---------------------------------------------------------------------------- #
class BluComponentState:
    # 상태 저장 딕셔너리 초기화
    def __init__(self):
        self._states = {}
        self._event = BluSimpleObserver()  # 이벤트 옵저버 초기화

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
    @property
    def MIN_VAL(self):
        return self.MIN_VAL

    @property
    def MAX_VAL(self):
        return self.MAX_VAL

    @property
    def UNIT_VAL(self):
        return self.UNIT_VAL

    # ---------------------------------------------------------------------------- #
    def __init__(
        self,
        device,
        component_states=BluComponentState(),
        min_val=MIN_VAL,
        max_val=MAX_VAL,
        unit_val=UNIT_VAL,
    ):
        self.device = device  # 장치 설정
        self.component_states = component_states  # 컴포넌트 상태 설정
        self.MIN_VAL = min_val  # 최소 값 설정
        self.MAX_VAL = max_val  # 최대 값 설정
        self.UNIT_VAL = unit_val  # 볼륨 조절 단위 값 설정

    # dB 값을 터치패널 0-255 값으로 변환
    @handle_exception
    def db_to_tp(self, x):
        x_min = self.MIN_VAL
        x_max = self.MAX_VAL
        y_min = 0
        y_max = 255
        y = (x - x_min) * (y_max - y_min) / (x_max - x_min) + y_min
        return y

    # 터치패널 0-255 값을 dB 값으로 변환
    @handle_exception
    def tp_to_db(self, x):
        x_min = 0
        x_max = 255
        y_min = self.MIN_VAL
        y_max = self.MAX_VAL
        y = (x - x_min) * (y_max - y_min) / (x_max - x_min) + y_min
        return y

    # ---------------------------------------------------------------------------- #
    @handle_exception
    def init(self, *path_lists: list[tuple[str, ...]]):
        for path_list in path_lists:
            for path in path_list:
                component = self.get_component(path)
                if component is not None:
                    # 초기 값 업데이트
                    self.component_states.update_state(path, component.value)
                    # 감시자 추가
                    component.watch(lambda evt, path=path: self.component_states.update_state(path, evt.value))
                    # 이벤트 오버라이드
                    self.component_states.override_notify(path)

    # ---------------------------------------------------------------------------- #
    # 컴포넌트 가져오기
    @handle_exception
    def get_component(self, path: tuple[str, ...]):
        if not isinstance(path, tuple):
            raise TypeError("comp_path must be a tuple")
        nested_component = self.device.Audio
        for p in path:
            nested_component = nested_component[p]
        return nested_component

    # ---------------------------------------------------------------------------- #
    # 컴포넌트 값 업데이트
    @handle_exception
    def _update_component_value(self, path: tuple[str, ...], new_value: Union[str, float]):
        if self.device.isOffline():
            return
        component = self.get_component(path)
        if component is not None:
            component.value = new_value

    # ---------------------------------------------------------------------------- #
    # 사용자 함수
    # ---------------------------------------------------------------------------- #
    def vol_up(self, path):
        val = self.component_states.get_state(path)
        if val is not None and val <= self.MAX_VAL - self.UNIT_VAL:
            self._update_component_value(path, round(val + self.UNIT_VAL))

    def vol_down(self, path):
        val = self.component_states.get_state(path)
        if val is not None and val >= self.MIN_VAL + self.UNIT_VAL:
            self._update_component_value(path, round(val - self.UNIT_VAL))

    def set_vol(self, path, val: float):
        if val is not None and self.MIN_VAL <= val <= self.MAX_VAL:
            self._update_component_value(path, round(val))

    def toggle_on_off(self, path, *args):
        val = self.component_states.get_state(path)
        val_str = "Off" if val == "On" else "Off"
        self._update_component_value(path, val_str)

    def set_on(self, path):
        self._update_component_value(path, "On")

    def set_off(self, path):
        self._update_component_value(path, "Off")

    def toggle_muted_unmuted(self, path):
        val = self.component_states.get_state(path)
        val_str = "Unmuted" if val == "Muted" else "Muted"
        self._update_component_value(path, val_str)

    def set_muted(self, path):
        self._update_component_value(path, "Muted")

    def set_unmuted(self, path):
        self._update_component_value(path, "Unmuted")


# ---------------------------------------------------------------------------- #
