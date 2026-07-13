# 마지막 수정일 : 20260713
"""이벤트 이름 → 핸들러 리스트를 관리하는 pub/sub 모듈.

장치 드라이버나 매니저 클래스(MicManager 등)가 상속하거나 인스턴스로 만들어,
상태 변화가 생기면 emit() 으로 구독자들에게 알리는 용도로 쓴다.
on() 으로 구독, off() 로 해제, emit() 으로 발행하는 단순한 구조다.
"""
import functools
import threading

from lib.utility import handler_loc, CommonLogger

# ---------------------------------------------------------------------------- #
event_manager_logger = CommonLogger()
# ---------------------------------------------------------------------------- #


def log_debug(message):
    event_manager_logger.log_debug(message)


def log_error(message):
    event_manager_logger.log_error(message)


def log_warn(message):
    event_manager_logger.log_warn(message)


def log_info(message):
    event_manager_logger.log_info(message)


class EventManager:
    """이벤트 pub/sub 관리자.

    - actions : {이벤트 이름: [핸들러, ...]} 딕셔너리
    - 생성자에 이벤트 이름들을 넘기면 미리 등록된다 (emit 시 "없는 이벤트" 로그 방지)
    - 사용 흐름: mgr.on("mic_on", handler) 로 구독 → mgr.emit("mic_on", 3) 으로 발행
      → 등록된 핸들러들이 등록 순서대로 호출된다.
    """
    def __init__(self, *initial_actions):
        self.actions = {event: [] for event in initial_actions}
        self._event_lock = threading.Lock()

    # ---------------------------------------------------------------------------- #
    def add_event_action(self, action):
        """이벤트 이름을 미리 등록한다. 이미 있으면 경고 로그만 남기고 기존 핸들러는 유지."""
        try:
            with self._event_lock:
                if action not in self.actions:
                    self.actions[action] = []
                else:
                    log_warn(f"add_event_action() -- event already exists {action=}")
        except Exception as e:
            log_error(f"add_event_action() {action=} -- {e=}")

    def remove_event_action(self, action):
        """이벤트 이름을 통째로 제거한다. 등록돼 있던 핸들러들도 함께 사라진다."""
        try:
            with self._event_lock:
                del self.actions[action]
        except Exception as e:
            log_error(f"remove_event_action() {action=} {e=}")

    # ---------------------------------------------------------------------------- #
    def on(self, action, handler, unique=False):
        """이벤트에 핸들러를 등록한다.

        - 없는 이벤트면 자동 생성 후 등록
        - unique=True 면 같은 핸들러의 중복 등록을 막는다 (기본은 중복 허용)
        """
        try:
            with self._event_lock:
                if action not in self.actions:
                    log_debug(f"on() -- event does not exist, adding {action=}")
                    self.actions[action] = []
                if unique and handler in self.actions[action]:
                    log_warn(f"on() -- handler already exists {action=} handler={handler_loc(handler)}")
                    return
                self.actions[action].append(handler)
            log_debug(f"on() {action=} handler={handler_loc(handler)}")
        except Exception as e:
            log_error(f"on() {action=} handler={handler_loc(handler)} {e=}")

    # ---------------------------------------------------------------------------- #
    def on_unique(self, action, handler):
        self.on(action, handler, unique=True)

    def once(self, action, handler):
        """한 번만 실행되는 핸들러 등록. 첫 emit 때 실행 후 자동 해제된다.

        실제 등록되는 건 wrapper 이므로, 실행 전에 수동으로 off 하려면 반환값(wrapper)을 써야 한다.
        """
        @functools.wraps(handler)
        def wrapper(*args, **kwargs):
            # 먼저 자신을 해제한 뒤 실행 → 핸들러 안에서 emit 이 또 일어나도 재실행 안 됨
            self.off(action, wrapper)
            handler(*args, **kwargs)

        self.on(action, wrapper)
        return wrapper

    # ---------------------------------------------------------------------------- #
    def off(self, action, handler):
        """핸들러 등록 해제. 없는 이벤트/핸들러면 에러 로그만 남긴다."""
        try:
            with self._event_lock:
                self.actions[action].remove(handler)
        except Exception as e:
            log_error(f"off() {action=} handler={handler_loc(handler)} {e=}")

    # ---------------------------------------------------------------------------- #
    def emit(self, action, *args, **kwargs):
        """이벤트 발행. 등록된 핸들러들을 등록 순서대로 동기 호출한다.

        개별 핸들러 예외는 로그만 남기고 다음 핸들러를 계속 호출한다.
        없는 이벤트면 info 로그만 남기고 조용히 반환.
        """
        try:
            with self._event_lock:
                if action not in self.actions:
                    log_info(f"emit() -- event does not exist {action=}")
                    return
                # 핸들러 목록을 스냅샷으로 복사 → 호출 도중 on/off 로 목록이 바뀌어도 안전
                handlers = list(self.actions[action])
            log_debug(f"emit() {action=} {args=} {kwargs=}")
            for handler in handlers:
                try:
                    handler(*args, **kwargs)
                except Exception as e:
                    log_error(f"emit() {action=} handler={handler_loc(handler)} {e=}")
        except Exception as e:
            log_error(f"emit() {action=} {e=}")
            raise

    # ---------------------------------------------------------------------------- #
    def remove_event_handler(self, action, handler):
        """off의 예전 메서드 이름"""
        self.off(action, handler)

    def remove_event_listener(self, action, handler):
        """off의 다른 이름"""
        self.off(action, handler)

    def add_event_handler(self, action, handler):
        """on의 예전 메서드 이름"""
        self.on(action, handler)

    def trigger_event(self, action, *args, **kwargs):
        """emit 의 예전 메서드 이름"""
        self.emit(action, *args, **kwargs)
