# from mojo import context


def log_warn(msg):
    print(f"WARNING: {msg}")


def log_error(msg):
    print(f"ERROR: {msg}")


def log_debug(msg):
    print(f"DEBUG: {msg}")


# ---------------------------------------------------------------------------- #
VERSION = "2025.07.26"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class EventManager:
    def __init__(self, *initial_actions):
        self.actions = {event: [] for event in initial_actions}

    def add_event_action(self, action):
        try:
            if action not in self.actions:
                self.actions[action] = []
            else:
                log_warn(f"add_event_action() {action=} : 이벤트가 이미 존재합니다. ")
        except Exception as e:
            log_error(f"add_event_action() 에러 {action=} : {e}")

    def remove_event(self, action):
        try:
            del self.actions[action]
        except Exception as e:
            log_error(f"remove_event() 에러 {action=} : {e}")

    def add_event_handler(self, action, handler):
        try:
            if action not in self.actions:
                log_debug(f"add_event_handler() {action=} : 해당 이벤트가 없습니다. 이벤트 액션을 추가합니다.")
                self.add_event_action(action)
            if handler not in self.actions[action]:
                self.actions[action].append(handler)
            else:
                log_debug(
                    f"add_event_handler() {action=} : 해당 이벤트에 동일한 핸들러가 이미 등록돼있습니다. {handler=} {self.actions[action]=}"
                )
                log_debug("그래도 추가는 할겁니다.")
                self.actions[action].append(handler)
        except Exception as e:
            log_error(f"add_event_handler() 에러 {action=} : {e}")

    def on(self, action, handler):
        """add_event_handler 의 alias"""
        self.add_event_handler(action, handler)

    def remove_event_handler(self, action, handler):
        try:
            self.actions[action].remove(handler)
        except Exception as e:
            log_error(f"remove_event_handler() 에러 {action=} : {e}")

    def trigger_event(self, action, *args, **kwargs):
        try:
            if action in self.actions:
                for handler in self.actions[action]:
                    log_debug(f"trigger_event() 발생 {action=} {self.actions[action]=}")
                    handler(*args, **kwargs)
            else:
                log_error(f"trigger_event() {action=} : 해당 이벤트가 없습니다")
        except Exception as e:
            log_error(f"trigger_event() 에러 {action=} : {e}")

    def emit(self, action, *args, **kwargs):
        """trigger_event 의 alias"""
        self.trigger_event(action, *args, **kwargs)
