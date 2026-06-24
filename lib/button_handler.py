# 마지막 수정일 : 20260625
import threading

from lib.event_manager import EventManager
from lib.utility import debounce, start_thread


def log_error(message):
    print(f"(ERROR) - buttonhandler : {message}")


class ButtonHandler(EventManager):
    def __init__(self, hold_time=30.0, repeat_interval=0.3, trigger_release_on_hold=False, init_action=None, init_handler=None):
        super().__init__("push", "release", "hold", "repeat")
        self.hold_time = hold_time  # 홀드 판정 시간(초)
        self.repeat_interval = repeat_interval  # 반복 이벤트 간격(초)
        self._is_pushed = False  # 현재 버튼 누름 상태
        self._is_hold = False  # 홀드 상태 플래그
        self.trigger_release_on_hold = trigger_release_on_hold  # 홀드 중 릴리즈 이벤트 발생 여부
        self._event_hold = threading.Event()  # 홀드 스레드 종료 신호
        self._event_repeat = threading.Event()  # 반복 스레드 종료 신호
        # self._counter = 0
        self.init(init_action, init_handler)

    def init(self, init_action=None, init_handler=None):
        """초기 액션 및 핸들러 설정"""
        if init_action and init_handler:
            self.on(init_action, init_handler)

    def start_hold(self):
        """hold_time 동안 버튼이 눌려있으면 홀드 이벤트 발생"""
        # hold_time 시간 동안 hold_event 신호를 기다림. 신호 없으면 False 반환
        # 타임아웃 되었다는 것은 버튼이 계속 눌려있다는 뜻
        if not self._event_hold.wait(self.hold_time):
            if self._is_pushed and not self._is_hold:
                self._is_hold = True
                try:
                    self.emit("hold")
                except Exception as e:
                    log_error(f"start_hold() : emit error {e=}")

    def start_repeat(self):
        """버튼 누름 상태에서 repeat_interval 간격으로 반복 이벤트 발생"""
        # is_pushed 상태가 유지되고 종료 신호(repeat_event)가 없을 때까지 반복
        while self._is_pushed and not self._event_repeat.is_set():
            try:
                self.emit("repeat")
            except Exception as e:
                log_error(f"start_repeat() : emit error {e=}")
                break
            # repeat_interval 시간 동안 repeat_event 신호를 기다림
            # 신호 수신 시 루프 탈출
            if self._event_repeat.wait(self.repeat_interval):
                break

    def on(self, action, handler):
        try:
            a = None
            if action in ("push", "release", "hold", "repeat"):
                a = action
            elif action.startswith("hold_"):
                # hold_0.5 형식으로 홀드 시간 설정
                a = "hold"
                hold_time = float(action.split("_")[1])
                # 홀드 시간 범위 검증 (0.5 < hold_time <= 30)
                if not 0.5 <= hold_time <= 30:
                    raise ValueError("must be in the range 0.5 <= hold_time <= 30")
                self.hold_time = hold_time
            elif action.startswith("hold="):
                # hold=0.5 형식으로 홀드 시간 설정
                a = "hold"
                hold_time = float(action.split("=")[1])
                if not 0.5 <= hold_time <= 30:
                    raise ValueError("must be in the range 0.5 <= hold_time <= 30")
                self.hold_time = hold_time
            elif action.startswith("repeat_"):
                # repeat_0.3 형식으로 반복 간격 설정
                a = "repeat"
                repeat_interval = float(action.split("_")[1])
                # 반복 간격 범위 검증 (0.1 <= repeat_interval <= 3.0)
                if not 0.1 <= repeat_interval <= 3.0:
                    raise ValueError("must be in the range 0.1 <= repeat_interval <= 3.0")
                self.repeat_interval = repeat_interval
            elif action.startswith("repeat="):
                # repeat=0.3 형식으로 반복 간격 설정
                a = "repeat"
                repeat_interval = float(action.split("=")[1])
                if not 0.1 <= repeat_interval <= 3.0:
                    raise ValueError("must be in the range 0.1 <= repeat_interval <= 3.0")
                self.repeat_interval = repeat_interval
            else:
                log_error(f"on() unknown {action=}")
                return
            if a is not None:
                super().on(a, handler)
        except ValueError as e:
            log_error(f"on() {action=} : {e=}")
        except Exception as e:
            log_error(f"on() {action=} {e=}")

    def handle_event(self, evt):
        if evt.value:  # 버튼 눌림 (True)
            if self._is_pushed:
                return
            self._is_pushed = True
            self._is_hold = False
            # self._counter += 1
            # press_id = self._counter
            self._event_repeat.clear()
            self._event_hold.clear()
            self.emit("push")
            # repeat 핸들러가 등록되어 있으면 반복 스레드 시작
            if "repeat" in self.actions and self.actions["repeat"]:
                start_thread(self.start_repeat)
            # hold 핸들러가 등록되어 있으면 홀드 감지 스레드 시작
            if "hold" in self.actions and self.actions["hold"]:
                start_thread(self.start_hold)
        else:  # 버튼 뗌 (False)
            if not self._is_pushed:
                return
            self._is_pushed = False
            self._event_repeat.set()  # 반복 스레드 종료 신호
            self._event_hold.set()  # 홀드 스레드 종료 신호
            # 홀드 상태가 아니거나 trigger_release_on_hold 설정이 True이면 릴리즈 이벤트 발생
            # (홀드 중에 버튼을 뗄 때도 릴리즈 이벤트를 발생시킬지 결정)
            if not self._is_hold or self.trigger_release_on_hold:
                self.emit("release")
            self._is_hold = False


class LevelHandler(EventManager):
    # 경고 -- debounce_ms는 초기화 중에 설정되며 이후에는 변경사항이 적용되지 않습니다
    def __init__(self, init_handler=None, debounce_ms=100):
        super().__init__("level")
        self.debounce_ms = debounce_ms

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
