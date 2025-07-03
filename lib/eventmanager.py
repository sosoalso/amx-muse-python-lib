from lib.lib_yeoul import log_debug, log_error

# ---------------------------------------------------------------------------- #
VERSION = "2025.07.03"


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
                log_error(f"add_event_action() 에러 {action=} : 이벤트가 이미 존재합니다. ")
        except Exception as e:
            log_error(f"add_event_action() 에러 {action=} : {e}")
            log_debug(f"add_event_action() 에러 {action=} : {e.__traceback__}")

    def remove_event(self, action):
        try:
            del self.actions[action]
        except Exception as e:
            log_error(f"remove_event() 에러 {action=} : {e}")
            log_debug(f"remove_event() 에러 {action=} : {e.__traceback__}")

    def add_event_handler(self, action, handler):
        try:
            if action not in self.actions:
                self.actions[action] = [handler]
            elif handler not in self.actions[action]:
                self.actions[action].append(handler)
            else:
                log_error(f"add_event_handler() 에러 : 해당 이벤트에 동일한 핸들러가 이미 등록돼있습니다. {action=}")
        except Exception as e:
            log_error(f"add_event_handler() 에러 {action=} : {e}")
            log_debug(f"add_event_handler() 에러 {action=} : {e.__traceback__}")

    def on(self, action, handler):
        """add_event_handler 의 alias"""
        self.add_event_handler(action, handler)

    def remove_event_handler(self, action, handler):
        try:
            self.actions[action].remove(handler)
        except Exception as e:
            log_error(f"remove_event_handler() 에러 {action=} : {e}")
            log_debug(f"remove_event_handler() 에러 {action=} : {e.__traceback__}")

    def trigger_event(self, action, *args, **kwargs):
        try:
            if action in self.actions:
                for handler in self.actions[action]:
                    log_debug(f"trigger_event() 발생 {action=}")
                    handler(*args, **kwargs)
            else:
                log_error(f"trigger_event() {action=} : 해당 이벤트가 없습니다")
        except Exception as e:
            log_error(f"trigger_event() 에러 {action=} : {e}")
            log_debug(f"trigger_event() 에러 {action=} : {e.__traceback__}")

    def emit(self, action, *args, **kwargs):
        """trigger_event 의 alias"""
        self.trigger_event(action, *args, **kwargs)
