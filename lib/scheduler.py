# 마지막 수정일 : 20260713
"""setTimeout/setInterval 스타일의 간단한 스레드 기반 스케줄러.

set_timeout/set_interval 로 등록한 함수는 별도 데몬 스레드에서 실행되고,
반환된 schedule 을 cancel() 에 넘기면 중단된다. 콜백 안에서 다시
set_timeout/set_interval 을 호출해 다음 예약을 이어가는 체이닝 패턴을 지원한다
(예: dv_pjlink.py 의 폴링 초기화 코드 참고).
"""

import atexit
import threading
from typing import Callable

from lib.utility import CommonLogger, handler_loc


class Scheduler(CommonLogger):
    """이름이 있는 스케줄 그룹 하나. 인스턴스별로 schedules 목록/shutdown 을 따로 관리한다."""

    def __init__(self, name="Scheduler"):
        self.name = name
        self.schedules = []
        self._lock = threading.Lock()
        self._local = threading.local()
        atexit.register(self.shutdown)

    def _get_current_schedule(self):
        # 스레드 로컬: "지금 이 스레드에서 실행 중인 콜백이 속한 schedule" (체이닝 취소 검사용)
        return getattr(self._local, "current_schedule", None)

    def _set_current_schedule(self, schedule):
        self._local.current_schedule = schedule

    def _create(self, kind):
        # 콜백 안에서 다시 set_interval/set_timeout 을 호출해 새 예약을 잇는 경우,
        # 그 사이 부모 schedule 이 이미 취소됐다면 새 예약을 만들지 않는다 (취소 후 되살아나는 것 방지)
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

        # func 실행 중에는 "현재 schedule"을 이 스레드 로컬에 세팅 -> func 안에서 만드는 새 예약이 부모를 알 수 있게 함
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
        """schedule 을 중단시킨다. 이미 실행 중인 콜백은 끝까지 실행되고, 다음 예약부터 멈춘다."""
        self._stop(schedule)

    def set_interval(self, interval: int | float, func: Callable):
        """interval 초마다 func 을 반복 실행한다. 반환된 schedule 을 cancel() 에 넘기면 중단."""
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
                        self.log_error(f"set_interval() func={handler_loc(func)} {e=}")
            finally:
                self._finalize(schedule)

        thread = threading.Thread(target=wrapper, daemon=True)
        schedule["thread"] = thread
        thread.start()
        return schedule

    def set_timeout(self, delay: int | float, func: Callable):
        """delay 초 뒤에 func 을 한 번 실행한다. cancel() 로 실행 전에 취소 가능."""
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
                        self.log_error(f"set_timeout() func={handler_loc(func)} {e=}")
            finally:
                self._finalize(schedule)

        thread = threading.Thread(target=wrapper, daemon=True)
        schedule["thread"] = thread
        thread.start()
        return schedule

    def shutdown(self):
        """모든 schedule 을 취소하고, 실행 중이던 스레드가 끝날 때까지 잠깐 기다린다 (atexit 에도 등록됨)."""
        atexit.unregister(self.shutdown)  # 누적 방지
        with self._lock:
            schedules = list(self.schedules)
        for schedule in schedules:
            self._stop(schedule)
        current = threading.current_thread()
        for schedule in schedules:
            thread = schedule.get("thread")
            if thread and thread.is_alive() and thread is not current:
                thread.join(timeout=2.0)
