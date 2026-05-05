# 마지막 수정일 : 20260505
import atexit
import threading
import time
from types import SimpleNamespace
from typing import Callable, List


class Timeline:
    class Expired:
        def __init__(self):
            self._handlers: List[Callable] = []

        def listen(self, handler: Callable):
            self._handlers.append(handler)

        def trigger(self, *args, **kwargs):
            # 등록된 모든 핸들러를 순차적으로 실행
            for handler in self._handlers:
                handler(*args, **kwargs)

    def __init__(self):
        self._handlers: List[Callable] = []
        self._thread_runner: threading.Thread
        self._lock: threading.Lock = threading.Lock()
        self._stop_flag: threading.Event = threading.Event()
        self._pause_flag: threading.Event = threading.Event()
        self.expired: Timeline.Expired = Timeline.Expired()
        self.max_repetition: int = 0
        self.repetition: int = 0
        self.is_absolute: bool = False
        self._time: List[int] = []
        self.debug = False
        atexit.register(self.stop)

    def log_debug(self, message):
        if self.debug:
            print(f"{__class__.__name__} DEBUG -- {message}")

    def log_error(self, message):
        print(f"{__class__.__name__} ERROR -- {message}")

    def log_info(self, message):
        print(f"{__class__.__name__} INFO -- {message}")

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
            # 정지 플래그가 설정되지 않고, 반복 횟수 조건을 만족하는 동안 반복
            while not self._stop_flag.is_set() and (self.max_repetition == -1 or self.repetition <= self.max_repetition):
                self.repetition += 1
                # 일시 중지 상태일 때 대기
                while self._pause_flag.is_set():
                    # 최대 0.01초씩 블로킹하여 반응성 유지
                    time.sleep(0.01)
                total_time = 0
                for s, t in enumerate(self._time):
                    if self._stop_flag.is_set():
                        break
                    ts = time.time()
                    self.log_debug(f"Timestamp Start: {ts * 1000}")
                    if self.is_absolute:
                        # 절대 시간 모드: 누적 시간 기준으로 대기
                        total_time += float(t / 1000)
                        time.sleep(total_time)
                    else:
                        # 상대 시간 모드: 각 구간별 시간만큼 대기
                        time.sleep(float(t / 1000))
                    self.log_debug(f"Timestamp End: {(time.time() - ts) * 1000}")
                    self.trigger(s, t)

        # 데몬 스레드에서 타임라인 실행
        self._thread_runner = threading.Thread(target=runner, daemon=True)
        self._thread_runner.start()

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
        if self._thread_runner.is_alive():
            self._thread_runner.join()

    def pause(self):
        self._pause_flag.set()

    def resume(self):
        self._pause_flag.clear()
