from mojo import context

from lib.eventmanager import EventManager
from lib.lib_yeoul import handle_exception

# ---------------------------------------------------------------------------- #
VERSION = "2025.06.27"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class MicManager(EventManager):
    def __init__(self, max_mic_index=40, last_mic_enabled=True):
        super().__init__("mic_on", "mic_off", "mic_all_off")
        self.max_mic_index = max_mic_index
        self.last_mic_enabled = last_mic_enabled
        self.mics_on = [False] * self.max_mic_index
        self.last_on_mics = []
        self.reset_mic_state()

    @handle_exception
    def reset_mic_state(self):
        context.log.debug("MicManager : reset_mic_state")
        self.mics_on = [False] * self.max_mic_index
        self.last_on_mics = []

    @handle_exception
    def index_to_idx(self, mic_index):
        if 0 < mic_index <= self.max_mic_index:
            return mic_index - 1
        return None

    @handle_exception
    def get_last_mic_enabled(self) -> bool:
        return self.last_mic_enabled

    @handle_exception
    def set_last_mic_enabled(self, is_enabled: bool) -> bool:
        self.last_mic_enabled = is_enabled
        return self.get_last_mic_enabled()

    # ---------------------------------------------------------------------------- #
    @handle_exception
    def turn_mic_on(self, mic_index):
        context.log.debug(f"MicManager : turn_mic_on {mic_index=}")
        self.handle_mic_on(mic_index)

    @handle_exception
    def turn_mic_off(self, mic_index):
        context.log.debug(f"MicManager : turn_mic_off {mic_index=}")
        self.handle_mic_off(mic_index)

    @handle_exception
    def turn_all_mic_off(self):
        context.log.debug("MicManager : turn_all_mic_off")
        self.handle_all_mic_off()

    @handle_exception
    def turn_last_mic_on(self):
        context.log.debug("MicManager : turn_last_mic_on")
        self.handle_last_mic_on()

    # ---------------------------------------------------------------------------- #
    @handle_exception
    def handle_all_mic_off(self):
        context.log.debug("MicManager : handle_all_mic_off")
        self.reset_mic_state()
        self.trigger_event("mic_all_off")

    @handle_exception
    def handle_last_mic_on(self):
        context.log.debug("MicManager : handle_last_mic_on")
        if self.last_on_mics:
            last_mic = self.last_on_mics[-1]
            self.handle_mic_on(last_mic)

    @handle_exception
    def handle_mic_on(self, mic_index):
        context.log.debug(f"MicManager : handle_mic_on {mic_index=}")
        mic_idx = self.index_to_idx(mic_index)
        if mic_idx is not None:
            self.mics_on[mic_idx] = True
            if mic_idx in self.last_on_mics:
                self.last_on_mics.remove(mic_idx)
            self.last_on_mics.append(mic_idx)
            self.trigger_event("mic_on", mic_index)

    @handle_exception
    def handle_mic_off(self, mic_index):
        context.log.debug(f"MicManager : handle_mic_off {mic_index=}")
        mic_idx = self.index_to_idx(mic_index)
        if mic_idx is not None:
            self.mics_on[mic_idx] = False
            if mic_idx in self.last_on_mics:
                self.last_on_mics.remove(mic_idx)
            # ---------------------------------------------------------------------------- #
            if self.last_on_mics:
                self.trigger_event("mic_off", mic_index)
                if self.last_mic_enabled:
                    last_mic_index = self.get_last_on_mic()
                    if last_mic_index:
                        self.trigger_event("mic_on", last_mic_index)
            # if not self.last_on_mics:
            else:
                self.trigger_event("mic_all_off")

    @handle_exception
    def get_mic_status(self, mic_index):
        mic_idx = self.index_to_idx(mic_index)
        if mic_idx is not None:
            return self.mics_on[mic_idx]
        context.log.error(f"MicManager : get_mic_status {mic_index=} 잘못된 인덱스")
        return None

    @handle_exception
    def get_last_on_mic(self):
        return self.last_on_mics[-1] + 1 if self.last_on_mics else None
