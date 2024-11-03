# ---------------------------------------------------------------------------- #
MIN_VAL = -60
MAX_VAL = 6
UNIT_VAL = 1
# ---------------------------------------------------------------------------- #


def db_to_tp(x):
    try:
        x_min = MIN_VAL
        x_max = MAX_VAL
        y_min = 0
        y_max = 255
        y = (x - x_min) * (y_max - y_min) / (x_max - x_min) + y_min
        return y
    except Exception as e:
        return None


def tp_to_db(x):
    try:
        x_min = 0
        x_max = 255
        y_min = MIN_VAL
        y_max = MAX_VAL
        y = (x - x_min) * (y_max - y_min) / (x_max - x_min) + y_min
        return y
    except Exception as e:
        return None


# ---------------------------------------------------------------------------- #
class BluSimpleObserver:
    def __init__(self):
        self._observers = []

    def subscribe(self, observer):
        self._observers.append(observer)

    def unsubscribe(self, observer):
        self._observers.remove(observer)

    def notify(self, *args, **kwargs):
        # print(f"BluSimpleObserver notify: {args=} {kwargs=}")
        for observer in self._observers:
            observer(*args, **kwargs)


# ---------------------------------------------------------------------------- #
class BluComponentState:
    def __init__(self):
        self._states = {}
        self._event = BluSimpleObserver()

    def update_state(self, key, val):
        # print(f"BluComponentState update_state: {key=}, {val=}")
        self.set_state(key, val)
        self._event.notify(key)

    def override_notify(self, key):
        # print(f"BluComponentState override_notify: {key=}")
        self._event.notify(key)

    # 키-값을 반환
    def get_state(self, key):
        return self._states.get(key, None)

    def set_state(self, key, val):
        self._states[key] = val

    def subscribe(self, observer):
        self._event.subscribe(observer)

    def unsubscribe(self, observer):
        self._event.unsubscribe(observer)


# ---------------------------------------------------------------------------- #
class BluController:

    def __init__(self, device, component_states):
        self.device = device
        self.component_states = component_states

    def init(self, *path_lists):
        try:
            for path_list in path_lists:
                for path in path_list:
                    component = self.get_component(path)
                    if component is not None:
                        self.component_states.update_state(path, component.value)
                        # print(f"{path=}, {component.value=} {self.component_states.get_state(path)=}")
                        component.watch(lambda evt, path=path: self.component_states.update_state(path, evt.value))
                        self.component_states.override_notify(path)
        except Exception as e:
            # print(f"Error in BluController.init: {path=} {e}")

    def get_component(self, path):
        if not isinstance(path, tuple):
            raise TypeError("comp_path must be a tuple")
        try:
            nested_component = self.device.Audio
            for p in path:
                nested_component = nested_component[p]
            return nested_component
        except Exception as e:
            return None

    def vol_up(self, path):
        if self.device.isOffline():
            return
        component = self.get_component(path)
        val = self.component_states.get_state(path)
        if val is None:
            return
        if val <= MAX_VAL - UNIT_VAL:
            component.value = round(val + 1.0)

    def vol_down(self, path):
        if self.device.isOffline():
            return
        component = self.get_component(path)
        val = self.component_states.get_state(path)
        if val is None:
            return
        if val >= MIN_VAL + UNIT_VAL:
            component.value = round(val - 1.0)

    def set_vol(self, path, val: float):
        if self.device.isOffline():
            return
        component = self.get_component(path)
        if val is None:
            return
        if val >= MIN_VAL and val <= MAX_VAL:
            component.value = round(val)

    def toggle_on_off(self, path, *args):
        if self.device.isOffline():
            return
        component = self.get_component(path)
        val = self.component_states.get_state(path)
        if val is None:
            return
        elif val == "On":
            component.value = "Off"
        elif val == "Off":
            component.value = "On"

    def set_on(self, path):
        if self.device.isOffline():
            return
        component = self.get_component(path)
        component.value = "On"

    def set_off(self, path):
        if self.device.isOffline():
            return
        component = self.get_component(path)
        component.value = "Off"

    def toggle_muted_unmuted(self, path):
        if self.device.isOffline():
            return
        component = self.get_component(path)
        val = self.component_states.get_state(path)
        if val == "Muted":
            component.value = "Unmuted"
        elif val == "Unmuted":
            component.value = "Muted"

    def set_muted(self, path):
        if self.device.isOffline():
            return
        component = self.get_component(path)
        val = self.component_states.get_state(path)
        component.value = "Muted"

    def set_unmuted(self, path):
        if self.device.isOffline():
            return
        component = self.get_component(path)
        val = self.component_states.get_state(path)
        component.value = "Unmuted"


# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
