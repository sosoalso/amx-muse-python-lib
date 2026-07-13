# 마지막 수정일 : 20260713
"""AMX(NetLinx)의 timeline 기능을 파이썬 스레드로 재구현한 모듈.

밀리초 단위 시간 목록(상대 간격 또는 누적 시각)에 따라 expired 이벤트를
순차적으로 발생시킨다. 순차 전원 제어, 일정 간격 반복 폴링처럼
"정해진 시간표대로 여러 동작을 차례로 실행"해야 할 때 사용한다.
start/stop/pause/resume 으로 제어한다.
"""

import atexit
import threading
import time
from types import SimpleNamespace
from typing import Callable, List

from lib.utility import CommonLogger, handler_loc, start_thread


class Timeline(CommonLogger):
    """시간 목록 기반 반복 타이머.

    사용 흐름: tl = Timeline() → tl.expired.listen(handler) → tl.start([...]).
    start() 시 백그라운드 러너 스레드가 시간 목록을 순회하며 각 지점마다
    expired 이벤트를 발생시킨다. 핸들러는 evt.arguments 로
    sequence(몇 번째 지점), repetition(몇 회차), time(설정값)을 받는다.
    """

    class Expired:
        """expired 이벤트의 구독(listen)/발행(trigger)을 담당하는 내부 클래스.

        AMX timeline API 의 expired 이벤트 형태를 흉내낸 것.
        """

        def __init__(self, owner):
            self._owner = owner
            self._handlers: List[Callable] = []

        def listen(self, handler: Callable):
            """expired 핸들러 등록 (같은 핸들러 중복 등록 방지)."""
            if handler not in self._handlers:
                self._handlers.append(handler)

        def trigger(self, *args, **kwargs):
            """등록된 모든 핸들러를 호출. 핸들러 예외는 로그만 남기고 다음 핸들러 계속 진행."""
            for handler in list(self._handlers):
                try:
                    handler(*args, **kwargs)
                except Exception as e:
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
        """타임라인 시작. 이미 실행 중이면 stop 후 새로 시작한다 (러너 스레드 생성).

        _time: 밀리초 단위 시간 목록 (음수는 걸러냄).
        is_absolute: True 면 각 값을 시작 시점 기준 누적 시각으로,
                     False 면 이전 지점으로부터의 간격으로 해석.
        repeat_count: 0=1회 실행, N=N+1회 실행, -1=무한 반복.
        """
        self.stop()
        atexit.register(self.stop)  # stop()에서 해제했으므로 재등록
        with self._lock:
            self._time = [int(t) for t in _time if int(t) >= 0]
            self.is_absolute = is_absolute
            self.repeat_count = repeat_count
            self._stop_flag.clear()
            self._pause_flag.clear()
            self._resume_event.set()  # 초기 상태: 일시정지 아님

        def runner():
            """백그라운드에서 시간 목록을 순회하며 각 지점마다 trigger() 호출."""
            # 실행 중 start() 재호출로 값이 바뀌어도 영향받지 않도록 스냅샷 사용
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
        """AMX timeline expired 이벤트와 같은 형태(evt.arguments)의 이벤트 객체를 만들어 발행."""
        evt = SimpleNamespace()
        evt.arguments = {}
        evt.arguments["sequence"] = s
        evt.arguments["repetition"] = self.repetition
        evt.arguments["time"] = t
        evt.arguments["this"] = self
        self.expired.trigger(evt)

    def _wait(self, seconds: float) -> bool:
        """seconds 동안 대기. 정상 완료 시 True, stop 신호로 중단되면 False 반환.

        pause 중에는 남은 시간을 차감하지 않고 resume 을 기다린다.
        """
        remaining = max(0.0, seconds)
        while remaining > 0 and not self._stop_flag.is_set():
            # 일시정지 대기 (event 기반)
            if self._pause_flag.is_set():
                self._resume_event.wait(timeout=0.05)
                continue
            # 50ms 단위로 stop/pause 신호 확인 (너무 짧으면 wakeup 이 잦아 부하 증가)
            step = min(0.05, remaining)
            start = time.monotonic()
            if self._stop_flag.wait(step):
                return False
            remaining -= time.monotonic() - start
        return not self._stop_flag.is_set()

    def stop(self):
        """타임라인 중지. 러너 스레드가 끝날 때까지 join (러너 스레드 자신이 부르면 join 생략)."""
        atexit.unregister(self.stop)  # 누적 방지
        self._stop_flag.set()
        self._resume_event.set()  # pause 중 stop 시 대기 해제
        if self._thread_runner and self._thread_runner.is_alive() and threading.current_thread() is not self._thread_runner:
            self._thread_runner.join()
        self._thread_runner = None

    def pause(self):
        """일시정지. 현재 대기 중인 지점의 남은 시간은 그대로 유지된다."""
        self._pause_flag.set()
        self._resume_event.clear()

    def resume(self):
        """일시정지 해제. 남아 있던 대기 시간부터 이어서 진행한다."""
        self._pause_flag.clear()
        self._resume_event.set()
