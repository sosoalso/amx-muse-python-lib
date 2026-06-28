# 마지막 수정일 : 20260629
import atexit
import threading
from typing import Callable

from lib.utility import CommonLogger


class Scheduler(CommonLogger):
    def __init__(self, name="Scheduler"):
        self.name = name
        self.schedules = []
        self._lock = threading.Lock()
        self._local = threading.local()
        atexit.register(self.shutdown)

    def _get_current_schedule(self):
        return getattr(self._local, "current_schedule", None)

    def _set_current_schedule(self, schedule):
        self._local.current_schedule = schedule

    def _create(self, kind):
        parent = self._get_current_schedule()
        if parent and parent["stop_event"].is_set():
            return None

        schedule = {"kind": kind, "stop_event": threading.Event(), "thread": None}
        with self._lock:
            self.schedules.append(schedule)
        return schedule

    def _run(self, schedule, func: Callable):
        if schedule["stop_event"].is_set():
            return

        previous = self._get_current_schedule()
        self._set_current_schedule(schedule)
        try:
            func()
        finally:
            self._set_current_schedule(previous)

    def _stop(self, schedule):
        if schedule:
            schedule["stop_event"].set()

    def _finalize(self, schedule):
        with self._lock:
            if schedule in self.schedules:
                self.schedules.remove(schedule)

    def cancel(self, schedule):
        self._stop(schedule)

    def set_interval(self, interval: int | float, func: Callable):
        if not isinstance(interval, (int, float)) or interval <= 0:
            raise ValueError(f"interval must be a positive number, got {interval}")
        if not isinstance(func, Callable):
            raise ValueError(f"func must be Callable, got {type(func)}")

        schedule = self._create("interval")
        if not schedule:
            return None

        stop_event = schedule["stop_event"]

        def wrapper():
            try:
                while not stop_event.wait(interval):
                    try:
                        self._run(schedule, func)
                    except Exception as e:
                        from lib.utility import handler_loc
                        self.log_error(f"set_interval() func={handler_loc(func)} {e=}")
            finally:
                self._finalize(schedule)

        thread = threading.Thread(target=wrapper, daemon=True)
        schedule["thread"] = thread
        thread.start()
        return schedule

    def set_timeout(self, delay: int | float, func: Callable):
        if not isinstance(delay, (int, float)) or delay < 0:
            raise ValueError(f"delay must be a non-negative number, got {delay}")
        if not isinstance(func, Callable):
            raise ValueError(f"func must be Callable, got {type(func)}")

        schedule = self._create("timeout")
        if not schedule:
            return None

        stop_event = schedule["stop_event"]

        def wrapper():
            try:
                if not stop_event.wait(delay):
                    try:
                        self._run(schedule, func)
                    except Exception as e:
                        from lib.utility import handler_loc
                        self.log_error(f"set_timeout() func={handler_loc(func)} {e=}")
            finally:
                self._finalize(schedule)

        thread = threading.Thread(target=wrapper, daemon=True)
        schedule["thread"] = thread
        thread.start()
        return schedule

    def shutdown(self):
        atexit.unregister(self.shutdown)  # 누적 방지
        with self._lock:
            schedules = list(self.schedules)
        for schedule in schedules:
            self._stop(schedule)
        current = threading.current_thread()
        for schedule in schedules:
            thread = schedule.get("thread")
            if thread and thread.is_alive() and thread is not current:
                thread.join()
