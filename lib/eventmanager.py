VERSION = "2026.04.24"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class EventManager:
    def __init__(self, *initial_actions):
        # 초기 이벤트들을 딕셔너리로 초기화 (각 이벤트마다 핸들러 리스트 생성)
        self.actions = {event: [] for event in initial_actions}
        self.event_manager_debug = False

    def log_debug(self, message):
        if self.event_manager_debug:
            print(f"{__class__.__name__} (DEBUG) -- {message}")

    def log_error(self, message):
        print(f"{__class__.__name__} (ERROR) -- {message}")

    def log_warn(self, message):
        print(f"{__class__.__name__} (WARN) -- {message}")

    def log_info(self, message):
        print(f"{__class__.__name__} (INFO) -- {message}")

    def add_event_action(self, action):
        try:
            # 새로운 이벤트 액션을 추가하고, 해당하는 빈 핸들러 리스트 생성
            if action not in self.actions:
                self.actions[action] = []
            else:
                self.log_warn(f"add_event_action() -- event already exists {action=}")
        except Exception as e:
            self.log_error(f"add_event_action() {action=} -- {e=}")

    def remove_event(self, action):
        try:
            # 등록된 이벤트 액션과 해당 핸들러 리스트 전체 삭제
            del self.actions[action]
        except Exception as e:
            self.log_error(f"remove_event() {action=} {e=}")

    def add_event_handler(self, action, handler):
        try:
            # 이벤트가 없으면 새로 생성
            if action not in self.actions:
                if self.event_manager_debug:
                    self.log_debug(f"add_event_handler() -- Event does not exist, adding event action {action=}")
                self.add_event_action(action)
            # 핸들러를 액션의 리스트에 추가 (중복 허용)
            self.actions[action].append(handler)
        except Exception as e:
            self.log_error(f"add_event_handler() {action=} {e=}")

    def remove_event_handler(self, action, handler):
        try:
            # 등록된 핸들러를 리스트에서 제거 (첫 번째 일치 항목만 삭제)
            self.actions[action].remove(handler)
        except Exception as e:
            self.log_error(f"remove_event_handler() {action=} {e=}")

    def on(self, action, handler):
        """add_event_handler의 편의 별칭 메서드"""
        self.add_event_handler(action, handler)

    def trigger_event(self, action, *args, **kwargs):
        try:
            # 등록된 이벤트가 존재하면 해당하는 모든 핸들러를 순차적으로 호출
            if action in self.actions:
                for handler in self.actions[action]:
                    if self.event_manager_debug:
                        self.log_debug(f"trigger_event() {action=} {self.actions[action]=} {args=} {kwargs=}")
                    # 각 핸들러 함수 실행 시 전달받은 인자들 전달
                    handler(*args, **kwargs)
            else:
                self.log_info(f"trigger_event() -- event does not exist {action=} ")
        except Exception as e:
            self.log_error(f"trigger_event() {action=} {e=}")

    def emit(self, action, *args, **kwargs):
        """trigger_event의 편의 별칭 메서드"""
        self.trigger_event(action, *args, **kwargs)
