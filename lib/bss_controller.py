# 마지막 수정일 : 20260529
from typing import Sequence, Union
from lib.utility import CommonLogger

# 최소 값
MIN_VAL: float = -60.0
# 최대 값
MAX_VAL: float = 6.0
# 단위 값
UNIT_VAL: float = 1.0


class BssObserver:
    # 옵저버 리스트 초기화
    def __init__(self, owner):
        self._observers = []
        self.owner = owner

    # 옵저버 추가
    def subscribe(self, observer):
        self._observers.append(observer)
        self.owner.log_debug(f"BssObserver subscribe {observer=}")

    # 옵저버 제거
    def unsubscribe(self, observer):
        self._observers.remove(observer)
        self.owner.log_debug(f"BssObserver unsubscribe {observer=}")

    # 모든 옵저버에게 알림
    def notify(self, *args, **kwargs):
        self.owner.log_debug(f"BssObserver notify {args=} {kwargs=}")
        for observer in self._observers:
            observer(*args, **kwargs)


class BssState:
    # 상태 저장 딕셔너리 초기화
    def __init__(self, owner):
        self.owner = owner
        self._states = {}
        # 이벤트 옵저버 초기화
        self._event = BssObserver(self.owner)

    # 상태 가져오기
    def get_state(self, key):
        self.owner.log_debug(f"BssState get_state() {key=} val={self._states.get(key, None)}")
        return self._states.get(key, None)

    # 상태 설정하고 변경 알림
    def set_state(self, key, val):
        self._states[key] = val
        self.owner.log_debug(f"BssState set_state() {key=} {val=}")
        # 상태 변경 시 등록된 모든 옵저버에 알림
        self._event.notify(key)

    def remove_state(self, key):
        self.owner.log_debug(f"BssState remove_state() {key=}")
        self._event.unsubscribe(key)
        self._states.pop(key)

    # 상태 변경 강제 알림
    def override_notify(self, key):
        self.owner.log_debug(f"BssState override_notify() {key=}")
        self._event.notify(key)

    # 옵저버 추가
    def subscribe(self, observer):
        self.owner.log_debug(f"BssState subscribe() {observer=}")
        self._event.subscribe(observer)

    # 옵저버 제거
    def unsubscribe(self, observer):
        self.owner.log_debug(f"BssState unsubscribe() {observer=}")
        self._event.unsubscribe(observer)


