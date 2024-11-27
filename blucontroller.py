# ---------------------------------------------------------------------------- #
# from stub_objectstorage import ObjectStorage
# from userdata import UserData
# ---------------------------------------------------------------------------- #
# TODO : MIN-MAX 값은 외부로 노출돼있는데 내부로 감추고 보다 편하게 지정할 수 있도록 수정 예정
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
class BluComponentState:
    def __init__(self):
        self._states = {}
        self._event = BluSimpleObserver()
        # self._storage = ObjectStorage(db_name="blu_component_state.db")
        # self._userdata = UserData("blu_component_state.json")

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

    # def save(self):
    #     self._userdata.save()
    #     # self._storage.save_json_object("states", self._states)
    # def load(self):
    #     # loaded_states = self._storage.load_json_object("states")
    #     # if loaded_states:
    #     #     self._states = loaded_states
    #     try:
    #         self._states = self._userdata.load()
    #     except Exception as e:
    #         print(f"Error in BluComponentState.load: {e}")


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
            print(f"Error in BluController.init: {path=} {e}")

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
        if val is not None and val <= MAX_VAL - UNIT_VAL:
            self._update_component_value(path, round(val + UNIT_VAL))

    def vol_down(self, path):
        val = self.component_states.get_state(path)
        if val is not None and val >= MIN_VAL + UNIT_VAL:
            self._update_component_value(path, round(val - UNIT_VAL))

    def set_vol(self, path, val: float):
        if val is not None and MIN_VAL <= val <= MAX_VAL:
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


# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
