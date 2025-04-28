# ---------------------------------------------------------------------------- #
import threading
from concurrent.futures import ThreadPoolExecutor

# ---------------------------------------------------------------------------- #
from lib.eventmanager import EventManager


# ---------------------------------------------------------------------------- #
def handle_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Exception occurred in {func.__name__}: {e}")
            return None

    return wrapper


# ---------------------------------------------------------------------------- #
class ButtonHandler(EventManager):
    def __init__(self, hold_time=2.0, repeat_interval=0.5, trigger_release_on_hold=False):
        super().__init__("push", "release", "hold", "repeat")
        self.hold_time = hold_time  # 버튼을 누르고 있는 시간
        self.repeat_interval = repeat_interval  # 반복 이벤트 간격
        self._executor = ThreadPoolExecutor(max_workers=2)  # 스레드 풀 초기화
        self.is_pushed = False  # 버튼이 눌렸는지 여부
        self.is_hold = False  # 버튼이 홀드 상태인지 여부
        self.trigger_release_on_hold = trigger_release_on_hold  # 홀드 상태에서 릴리즈 트리거 여부

    @handle_exception
    def init_executor(self):
        self._executor.shutdown(wait=False)  # 기존 스레드 풀 종료
        self._executor = ThreadPoolExecutor(max_workers=2)  # 새로운 스레드 풀 초기화

    @handle_exception
    def start_repeat(self):
        threading.Event().wait(self.repeat_interval)  # 반복 간격 대기
        while self.is_pushed:
            self.trigger_event("repeat")  # 반복 이벤트 트리거
            threading.Event().wait(self.repeat_interval)  # 반복 간격 대기

    @handle_exception
    def start_hold(self):
        while self.is_pushed:
            threading.Event().wait(self.hold_time)  # 홀드 시간 대기
            if self.is_pushed and not self.is_hold:
                self.is_hold = True
                self.trigger_event("hold")  # 홀드 이벤트 트리거

    @handle_exception
    def handle_event(self, evt):
        if evt.value:
            self.is_pushed = True
            self.trigger_event("push")  # 푸시 이벤트 트리거
            self._executor.submit(self.start_hold)  # 홀드 시작
            self._executor.submit(self.start_repeat)  # 반복 시작
        else:
            self.is_pushed = False
            if self.trigger_release_on_hold or not self.is_hold:
                self.trigger_event("release")  # 릴리즈 이벤트 트리거
            self.is_hold = False
            self.init_executor()  # 스레드 풀 초기화


# ---------------------------------------------------------------------------- #
class LevelHandler(EventManager):
    def __init__(self):
        super().__init__("level")

    @handle_exception
    def add_event_handler(self, handler, *args):
        if "level" not in self.event_handlers:
            self.event_handlers["level"] = [handler]  # 레벨 이벤트 핸들러 추가
        elif handler not in self.event_handlers["level"]:
            self.event_handlers["level"].append(handler)  # 중복되지 않으면 핸들러 추가
        else:
            print("Handler already registered for event: level")

    @handle_exception
    def handle_event(self, evt):
        value = int(evt.value)
        self.trigger_event("level", value=value, actuator=True)  # 레벨 이벤트 트리거


# ---------------------------------------------------------------------------- #
if __name__ == "__main__":
    pass
