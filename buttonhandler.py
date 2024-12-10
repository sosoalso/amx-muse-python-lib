# ---------------------------------------------------------------------------- #
import concurrent.futures
import time

from eventmanager import EventManager


# ---------------------------------------------------------------------------- #
class ButtonHandler(EventManager):
    def __init__(self, hold_time=2.0, repeat_interval=0.5, trigger_release_on_hold=False):
        super().__init__("push", "release", "hold", "repeat")
        self.hold_time = hold_time
        self.repeat_interval = repeat_interval
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.is_pushed = False
        self.is_hold = False
        self.trigger_release_on_hold = trigger_release_on_hold

    def init_executor(self):
        self._executor.shutdown(wait=False)
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

    def start_repeat(self):
        while self.is_pushed:
            self.trigger_event("repeat")
            time.sleep(self.repeat_interval)

    def start_hold(self):
        while self.is_pushed:
            # print("start_hold")
            time.sleep(self.hold_time)
            if self.is_pushed and not self.is_hold:
                self.is_hold = True
                self.trigger_event("hold")

    def handle_event(self, evt):
        if evt.value:
            self.is_pushed = True
            self.trigger_event("push")
            self._executor.submit(self.start_hold)
            self._executor.submit(self.start_repeat)
        else:
            self.is_pushed = False
            if self.trigger_release_on_hold or not self.is_hold:
                self.trigger_event("release")
            self.is_hold = False
            self.init_executor()


# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
