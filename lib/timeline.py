# 마지막 수정일 : 20260626
import atexit
import threading
import time
from types import SimpleNamespace
from typing import Callable, List

from lib.utility import CommonLogger, start_thread


class Timeline(CommonLogger):
    class Expired:
        def __init__(self, owner):
            self._owner = owner
            self._handlers: List[Callable] = []

        def listen(self, handler: Callable):
            if handler not in self._handlers:
                self._handlers.append(handler)

        def trigger(self, *args, **kwargs):
            for handler in list(self._handlers):
                try:
                    handler(*args, **kwargs)
                except Exception as e:
                    from lib.utility import handler_loc
                    self._owner.log_error(f"expired handler={handler_loc(handler)} {e=}")

    def __init__(self):
        self._thread_runner: threading.Thread | None = None
        self._lock: threading.Lock = threading.Lock()
        self._stop_flag: threading.Event = threading.Event()
        self._pause_flag: threading.Event = threading.Event()
        self._resume_event: threading.Event = threading.Event()
        self._resume_event.set()  # 초기 상태: 일시정지 아님
        self.expired: Timeline.Expired = Timeline.Expired(self)
        # repeat_count: 0=1회 실행, N=N+1회 실행, -1=무한 반복
        self.repeat_count: int = 0
        self.repetition: int = 0
        self.is_absolute: bool = False
        self._time: List[int] = []
        atexit.register(self.stop)

    def start(self, _time: List[int], is_absolute=False, repeat_count=0):
        self.stop()
        atexit.register(self.stop)  # stop()에서 해제했으므로 재등록
        with self._lock:
            self._time = [int(t) for t in _time if int(t) >= 0]
            self.is_absolute = is_absolute
            self.repeat_count = repeat_count
            self._stop_flag.clear()
            self._pause_flag.clear()
            self._resume_event.set()

        def runner():
            with self._lock:
                time_snapshot = list(self._time)
                is_abs = self.is_absolute
            self.repetition = 0
            while not self._stop_flag.is_set() and (self.repeat_count == -1 or self.repetition <= self.repeat_count):
                self.repetition += 1
                # 일시정지 대기 (event 기반, busy-wait 없음)
                while self._pause_flag.is_set():
                    if self._stop_flag.is_set():
                        return
                    self._resume_event.wait(timeout=0.05)
                last_absolute_time = 0.0
                for s, t in enumerate(time_snapshot):
                    if self._stop_flag.is_set():
                        break
                    ts = time.time()
                    self.log_debug(f"Timestamp Start: {ts * 1000}")
                    if is_abs:
                        target_time = float(t / 1000)
                        wait_time = max(0, target_time - last_absolute_time)
                        last_absolute_time = target_time
                        if not self._wait(wait_time):
                            break
                    else:
                        if not self._wait(float(t / 1000)):
                            break
                    self.log_debug(f"Timestamp End: {(time.time() - ts) * 1000}")
                    if self._stop_flag.is_set():
                        break
                    self.trigger(s, t)

        self._thread_runner = start_thread(runner)

    def trigger(self, s: int, t: int):
        evt = SimpleNamespace()
        evt.arguments = {}
        evt.arguments["sequence"] = s
        evt.arguments["repetition"] = self.repetition
        evt.arguments["time"] = t
        evt.arguments["this"] = self
        self.expired.trigger(evt)

    def _wait(self, seconds: float) -> bool:
        remaining = max(0.0, seconds)
        while remaining > 0 and not self._stop_flag.is_set():
            # 일시정지 대기 (event 기반)
            if self._pause_flag.is_set():
                self._resume_event.wait(timeout=0.05)
                continue
            step = min(0.01, remaining)
            start = time.monotonic()
            if self._stop_flag.wait(step):
                return False
            remaining -= time.monotonic() - start
        return not self._stop_flag.is_set()

    def stop(self):
        atexit.unregister(self.stop)  # 누적 방지
        self._stop_flag.set()
        self._resume_event.set()  # pause 중 stop 시 대기 해제
        if self._thread_runner and self._thread_runner.is_alive() and threading.current_thread() is not self._thread_runner:
            self._thread_runner.join()
        self._thread_runner = None

    def pause(self):
        self._pause_flag.set()
        self._resume_event.clear()

    def resume(self):
        self._pause_flag.clear()
        self._resume_event.set()