class BssController(CommonLogger):
    def __init__(self, dv, states=None, min_val=MIN_VAL, max_val=MAX_VAL, unit_val=UNIT_VAL):
        # 장치 설정
        self.dv = dv
        # 컴포넌트 상태 설정
        self.states = BssState(self) if states is None else states
        # 최소 값 설정
        self.MIN_VAL = min_val
        # 최대 값 설정
        self.MAX_VAL = max_val
        # 볼륨 조절 단위 값 설정
        self.UNIT_VAL = unit_val

    def db_to_tp(self, x):
        """dB 값을 터치패널 0-255 범위로 선형 변환"""
        try:
            x_min = self.MIN_VAL
            x_max = self.MAX_VAL
            y_min = 0
            y_max = 255
            # 선형 변환 공식: (입력값 - 입력최소) * (출력최대 - 출력최소) / (입력최대 - 입력최소) + 출력최소
            y = (x - x_min) * (y_max - y_min) / (x_max - x_min) + y_min
            return y
        except Exception as e:
            self.log_error(f"db_to_tp() {e=}")
            return 0

    def tp_to_db(self, x):
        """터치패널 0-255 값을 dB 값으로 선형 변환"""
        x_min = 0
        x_max = 255
        y_min = self.MIN_VAL
        y_max = self.MAX_VAL
        # 선형 변환 공식: (입력값 - 입력최소) * (출력최대 - 출력최소) / (입력최대 - 입력최소) + 출력최소
        y = (x - x_min) * (y_max - y_min) / (x_max - x_min) + y_min
        return y

    def init(self, *path_lists: Sequence[Union[list[str], tuple[str, ...]]]):
        """컴포넌트 초기화: 각 경로의 초기값을 상태에 저장하고 변경 감시 설정"""
        for path_list in path_lists:
            if not isinstance(path_list, (list, tuple)):
                self.log_error("init() : each element of path_lists must be a list or tuple composed of path strings")
                raise TypeError
            for path in path_list:
                if not isinstance(path, tuple):
                    self.log_error("init() : each path must be a tuple composed of path strings")
                    raise TypeError
                component = self.get_component(path)
                if component is not None:
                    # 초기값 저장
                    self.states.set_state(path, component.value)
                    # 컴포넌트의 값 변경을 감시하여 상태 업데이트 (default 파라미터로 path 값 고정)
                    component.watch(lambda evt, path=path, component=component: self._handle_component_update(evt, path, component))

    def _handle_component_update(self, evt, path, component):
        """하나의 컴포넌트에 대한 Watcher 콜백.
        BSS 이벤트는 다양한 콜백 턴에서 매우 가까운 값 변경을 전달할 수 있습니다.
        이전 콜백이 새로운 콜백보다 나중에 실행되는 경우 상태를 덮어쓰지 않습니다.
        """
        evt_value = evt.value
        self.log_debug(f"_handle_component_update() : {component=} {path=} evt.value={evt_value}")
        try:
            current_value = component.value
        except Exception:
            current_value = evt_value
        if not self._values_are_same(current_value, evt_value):
            self.log_debug(f"_handle_component_update() : stale ignored {path=} evt.value={evt_value} component.value={current_value}")
            return
        self.states.set_state(path, evt_value)

    def _values_are_same(self, a, b):
        """숫자형 값은 float 변환 후 비교하고, 변환 불가 값은 원본 값으로 비교."""
        a_float = self.check_val_convert_float(a)
        b_float = self.check_val_convert_float(b)
        if a_float is not None and b_float is not None:
            return abs(a_float - b_float) < 0.000001
        return a == b

    def add_path_event(self, observer):
        """상태 변경 이벤트에 옵저버 등록"""
        self.states.subscribe(observer)

    def subscribe(self, observer):
        self.log_warn("subscribe() : is deprecated, use add_path_event() instead.")
        self.add_path_event(observer)

    def get_component(self, path: tuple[str, ...]):
        """튜플 형식의 경로를 통해 중첩된 컴포넌트 객체 가져오기"""
        if not isinstance(path, tuple):
            self.log_error("get_component() : path must be a tuple composed of strings")
            raise TypeError
        # dv 에서 시작하여 경로의 각 단계마다 인덱싱으로 중첩 컴포넌트 접근
        nested_component = self.dv
        for p in path:
            nested_component = nested_component[p]
        return nested_component

    def get_state(self, path: tuple[str, ...]):
        """경로에 해당하는 상태값 조회"""
        if not isinstance(path, tuple):
            self.log_error("get_state() : path must be composed of strings surrounded by tuple")
            raise TypeError
        self.log_debug(f"get_state() {path=}")
        return self.states.get_state(path)

    def set_state(self, path: tuple[str, ...], new_value: Union[str, float]):
        """컴포넌트 값을 업데이트 (장치가 온라인 상태일 때만 실행)"""
        if self.dv.isOnline():
            component = self.get_component(path)
            if component is not None:
                # override
                # self.states.set_state(path, new_value)
                component.value = new_value
                self.log_debug(f"set_state() {component=} {new_value=}")

    def check_val_convert_float(self, val):
        """값을 float 로 변환 시도, 실패 시 None 반환"""
        try:
            return float(val)
        except (ValueError, TypeError) as e:
            self.log_debug(f"check_val_convert_float() : cannot convert {val=} {e=}")
            return None

    def vol_up(self, path):
        """음량 증가: 현재값에 단위값을 더하고 범위 내 값으로 제한"""
        val_db = self.check_val_convert_float(self.states.get_state(path))
        if val_db is not None:
            self.log_debug(f"vol_up() : {path=} old {val_db=}")
            # 단위값만큼 증가 후 반올림
            val_db = float(round(val_db + self.UNIT_VAL))
            # 범위를 벗어난 값을 MIN/MAX 값으로 제한
            if self.MIN_VAL < val_db < self.MAX_VAL:
                self.set_state(path, val_db)
            elif val_db >= self.MAX_VAL:
                self.set_state(path, self.MAX_VAL)
            elif val_db <= self.MIN_VAL:
                self.set_state(path, self.MIN_VAL)

    def vol_down(self, path):
        """음량 감소: 현재값에서 단위값을 빼고 범위 내 값으로 제한"""
        self.log_debug(f"vol_down() : {path=}")
        val_db = self.check_val_convert_float(self.states.get_state(path))
        if val_db is not None:
            self.log_debug(f"vol_down() : {path=} old {val_db=}")
            # 단위값만큼 감소 후 반올림
            val_db = float(round(val_db - self.UNIT_VAL))
            # 범위를 벗어난 값을 MIN/MAX 값으로 제한
            if self.MIN_VAL < val_db < self.MAX_VAL:
                self.set_state(path, val_db)
            elif val_db >= self.MAX_VAL:
                self.set_state(path, self.MAX_VAL)
            elif val_db <= self.MIN_VAL:
                self.set_state(path, self.MIN_VAL)

    def set_vol(self, path, val: float):
        """음량을 특정값으로 설정: 범위를 벗어난 값은 MIN/MAX 값으로 제한"""
        self.log_debug(f"set_vol() : {path=} {val=}")
        if val is not None:
            val = float(round(val))
            # 범위를 벗어난 값을 MIN/MAX 값으로 제한
            if self.MIN_VAL < val < self.MAX_VAL:
                self.set_state(path, val)
            elif val >= self.MAX_VAL:
                self.set_state(path, self.MAX_VAL)
            elif val <= self.MIN_VAL:
                self.set_state(path, self.MIN_VAL)

    def toggle_on_off(self, path, *args):
        """On/Off 상태 토글"""
        self.log_debug(f"toggle_on_off() : {path=}")
        val = self.states.get_state(path)
        if val == "On":
            val_str = "Off"
        elif val == "Off":
            val_str = "On"
        else:
            return
        self.set_state(path, val_str)

    def set_on(self, path):
        """상태를 'On' 으로 설정"""
        self.log_debug(f"set_on() : {path=}")
        self.set_state(path, "On")

    def set_off(self, path):
        """상태를 'Off' 로 설정"""
        self.log_debug(f"set_off() : {path=}")
        self.set_state(path, "Off")

    def toggle_muted_unmuted(self, path):
        """Muted/Unmuted 상태 토글"""
        self.log_debug(f"toggle_muted_unmuted() : {path=}")
        val = self.states.get_state(path)
        if val == "Unmuted":
            val_str = "Muted"
        elif val == "Muted":
            val_str = "Unmuted"
        else:
            return
        self.set_state(path, val_str)

    def toggle_muted_unmuted_omni(self, path):
        """Muted/Unmuted 상태 토글"""
        self.log_debug(f"toggle_muted_unmuted() : {path=}")
        val = self.states.get_state(path)
        if val == "UnMuted":
            val_str = "Muted"
        elif val == "Muted":
            val_str = "UnMuted"
        else:
            return
        self.set_state(path, val_str)

    def set_muted(self, path):
        """상태를 'Muted' 로 설정"""
        self.log_debug(f"set_muted() : {path=}")
        self.set_state(path, "Muted")

    def set_unmuted(self, path):
        """상태를 'Unmuted' 로 설정"""
        self.log_debug(f"set_unmuted() : {path=}")
        self.set_state(path, "Unmuted")

    def set_muted_omni(self, path):
        """상태를 'Muted' 로 설정"""
        self.log_debug(f"set_muted() : {path=}")
        self.set_state(path, "Muted")

    def set_unmuted_omni(self, path):
        """상태를 'Unmuted' 로 설정"""
        self.log_debug(f"set_unmuted() : {path=}")
        self.set_state(path, "UnMuted")

    def set_val(self, path, val):
        """지정된 경로의 상태값을 설정"""
        self.log_debug(f"set_val() : {path=} {val=}")
        self.set_state(path, val)
