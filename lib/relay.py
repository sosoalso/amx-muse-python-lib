from mojo import context

from lib.button import add_button_ss
from lib.lib_tp import tp_set_button
from lib.lib_yeoul import pulse

# ---------------------------------------------------------------------------- #
VERSION = "2025.06.24"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class Relay:
    def __init__(self, devchan_list: list[tuple], tp_list: list, port: int, pulse_time: float = 0.5):
        self.devchan_list = devchan_list if devchan_list else []
        self.relay_state = [{} for _ in range(len(devchan_list))]
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
    def _get_relay_devchan(self, idx):
        dv, ch = self.devchan_list[idx]
        return dv[ch]

    def _get_relay_devchan_state(self, idx):
        return self._get_relay_devchan(idx).state.value

    def _set_relay_devchan_state(self, idx, state):
        self._get_relay_devchan(idx).state.value = state

    # ---------------------------------------------------------------------------- #
    def get_relay_state(self, idx):
        return self.relay_state[idx]["state"]

    def set_relay_state(self, idx, state):
        self._set_relay_devchan_state(idx, state)
        self.update_relay_state(idx)

    def set_relay_on(self, idx):
        self.set_relay_state(idx, True)
        self.update_relay_state(idx)
        self.refresh_relay_button(idx)

    def set_relay_off(self, idx):
        self.set_relay_state(idx, False)
        self.update_relay_state(idx)
        self.refresh_relay_button(idx)

    def set_relay_toggle(self, idx):
        self.set_relay_state(idx, not self.get_relay_state(idx))
        self.update_relay_state(idx)
        self.refresh_relay_button(idx)

    def set_relay_pulse(self, idx):
        @pulse(self.pulse_time, self.set_relay_off, idx)
        def inner():
            self.set_relay_on(idx)
            self.update_relay_state(idx)
            self.refresh_relay_button(idx)

        inner()

    # ---------------------------------------------------------------------------- #
    def update_relay_state(self, idx):
        self.relay_state[idx]["state"] = self._get_relay_devchan_state(idx)

    # ---------------------------------------------------------------------------- #
    def add_relay_button(self):
        for idx in range(len(self.devchan_list)):
            add_button_ss(self.tp_list, self.tp_port, idx + 1, "push", lambda idx=idx: self.set_relay_on(idx))
            add_button_ss(self.tp_list, self.tp_port, idx + 101, "push", lambda idx=idx: self.set_relay_off(idx))
            add_button_ss(self.tp_list, self.tp_port, idx + 201, "push", lambda idx=idx: self.set_relay_pulse(idx))
            add_button_ss(self.tp_list, self.tp_port, idx + 301, "push", lambda idx=idx: self.set_relay_toggle(idx))
            add_button_ss(self.tp_list, self.tp_port, idx + 301, "push", lambda idx=idx: self.set_relay_toggle(idx))
            add_button_ss(self.tp_list, self.tp_port, idx + 401, "push", lambda idx=idx: self.set_relay_on(idx))
            add_button_ss(self.tp_list, self.tp_port, idx + 401, "release", lambda idx=idx: self.set_relay_off(idx))

    def refresh_relay_button(self, idx):
        for tp in self.tp_list:
            tp_set_button(tp, self.tp_port, idx + 1, self.get_relay_state(idx))
            tp_set_button(tp, self.tp_port, idx + 101, not self.get_relay_state(idx))

    def show_all_relay_state(self):
        for idx in range(len(self.devchan_list)):
            context.log.debug(f"{idx=} {self.relay_state[idx]['state']=}")
            context.log.debug(f"{idx=} {self._get_relay_devchan_state(idx)=}")
