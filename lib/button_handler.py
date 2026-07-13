# 마지막 수정일 : 20260713
"""터치패널 원시 이벤트를 push/release/hold/repeat 등의 액션으로 가공하는 계층.

ButtonHandler: 버튼의 눌림/뗌 이벤트를 받아 push, release, hold(길게 누름),
repeat(누르는 동안 반복) 이벤트로 변환해 발행한다.
LevelHandler: 레벨(슬라이더 등) 값 변화를 debounce 처리해 level 이벤트로 발행한다.
보통 직접 생성하지 않고 lib.button 의 add_button()/add_level() 을 통해 사용한다.
"""
import threading

from lib.event_manager import EventManager
from lib.utility import CommonLogger, debounce, start_thread

# ---------------------------------------------------------------------------- #
button_handler_logger = CommonLogger()
# ---------------------------------------------------------------------------- #


def log_error(message):
    button_handler_logger.log_error(message)


# ---------------------------------------------------------------------------- #


class ButtonHandler(EventManager):
    """버튼 하나의 상태 머신.

    handle_event() 로 원시 눌림/뗌 이벤트를 받아 push/release/hold/repeat
    이벤트를 발행한다. hold/repeat 은 push 시점에 각각 전용 스레드로 처리하며,
    push 마다 새 Event 객체를 만들어 이전 push 의 스레드와 신호가 섞이지 않게 한다.
    사용 흐름: handler.on("push", cb) 등록 → 터치패널 이벤트가 handle_event 로 유입.
    """

    def __init__(self, hold_time=30.0, repeat_interval=0.3, trigger_release_on_hold=False, init_action=None, init_handler=None):
        super().__init__("push", "release", "hold", "repeat")
        self.hold_time = hold_time  # 홀드 판정 시간(초)
        self.repeat_interval = repeat_interval  # 반복 이벤트 간격(초)
        self._is_pushed = False  # 현재 버튼 누름 상태
        self._is_hold = False  # 홀드 상태 플래그
        self.trigger_release_on_hold = trigger_release_on_hold  # 홀드 중 릴리즈 이벤트 발생 여부
        self._event_hold = threading.Event()  # 홀드 스레드 종료 신호 (push 마다 새로 생성)
        self._event_repeat = threading.Event()  # 반복 스레드 종료 신호 (push 마다 새로 생성)
        self.init(init_action, init_handler)

    def init(self, init_action=None, init_handler=None):
        """초기 액션 및 핸들러 설정"""
        if init_action and init_handler:
            self.on(init_action, init_handler)

    def start_hold(self, stop_event: threading.Event):
        """hold_time 동안 버튼이 눌려있으면 홀드 이벤트 발생"""
        # stop_event 는 이 push 전용 Event - 이전/다음 push 의 신호와 섞이지 않음
        if not stop_event.wait(self.hold_time):
            if self._is_pushed and not self._is_hold:
                self._is_hold = True
                try:
                    # emit: hold()
                    self.emit("hold")
                except Exception as e:
                    log_error(f"start_hold() : emit error {e=}")

    def start_repeat(self, stop_event: threading.Event):
        """버튼 누름 상태에서 repeat_interval 간격으로 반복 이벤트 발생"""
        # stop_event 는 이 push 전용 Event - 이전/다음 push 의 신호와 섞이지 않음
        # 릴리즈 신호를 놓치는 비정상 상황에 대비해 반복 횟수를 100회로 제한 (안전장치)
        for _ in range(100):
            if not self._is_pushed or stop_event.is_set():
                break
            if stop_event.wait(self.repeat_interval):
                break
            try:
                # emit: repeat()
                self.emit("repeat")
            except Exception as e:
                log_error(f"start_repeat() : emit error {e=}")
                break

    def on(self, action, handler):
        """액션에 핸들러 등록.

        "hold_1.5" / "hold=1.5" / "repeat_0.3" / "repeat=0.3" 형식으로
        홀드 시간·반복 간격을 함께 지정할 수 있다 (핸들러 전체에 적용됨).
        알 수 없는 액션이나 범위 밖 값은 에러 로그만 남기고 등록하지 않는다.
        """
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
        """터치패널 원시 버튼 이벤트 진입점. evt.value 참이면 push, 거짓이면 release 처리.

        push 시 hold/repeat 핸들러가 등록되어 있을 때만 해당 스레드를 시작한다.
        """
        if evt.value:  # 버튼 눌림 (True)
            self._is_pushed = True
            self._is_hold = False
            # push 마다 새 Event 생성 - 이전 push 의 스레드가 아직 살아있어도
            # 그 스레드는 자기 전용 Event(이미 set 됨)를 보고 있으므로 신호가 섞이지 않음
            self._event_repeat = threading.Event()
            self._event_hold = threading.Event()
            # emit: push()
            self.emit("push")
            if self.actions.get("repeat"):
                start_thread(self.start_repeat, self._event_repeat)
            if self.actions.get("hold"):
                start_thread(self.start_hold, self._event_hold)
        else:  # 버튼 뗌 (False)
            self._is_pushed = False
            self._event_repeat.set()  # 반복 스레드 종료 신호
            self._event_hold.set()  # 홀드 스레드 종료 신호
            # 홀드 상태가 아니거나 trigger_release_on_hold 설정이 True이면 릴리즈 이벤트 발생
            # (홀드 중에 버튼을 뗄 때도 릴리즈 이벤트를 발생시킬지 결정)
            if not self._is_hold or self.trigger_release_on_hold:
                # emit: release()
                self.emit("release")
            self._is_hold = False


class LevelHandler(EventManager):
    """레벨(볼륨 슬라이더 등) 값 변화 처리기.

    연속으로 쏟아지는 레벨 이벤트를 debounce 로 걸러 마지막 값만
    level 이벤트로 발행한다. handler.on("level", cb) 로 콜백 등록.
    """

    # 경고 -- debounce_ms는 초기화 중에 설정되며 이후에는 변경사항이 적용되지 않습니다
    def __init__(self, init_handler=None, debounce_ms=100):
        super().__init__("level")
        self.debounce_ms = debounce_ms

        # 과도한 이벤트 발생을 방지하기 위해 debounce 적용
        # debounce_ms 시간 동안 동일한 신호가 계속 들어오면 마지막 신호만 발생
        @debounce(self.debounce_ms)
        def debounced_emit(value):
            self.emit("level", value)

        # emit: level(value: int)
        self.debounced_emit = debounced_emit
        if init_handler:
            self.on("level", init_handler)

    def handle_event(self, evt):
        # 이벤트 값을 정수로 변환하여 debounce된 이벤트 발생
        value = int(evt.value)
        self.debounced_emit(value)
