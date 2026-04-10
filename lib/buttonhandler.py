import threading

from mojo import context

from lib.eventmanager import EventManager
from lib.lib_yeoul import debounce

# ---------------------------------------------------------------------------- #
VERSION = "2026.04.10"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class ButtonHandler(EventManager):
    def __init__(self, hold_time=30.0, repeat_interval=0.3, trigger_release_on_hold=False, init_action=None, init_handler=None):
        super().__init__("push", "release", "hold", "repeat")
        self.hold_time = hold_time  # 홀드 판정 시간(초)
        self.repeat_interval = repeat_interval  # 반복 이벤트 간격(초)
        self.is_pushed = False  # 현재 버튼 누름 상태
        self.is_hold = False  # 홀드 상태 플래그
        self.trigger_release_on_hold = trigger_release_on_hold  # 홀드 중 릴리즈 이벤트 발생 여부
        self.hold_thread: threading.Thread | None = None  # 홀드 감지 스레드
        self.repeat_thread: threading.Thread | None = None  # 반복 이벤트 스레드
        self.hold_event = threading.Event()  # 홀드 스레드 종료 신호
        self.repeat_event = threading.Event()  # 반복 스레드 종료 신호
        # ---------------------------------------------------------------------------- #
        self.init(init_action, init_handler)

    def init(self, init_action=None, init_handler=None):
        if init_action and init_handler:
            self.on(init_action, init_handler)

    def start_hold(self):
        # hold_time 동안 버튼이 눌려있으면 홀드 이벤트 발생
        self.hold_event.clear()
        # hold_time 시간 동안 hold_event 신호를 기다림. 신호 없으면 False 반환
        # 타임아웃 되었다는 것은 버튼이 계속 눌려있다는 뜻
        if not self.hold_event.wait(self.hold_time):
            if self.is_pushed and not self.is_hold:
                self.is_hold = True
                self.emit("hold")

    def start_repeat(self):
        # 버튼 누름 상태에서 repeat_interval 간격으로 반복 이벤트 발생
        self.repeat_event.clear()
        # is_pushed 상태가 유지되고 종료 신호(repeat_event)가 없을 때까지 반복
        while self.is_pushed and not self.repeat_event.is_set():
            self.emit("repeat")
            # repeat_interval 시간 동안 repeat_event 신호를 기다림
            # 신호 수신 시 루프 탈출
            if self.repeat_event.wait(self.repeat_interval):
                break

    def on(self, action, handler):
        try:
            # ---------------------------------------------------------------------------- #
            if action in ("push", "release", "hold", "repeat"):
                a = action
            # ---------------------------------------------------------------------------- #
            elif action.startswith("hold_"):
                # hold_0.5 형식으로 홀드 시간 설정
                a = "hold"
                hold_time = float(action.split("_")[1])
                # 홀드 시간 범위 검증 (0.5 < hold_time <= 30)
                if not 0.5 <= hold_time <= 30:
                    raise ValueError("0.5 < hold_time <= 30 범위어야 함")
                self.hold_time = hold_time
            # ---------------------------------------------------------------------------- #
            elif action.startswith("hold="):
                # hold=0.5 형식으로 홀드 시간 설정
                a = "hold"
                hold_time = float(action.split("=")[1])
                if not 0.5 <= hold_time <= 30:
                    raise ValueError("0.5 < hold_time <= 30 범위어야 함")
                self.hold_time = hold_time
            # ---------------------------------------------------------------------------- #
            elif action.startswith("repeat_"):
                # repeat_0.3 형식으로 반복 간격 설정
                a = "repeat"
                repeat_interval = float(action.split("_")[1])
                # 반복 간격 범위 검증 (0.1 <= repeat_interval <= 3.0)
                if not 0.1 <= repeat_interval <= 3.0:
                    raise ValueError("0.1 <= repeat_interval <= 3.0 범위어야 함")
                self.repeat_interval = repeat_interval
            # ---------------------------------------------------------------------------- #
            elif action.startswith("repeat="):
                # repeat=0.3 형식으로 반복 간격 설정
                a = "repeat"
                repeat_interval = float(action.split("=")[1])
                if not 0.1 <= repeat_interval <= 3.0:
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
        if evt.value:  # 버튼 눌림 (True)
            self.is_pushed = True
            self.emit("push")
            # ---------------------------------------------------------------------------- #
            # repeat 핸들러가 등록되어 있으면 반복 스레드 시작
            # 기존 스레드가 없거나 실행 중이 아닐 때만 새 스레드 생성 (중복 방지)
            if "repeat" in self.actions and self.actions["repeat"]:
                if self.repeat_thread is None or not self.repeat_thread.is_alive():
                    self.repeat_thread = threading.Thread(target=self.start_repeat, daemon=True)
                    self.repeat_thread.start()
            # ---------------------------------------------------------------------------- #
            # hold 핸들러가 등록되어 있으면 홀드 감지 스레드 시작
            # 기존 스레드가 없거나 실행 중이 아닐 때만 새 스레드 생성 (중복 방지)
            if "hold" in self.actions and self.actions["hold"]:
                if self.hold_thread is None or not self.hold_thread.is_alive():
                    self.hold_thread = threading.Thread(target=self.start_hold, daemon=True)
                    self.hold_thread.start()
        # ---------------------------------------------------------------------------- #
        else:  # 버튼 뗌 (False)
            self.is_pushed = False
            self.repeat_event.set()  # 반복 스레드 종료 신호
            self.hold_event.set()  # 홀드 스레드 종료 신호
            # 홀드 상태가 아니거나 trigger_release_on_hold 설정이 True이면 릴리즈 이벤트 발생
            # (홀드 중에 버튼을 뗄 때도 릴리즈 이벤트를 발생시킬지 결정)
            if not self.is_hold or self.trigger_release_on_hold:
                self.emit("release")
            self.is_hold = False


# ---------------------------------------------------------------------------- #
class LevelHandler(EventManager):

    def __init__(self, init_handler=None, debounce_ms=100):
        super().__init__("level")
        self.debounce_ms = debounce_ms
        context.log.warn("debounce_ms 는 초기화 시 설정되며 이후 변경이 적용되지 않음")

        # 과도한 이벤트 발생을 방지하기 위해 debounce 적용
        # debounce_ms 시간 동안 동일한 신호가 계속 들어오면 마지막 신호만 발생
        @debounce(self.debounce_ms)
        def debounced_emit(value):
            self.emit("level", value)

        self.debounced_emit = debounced_emit

        if init_handler:
            self.on("level", init_handler)

    def handle_event(self, evt):
        # 이벤트 값을 정수로 변환하여 debounce된 이벤트 발생
        value = int(evt.value)
        self.debounced_emit(value)
