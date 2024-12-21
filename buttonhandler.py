# ---------------------------------------------------------------------------- #
import concurrent.futures
import time

from eventmanager import EventManager


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
class ButtonHandler(EventManager):
    def __init__(self, hold_time=2.0, repeat_interval=0.5, trigger_release_on_hold=False):
        super().__init__("push", "release", "hold", "repeat")
        self.hold_time = hold_time
        self.repeat_interval = repeat_interval
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)
        self.is_pushed = False
        self.is_hold = False
        self.trigger_release_on_hold = trigger_release_on_hold

    @simple_exception_handler
    def init_executor(self):
        self._executor.shutdown(wait=False)
        self._executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

    @simple_exception_handler
    def start_repeat(self):
        while self.is_pushed:
            self.trigger_event("repeat")
            time.sleep(self.repeat_interval)

    @simple_exception_handler
    def start_hold(self):
        while self.is_pushed:
            time.sleep(self.hold_time)
            if self.is_pushed and not self.is_hold:
                self.is_hold = True
                self.trigger_event("hold")

    @simple_exception_handler
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
class LevelHandler(EventManager):
    def __init__(self):
        super().__init__("level")

    @simple_exception_handler
    def add_event_handler(self, handler):
        if "level" not in self.event_handlers:
            self.event_handlers["level"] = [handler]
        elif handler not in self.event_handlers["level"]:
            self.event_handlers["level"].append(handler)
        else:
            print("Handler already registered for event: level")

    @simple_exception_handler(AttributeError, ValueError)
    def handle_event(self, evt):
        value = int(evt.value)
        self.trigger_event("level", value=value)


# ---------------------------------------------------------------------------- #
