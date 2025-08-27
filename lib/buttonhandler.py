import threading
from typing import Optional

from mojo import context

from lib.eventmanager import EventManager
from lib.lib_yeoul import debounce

# ---------------------------------------------------------------------------- #
VERSION = "2025.08.27"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class ButtonHandler(EventManager):
    def __init__(
        self, hold_time=30.0, repeat_interval=0.3, trigger_release_on_hold=False, init_action=None, init_handler=None
    ):
        super().__init__("push", "release", "hold", "repeat")
        self.hold_time = hold_time  # 버튼을 누르고 있는 시간
        self.repeat_interval = repeat_interval  # 반복 이벤트 간격
        self.is_pushed = False  # 버튼이 눌렸는지 여부
        self.is_hold = False  # 버튼이 홀드 상태인지 여부
        self.trigger_release_on_hold = trigger_release_on_hold  # 홀드 상태에서 릴리즈 트리거 여부
        self.hold_thread: Optional[threading.Thread] = None
        self.repeat_thread: Optional[threading.Thread] = None
        self.hold_event = threading.Event()
        self.repeat_event = threading.Event()
        # ---------------------------------------------------------------------------- #
        self.init(init_action, init_handler)

    def init(self, init_action=None, init_handler=None):
        if init_action and init_handler:
            self.on(init_action, init_handler)

    def start_hold(self):
        self.hold_event.clear()
        if not self.hold_event.wait(self.hold_time):
            if self.is_pushed and not self.is_hold:
                self.is_hold = True
                self.emit("hold")  # 홀드 이벤트 트리거

    def start_repeat(self):
        self.repeat_event.clear()
        while self.is_pushed and not self.repeat_event.is_set():
            self.emit("repeat")  # 반복 이벤트 트리거
            if self.repeat_event.wait(self.repeat_interval):
                break

    def on(self, action, handler):
        try:
            # ---------------------------------------------------------------------------- #
            if action in ("push", "release", "hold", "repeat"):
                a = action
            # ---------------------------------------------------------------------------- #
            elif action.startswith("hold_"):
                a = "hold"
                hold_time = float(action.split("_")[1])
                if not (0.5 <= hold_time <= 30):
                    raise ValueError("0.5 < hold_time <= 30 범위어야 함")
                self.hold_time = hold_time
            # ---------------------------------------------------------------------------- #
            elif action.startswith("hold="):
                a = "hold"
                hold_time = float(action.split("=")[1])
                if not (0.5 <= hold_time <= 30):
                    raise ValueError("0.5 < hold_time <= 30 범위어야 함")
                self.hold_time = hold_time
            # ---------------------------------------------------------------------------- #
            elif action.startswith("repeat_"):
                a = "repeat"
                repeat_interval = float(action.split("_")[1])
                if not (0.1 <= repeat_interval <= 3.0):
                    raise ValueError("0.1 <= repeat_interval <= 3.0 범위어야 함")
                self.repeat_interval = repeat_interval
            # ---------------------------------------------------------------------------- #
            elif action.startswith("repeat="):
                a = "repeat"
                repeat_interval = float(action.split("=")[1])
                if not (0.1 <= repeat_interval <= 3.0):
                    raise ValueError("0.1 <= repeat_interval <= 3.0 범위어야 함")
                self.repeat_interval = repeat_interval
            # ---------------------------------------------------------------------------- #
            else:
                context.log.error(f"on() {action=} 에러 : 알 수 없는 액션")
                raise ValueError
            # ---------------------------------------------------------------------------- #
            super().on(a, handler)
        except ValueError as exc:
            context.log.error(f"on() {action=} : {exc}")
            raise
        except Exception as exc:
            context.log.error(f"on() {action=} 에러 : 처리 중 오류 발생")
            raise ValueError from exc

    def handle_event(self, evt):
        # ---------------------------------------------------------------------------- #
        if evt.value:
            self.is_pushed = True
            self.emit("push")
            # ---------------------------------------------------------------------------- #
            if "hold" in self.actions and self.actions["hold"]:
                if self.hold_thread is None or not self.hold_thread.is_alive():
                    self.hold_thread = threading.Thread(target=self.start_hold)
                    self.hold_thread.start()
            # ---------------------------------------------------------------------------- #
            if "repeat" in self.actions and self.actions["repeat"]:
                if self.repeat_thread is None or not self.repeat_thread.is_alive():
                    self.repeat_thread = threading.Thread(target=self.start_repeat)
                    self.repeat_thread.start()
        # ---------------------------------------------------------------------------- #
        else:
            self.is_pushed = False
            self.is_hold = False
            self.hold_event.set()  # 스레드 종료 신호
            self.repeat_event.set()  # 스레드 종료 신호
            if self.trigger_release_on_hold or not self.is_hold:
                self.emit("release")  # 릴리즈 이벤트 트리거


# ---------------------------------------------------------------------------- #
class LevelHandler(EventManager):

    def __init__(self, init_handler=None, debounce_ms=100):
        super().__init__("level")
        self.debounce_ms = debounce_ms
        context.log.warn("debounce_ms 는 초기화 시 설정되며 이후 변경이 적용되지 않습니다.")

        @debounce(self.debounce_ms)
        def debounced_emit(value):
            self.emit("level", value)  # 레벨 이벤트 트리거

        self.debounced_emit = debounced_emit

        if init_handler:
            self.on("level", init_handler)

    def handle_event(self, evt):
        value = int(evt.value)
        self.debounced_emit(value)
