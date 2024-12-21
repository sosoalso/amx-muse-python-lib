# ---------------------------------------------------------------------------- #
MIN_VAL = -60
MAX_VAL = 6
UNIT_VAL = 1


# ---------------------------------------------------------------------------- #
def simple_exception_handler(*exceptions):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                print(f"Exception occurred in {func.__name__}: {e}")
                return None
            except Exception as e:
                print(f"Exception occurred in {func.__name__}: {e}")
                return None

        return wrapper

    return decorator


# ---------------------------------------------------------------------------- #
class BluComponentState:
    def __init__(self):
        self._states = {}
        self._event = BluSimpleObserver()

    @simple_exception_handler
    def update_state(self, key, val):
        self.set_state(key, val)
        self._event.notify(key)

    @simple_exception_handler
    def override_notify(self, key):
        self._event.notify(key)

    @simple_exception_handler
    def get_state(self, key):
        return self._states.get(key, None)

    @simple_exception_handler
    def set_state(self, key, val):
        self._states[key] = val

    @simple_exception_handler
    def subscribe(self, observer):
        self._event.subscribe(observer)

    @simple_exception_handler
    def unsubscribe(self, observer):
        self._event.unsubscribe(observer)


# ---------------------------------------------------------------------------- #
class BluSimpleObserver:
    def __init__(self):
        self._observers = []

    @simple_exception_handler
    def subscribe(self, observer):
        self._observers.append(observer)

    @simple_exception_handler
    def unsubscribe(self, observer):
        self._observers.remove(observer)

    @simple_exception_handler
    def notify(self, *args, **kwargs):
        for observer in self._observers:
            observer(*args, **kwargs)


# ---------------------------------------------------------------------------- #
class BluController:
    def __init__(self, device, component_states, min_val=MIN_VAL, max_val=MAX_VAL, unit_val=UNIT_VAL):
        self.device = device
        self.component_states = component_states
        self.MIN_VAL = min_val
        self.MAX_VAL = max_val
        self.UNIT_VAL = unit_val

    @property
    def MIN_VAL(self):
        return self.MIN_VAL

    @property
    def MAX_VAL(self):
        return self.MAX_VAL

    @property
    def UNIT_VAL(self):
        return self.UNIT_VAL

    @simple_exception_handler
    def db_to_tp(self, x):
        x_min = self.MIN_VAL
        x_max = self.MAX_VAL
        y_min = 0
        y_max = 255
        y = (x - x_min) * (y_max - y_min) / (x_max - x_min) + y_min
        return y

    @simple_exception_handler
    def tp_to_db(self, x):
        x_min = 0
        x_max = 255
        y_min = self.MIN_VAL
        y_max = self.MAX_VAL
        y = (x - x_min) * (y_max - y_min) / (x_max - x_min) + y_min
        return y

    @simple_exception_handler
    def init(self, *path_lists):
        for path_list in path_lists:
            for path in path_list:
                component = self.get_component(path)
                if component is not None:
                    self.component_states.update_state(path, component.value)
                    component.watch(lambda evt, path=path: self.component_states.update_state(path, evt.value))
                    self.component_states.override_notify(path)

    @simple_exception_handler
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

    # ---------------------------------------------------------------------------- #
    def _update_component_value(self, path, new_value):
        if self.device.isOffline():
            return
        component = self.get_component(path)
        if component is not None:
            component.value = new_value

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
        if val == "On":
            self._update_component_value(path, "Off")
        elif val == "Off":
            self._update_component_value(path, "On")

    def set_on(self, path):
        self._update_component_value(path, "On")

    def set_off(self, path):
        self._update_component_value(path, "Off")

    def toggle_muted_unmuted(self, path):
        val = self.component_states.get_state(path)
        if val == "Muted":
            self._update_component_value(path, "Unmuted")
        elif val == "Unmuted":
            self._update_component_value(path, "Muted")

    def set_muted(self, path):
        self._update_component_value(path, "Muted")

    def set_unmuted(self, path):
        self._update_component_value(path, "Unmuted")


# ---------------------------------------------------------------------------- #
