import threading
import time

from mojo import context

from lib.eventmanager import EventManager
from lib.lib_yeoul import handle_exception

# ---------------------------------------------------------------------------- #
VERSION = "2025.06.27"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class ButtonHandler(EventManager):
    def __init__(
        self,
        hold_time=30.0,
        repeat_interval=0.3,
        trigger_release_on_hold=False,
        init_action=None,
        init_handler=None,
    ):
        super().__init__("push", "release", "hold", "repeat")
        self.hold_time = hold_time  # 버튼을 누르고 있는 시간
        self.repeat_interval = repeat_interval  # 반복 이벤트 간격
        self.is_pushed = False  # 버튼이 눌렸는지 여부
        self.is_hold = False  # 버튼이 홀드 상태인지 여부
        self.trigger_release_on_hold = trigger_release_on_hold  # 홀드 상태에서 릴리즈 트리거 여부
        self.hold_thread = None
        self.repeat_thread = None
        # ---------------------------------------------------------------------------- #
        self.init(init_action, init_handler)

    @handle_exception
    def init(self, init_action=None, init_handler=None):
        if init_action and init_handler:
            self.add_event_handler(init_action, init_handler)

    @handle_exception
    def start_repeat(self):
        while self.is_pushed:
            if self.is_pushed:
                self.trigger_event("repeat")  # 반복 이벤트 트리거
            time.sleep(self.repeat_interval)  # 반복 간격 대기

    @handle_exception
    def start_hold(self):
        time.sleep(self.hold_time)  # 홀드 시간 대기
        if self.is_pushed and not self.is_hold:
            self.is_hold = True
            self.trigger_event("hold")  # 홀드 이벤트 트리거

    def add_event_handler(self, action, handler):
        try:
            if action in ("push", "release", "hold", "repeat"):
                a = action
            elif action.startswith("hold_"):
                a = "hold"
                hold_time = float(action.split("_")[1])
                if not (0.5 <= hold_time <= 30):
                    raise ValueError("0.5 < hold_time <= 30 범위어야 함")
                self.hold_time = hold_time
            elif action.startswith("repeat_"):
                a = "repeat"
                repeat_interval = float(action.split("_")[1])
                if not (0.1 <= repeat_interval <= 3.0):
                    raise ValueError("0.1 <= repeat_interval <= 3.0 범위어야 함")
                self.repeat_interval = repeat_interval
            else:
                context.log.error(f"add_event_handler 알 수 없는 액션 {action=}")
                raise ValueError
            super().add_event_handler(a, handler)
        except ValueError as exc:
            context.log.error(f"add_event_handler {action=} : {exc}")
            raise
        except Exception as exc:
            context.log.error(f"add_event_handler {action=} : 처리 중 오류 발생")
            raise ValueError from exc

    @handle_exception
    def handle_event(self, evt):
        if evt.value:
            self.is_pushed = True
            self.trigger_event("push")
            # ---------------------------------------------------------------------------- #
            if self.hold_thread is None or not self.hold_thread.is_alive():
                self.hold_thread = threading.Thread(target=self.start_hold, daemon=True)
                self.hold_thread.start()
            # ---------------------------------------------------------------------------- #
            if self.repeat_thread is None or not self.repeat_thread.is_alive():
                self.repeat_thread = threading.Thread(target=self.start_repeat, daemon=True)
                self.repeat_thread.start()
        else:
            self.is_pushed = False
            if self.trigger_release_on_hold or not self.is_hold:
                self.trigger_event("release")  # 릴리즈 이벤트 트리거
            self.is_hold = False


# ---------------------------------------------------------------------------- #
class LevelHandler(EventManager):
    def __init__(self, init_handler=None):
        super().__init__("level")
        self.init(init_handler)

    @handle_exception
    def init(self, init_handler=None):
        if init_handler:
            self.add_event_handler("level", init_handler)

    @handle_exception
    def handle_event(self, evt):
        value = int(evt.value)
        self.trigger_event("level", value)  # 레벨 이벤트 트리거
