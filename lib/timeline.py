import concurrent.futures
import threading
import time
from types import SimpleNamespace
from typing import Callable, List

# ---------------------------------------------------------------------------- #
VERSION = "2025.09.27"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class Timeline:
    class Expired:
        def __init__(self):
            self._handlers: List[Callable] = []

        def listen(self, handler: Callable):
            self._handlers.append(handler)
            print(f"Handler added: {handler}")

        def trigger(self, *args, **kwargs):
            for handler in self._handlers:
                handler(*args, **kwargs)

    def __init__(self):
        self._handlers: List[Callable] = []
        self._thread_dict: dict[int, threading.Thread] = {}
        self._lock: threading.Lock = threading.Lock()
        self._stop_flag: threading.Event = threading.Event()
        self._pause_flag: threading.Event = threading.Event()
        self.expired: Timeline.Expired = Timeline.Expired()
        self.max_repetition: int = 0
        self.repetition: int = 0
        self.is_absolute: bool = False
        self._time: List[int] = []

    def start(self, _time: List[int], is_absolute=False, max_repetition=0):
        with self._lock:
            # todo 범위 및 값 무결성 체크
            self._time = _time
            self.is_absolute = is_absolute
            self.max_repetition = max_repetition
            self._stop_flag.clear()
            self._pause_flag.clear()

        def runner():
            self.repetition = 0
            while not self._stop_flag.is_set() and (self.max_repetition == -1 or self.repetition < self.max_repetition):
                self.repetition += 1
                while self._pause_flag.is_set():
                    time.sleep(0.05)  # Pause 상태에서 잠시 대기
                total_time = 0
                for s, t in enumerate(self._time):
                    if self._stop_flag.is_set():
                        break
                    ts = time.time()
                    print(f"Timestamp Start: {ts*1000}")
                    if self.is_absolute:
                        total_time += t
                        time.sleep(total_time)  # Simulate waiting for the absolute time
                    else:
                        time.sleep(t)  # Simulate waiting for the relative time
                    print(f"Timestamp End: {(time.time() - ts) * 1000}")
                    self.trigger(s, t)

        # ---------------------------------------------------------------------------- #
        threading.Thread(target=runner).start()
        # ---------------------------------------------------------------------------- #

    def trigger(self, s: int, t: int):
        evt = SimpleNamespace()
        evt.arguments = {}
        evt.arguments["sequence"] = s
        evt.arguments["repetition"] = self.repetition
        evt.arguments["time"] = t
        evt.arguments["this"] = self
        self.expired.trigger(evt)

    def stop(self):
        self._stop_flag.set()

    def pause(self):
        self._pause_flag.set()

    def resume(self):
        self._pause_flag.clear()


class TimelineEx:
    class Expired:
        def __init__(self):
            self._handlers: List[Callable] = []

        def listen(self, handler: Callable):
            self._handlers.append(handler)
            print(f"Handler added: {handler}")

        def trigger(self, *args, **kwargs):
            for handler in self._handlers:
                handler(*args, **kwargs)

    def __init__(self):
        self._handlers: List[Callable] = []
        self._executor: concurrent.futures.ThreadPoolExecutor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self._future: concurrent.futures.Future | None = None
        self._lock: threading.Lock = threading.Lock()
        self._stop_flag: threading.Event = threading.Event()
        self._pause_flag: threading.Event = threading.Event()
        self.expired: "TimelineEx.Expired" = TimelineEx.Expired()
        self.max_repetition: int = 0
        self.repetition: int = 0
        self.is_absolute: bool = False
        self._time: List[int] = []

    def _wait(self, duration: float):
        # Interruptible wait that respects stop and pause
        end = time.monotonic() + duration
        while not self._stop_flag.is_set():
            # Handle pause
            while self._pause_flag.is_set() and not self._stop_flag.is_set():
                self._stop_flag.wait(0.05)
            if self._stop_flag.is_set():
                break
            remaining = end - time.monotonic()
            if remaining <= 0:
                break
            self._stop_flag.wait(min(remaining, 0.05))

    def start(self, _time: List[int], is_absolute=False, max_repetition=0):
        with self._lock:
            self._time = _time
            self.is_absolute = is_absolute
            self.max_repetition = max_repetition
            self._stop_flag.clear()
            self._pause_flag.clear()

        def runner():
            self.repetition = 0
            while not self._stop_flag.is_set() and (self.max_repetition == -1 or self.repetition < self.max_repetition):
                self.repetition += 1
                cycle_start = time.monotonic()
                for s, t in enumerate(self._time):
                    if self._stop_flag.is_set():
                        break
                    ts = time.time()
                    print(f"Timestamp Start: {ts * 1000}")
                    if self.is_absolute:
                        # Treat t as absolute offset from cycle start
                        target = cycle_start + t
                        now = time.monotonic()
                        wait_for = max(0, target - now)
                        self._wait(wait_for)
                    else:
                        self._wait(t)
                    print(f"Timestamp End: {(time.time() - ts) * 1000}")
                    if self._stop_flag.is_set():
                        break
                    self.trigger(s, t)

        self._future = self._executor.submit(runner)

    def trigger(self, s: int, t: int):
        evt = SimpleNamespace()
        evt.arguments = {}
        evt.arguments["sequence"] = s
        evt.arguments["repetition"] = self.repetition
        evt.arguments["time"] = t
        evt.arguments["this"] = self
        self.expired.trigger(evt)

    def stop(self):
        self._stop_flag.set()
        if self._future:
            self._future.cancel()

    def pause(self):
        self._pause_flag.set()

    def resume(self):
        self._pause_flag.clear()

    def __del__(self):
        self._executor.shutdown(wait=False)
