from functools import partial

from lib.buttonhandler import ButtonHandler
from lib.lib_tp import tp_add_watcher, tp_set_button
from lib.lib_yeoul import pulse, uni_log_debug, uni_log_error


# ---------------------------------------------------------------------------- #
def handle_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            uni_log_error(f"Relay 에러: {e}")
            return None

    return wrapper


# ---------------------------------------------------------------------------- #
class Relay:
    def __init__(self, devchan_list: list[tuple] = None, tp_list: list = None, port: int = 0, pulse_time: float = 0.5):
        self.devchan_list = devchan_list if devchan_list else []
        self.relay_state = [False] * len(devchan_list)
        self.tp_list = tp_list
        self.pulse_time = pulse_time
        self.tp_port = port
        self.init()

    def init(self):
        for idx, (dv, ch) in enumerate(self.devchan_list):
            self.relay_state[idx] = {
                "dv": dv,
                "ch": int(ch),
                "state": self._get_relay_devchan_state(idx) or False,
            }

    # ---------------------------------------------------------------------------- #
    @handle_exception
    def _get_relay_devchan(self, idx):
        dv, ch = self.devchan_list[idx]
        return dv[ch]

    @handle_exception
    def _get_relay_devchan_state(self, idx):
        return self._get_relay_devchan(idx).state.value

    @handle_exception
    def _set_relay_devchan_state(self, idx, state):
        self._get_relay_devchan(idx).state.value = state

    # ---------------------------------------------------------------------------- #
    @handle_exception
    def get_relay_state(self, idx):
        return self.relay_state[idx]["state"]

    @handle_exception
    def set_relay_state(self, idx, state):
        self._set_relay_devchan_state(idx, state)
        self.update_relay_state(idx)

    @handle_exception
    def set_relay_on(self, idx):
        self.set_relay_state(idx, True)
        self.update_relay_state(idx)
        self.refresh(idx)

    @handle_exception
    def set_relay_off(self, idx):
        self.set_relay_state(idx, False)
        self.update_relay_state(idx)
        self.refresh(idx)

    @handle_exception
    def set_relay_toggle(self, idx):
        self.set_relay_state(idx, not self.get_relay_state(idx))
        self.update_relay_state(idx)
        self.refresh(idx)

    @handle_exception
    def set_relay_pulse(self, idx):
        @pulse(self.pulse_time, self.set_relay_off, idx)
        def inner():
            self.set_relay_on(idx)
            self.update_relay_state(idx)
            self.refresh(idx)

        inner()

    # ---------------------------------------------------------------------------- #
    @handle_exception
    def update_relay_state(self, idx):
        self.relay_state[idx]["state"] = self._get_relay_devchan_state(idx)

    # ---------------------------------------------------------------------------- #
    @handle_exception
    def add_button(self):
        for idx in range(len(self.devchan_list)):
            button_relay_on = ButtonHandler()
            button_relay_on.add_event_handler("push", partial(self.set_relay_on, idx))
            button_relay_off = ButtonHandler()
            button_relay_off.add_event_handler("push", partial(self.set_relay_off, idx))
            button_relay_pulse = ButtonHandler()
            button_relay_pulse.add_event_handler("push", partial(self.set_relay_pulse, idx))
            button_relay_toggle = ButtonHandler()
            button_relay_toggle.add_event_handler("push", partial(self.set_relay_toggle, idx))
            button_relay_momentary = ButtonHandler()
            button_relay_momentary.add_event_handler("push", partial(self.set_relay_on, idx))
            button_relay_momentary.add_event_handler("release", partial(self.set_relay_off, idx))
            for tp in self.tp_list:
                tp_add_watcher(tp, self.tp_port, idx + 1, button_relay_on.handle_event)
                tp_add_watcher(tp, self.tp_port, idx + 101, button_relay_off.handle_event)
                tp_add_watcher(tp, self.tp_port, idx + 201, button_relay_pulse.handle_event)
                tp_add_watcher(tp, self.tp_port, idx + 301, button_relay_toggle.handle_event)
                tp_add_watcher(tp, self.tp_port, idx + 401, button_relay_momentary.handle_event)

    @handle_exception
    def refresh(self, idx):
        # self.show_all_relay_state()
        for tp in self.tp_list:
            tp_set_button(tp, self.tp_port, idx + 1, self.get_relay_state(idx))
            tp_set_button(tp, self.tp_port, idx + 101, not self.get_relay_state(idx))

    def show_all_relay_state(self):
        for idx in range(len(self.devchan_list)):
            uni_log_debug(f"{idx=} {self.relay_state[idx]['state']=}")
            uni_log_debug(f"{idx=} {self._get_relay_devchan_state(idx)=}")
