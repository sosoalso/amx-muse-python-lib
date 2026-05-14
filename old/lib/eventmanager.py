# 마지막 수정일 : 20260505
class EventManagerDebugFlags:
    debug = False


class EventManager:
    def __init__(self, *initial_actions):
        # 초기 이벤트들을 딕셔너리로 초기화 (각 이벤트마다 핸들러 리스트 생성)
        self.actions = {event: [] for event in initial_actions}

    def evt_log_debug(self, message):
        if EventManagerDebugFlags.debug:
            print(f"(DEBUG) - {__class__.__name__} : {message}")

    def evt_log_error(self, message):
        print(f"(ERROR) - {__class__.__name__} : {message}")

    def evt_log_warn(self, message):
        print(f"( WARN) - {__class__.__name__} : {message}")

    def evt_log_info(self, message):
        print(f"( INFO) - {__class__.__name__} : {message}")

    def add_event_action(self, action):
        try:
            # 새로운 이벤트 액션을 추가하고, 해당하는 빈 핸들러 리스트 생성
            if action not in self.actions:
                self.actions[action] = []
            else:
                self.evt_log_warn(f"add_event_action() -- event already exists {action=}")
        except Exception as e:
            self.evt_log_error(f"add_event_action() {action=} -- {e=}")

    def remove_event(self, action):
        try:
            # 등록된 이벤트 액션과 해당 핸들러 리스트 전체 삭제
            del self.actions[action]
        except Exception as e:
            self.evt_log_error(f"remove_event() {action=} {e=}")

    def on(self, action, handler):
        try:
            # 이벤트가 없으면 새로 생성
            if action not in self.actions:
                self.evt_log_debug(f"add_event_handler() -- Event does not exist, adding event action {action=}")
                self.add_event_action(action)
            # 핸들러를 액션의 리스트에 추가 (중복 허용)
            self.actions[action].append(handler)
        except Exception as e:
            self.evt_log_error(f"add_event_handler() {action=} {e=}")

    def remove_event_handler(self, action, handler):
        try:
            # 등록된 핸들러를 리스트에서 제거 (첫 번째 일치 항목만 삭제)
            self.actions[action].remove(handler)
        except Exception as e:
            self.evt_log_error(f"remove_event_handler() {action=} {e=}")

    def emit(self, action, *args, **kwargs):
        try:
            # 등록된 이벤트가 존재하면 현재 핸들러 목록의 복사본을 순차적으로 호출
            if action in self.actions:
                handlers = list(self.actions[action])
                self.evt_log_debug(f"emit() {action=} {handlers=} {args=} {kwargs=}")
                for handler in handlers:
                    handler(*args, **kwargs)
            else:
                self.evt_log_info(f"emit() -- event does not exist {action=} ")
        except Exception as e:
            self.evt_log_error(f"emit() {action=} {e=}")

    def add_event_handler(self, action, handler):
        """on의 예전 메서드 이름"""
        self.on(action, handler)

    def trigger_event(self, action, *args, **kwargs):
        """emit 의 예전 메서드 이름"""
        self.emit(action, *args, **kwargs)
