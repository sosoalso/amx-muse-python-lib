# ---------------------------------------------------------------------------- #
import threading
import time

from eventmanager import EventManager


# ---------------------------------------------------------------------------- #
class ButtonHandler(EventManager):
    def __init__(self, hold_time=2.0, repeat_interval=0.5, trigger_release_on_hold=False):
        super().__init__("push", "release", "hold", "repeat")
        self.hold_time = hold_time
        self.repeat_interval = repeat_interval
        self.repeat_thread = None
        self.hold_thread = None
        self.is_pushed = False
        self.is_hold = False
        self.trigger_release_on_hold = trigger_release_on_hold

    def start_repeat(self):
        while self.is_pushed:
            self.trigger_event("repeat")
            time.sleep(self.repeat_interval)

    def start_hold(self):
        while self.is_pushed:
            time.sleep(self.hold_time)
            if self.is_pushed and not self.is_hold:
                self.is_hold = True
                self.trigger_event("hold")

    def handle_event(self, evt):
        if evt.value:
            self.is_pushed = True
            self.trigger_event("push")
            if self.repeat_thread is None or not self.repeat_thread.is_alive():
                self.repeat_thread = threading.Thread(target=self.start_repeat)
                self.repeat_thread.start()
            if self.hold_thread is None or not self.hold_thread.is_alive():
                self.hold_thread = threading.Thread(target=self.start_hold)
                self.hold_thread.start()
        else:
            self.is_pushed = False
            if self.trigger_release_on_hold and self.is_hold:
                self.trigger_event("release")
            elif not self.is_hold:
                self.trigger_event("release")
            self.is_hold = False


# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
