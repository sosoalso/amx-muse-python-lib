# 마지막 수정일 : 20260514
import threading


class EventManagerDebugFlags:
    debug = False


class EventManager:
    def __init__(self, *initial_actions):
        # 초기 이벤트들을 딕셔너리로 초기화 (각 이벤트마다 핸들러 리스트 생성)
        self.actions = {event: [] for event in initial_actions}
        self._event_lock = threading.Lock()

    def evt_log_debug(self, message):
        if EventManagerDebugFlags.debug:
            print(f"(DEBUG) - {self.__class__.__name__} : {message}", end="\n", flush=True)

    def evt_log_error(self, message):
        print(f"(ERROR) - {self.__class__.__name__} : {message}", end="\n", flush=True)

    def evt_log_warn(self, message):
        print(f"( WARN) - {self.__class__.__name__} : {message}", end="\n", flush=True)

    def evt_log_info(self, message):
        print(f"( INFO) - {self.__class__.__name__} : {message}", end="\n", flush=True)

    def add_event_action(self, action):
        try:
            # 새로운 이벤트 액션을 추가하고, 해당하는 빈 핸들러 리스트 생성
            with self._event_lock:
                if action not in self.actions:
                    self.actions[action] = []
                else:
                    self.evt_log_warn(f"add_event_action() : event already exists {action=}")
        except Exception as e:
            self.evt_log_error(f"add_event_action() : {action=} {e=}")

    def remove_event(self, action):
        try:
            # 등록된 이벤트 액션과 해당 핸들러 리스트 전체 삭제
            with self._event_lock:
                self.actions.pop(action, None)
        except Exception as e:
            self.evt_log_error(f"remove_event() : {action=} {e=}")

    def on(self, action, handler):
        try:
            # 이벤트가 없으면 알림
            with self._event_lock:
                if action not in self.actions:
                    self.evt_log_debug(f"on() : Event does not exist, adding event action {action=}")
                    self.actions[action] = []
                if handler not in self.actions[action]:
                    self.actions[action].append(handler)
                else:
                    self.evt_log_debug(f"on() : handler already registered {action=}")
        except Exception as e:
            self.evt_log_error(f"on() {action=} {e=}")

    def remove_event_handler(self, action, handler):
        try:
            # 등록된 핸들러를 리스트에서 제거 (첫 번째 일치 항목만 삭제)
            with self._event_lock:
                if action in self.actions and handler in self.actions[action]:
                    self.actions[action].remove(handler)
        except Exception as e:
            self.evt_log_error(f"remove_event_handler() {action=} {e=}")

    def emit(self, action, *args, **kwargs):
        try:
            # 등록된 이벤트가 존재하면 현재 핸들러 목록의 복사본을 순차적으로 호출
            with self._event_lock:
                handlers = list(self.actions.get(action, []))
            if not handlers:
                self.evt_log_debug(f"emit() : no handlers {action=}")
                return
            self.evt_log_debug(f"emit() : {action=} {handlers=} {args=} {kwargs=}")
            for handler in handlers:
                try:
                    handler(*args, **kwargs)
                except Exception as e:
                    self.evt_log_error(f"emit() : handler error {action=} {handler=} {e=}")
        except Exception as e:
            self.evt_log_error(f"emit() : {action=} {e=}")

    def add_event_handler(self, action, handler):
        """on의 예전 메서드 이름"""
        self.on(action, handler)

    def trigger_event(self, action, *args, **kwargs):
        """emit 의 예전 메서드 이름"""
        self.emit(action, *args, **kwargs)
