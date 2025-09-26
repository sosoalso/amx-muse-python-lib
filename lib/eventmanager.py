from mojo import context

# ---------------------------------------------------------------------------- #
VERSION = "2025.09.25"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class EventManager:
    def __init__(self, *initial_actions):
        self.actions = {event: [] for event in initial_actions}
        self.event_manager_debug = False

    def add_event_action(self, action):
        try:
            if action not in self.actions:
                self.actions[action] = []
            else:
                context.log.warn(f"add_event_action() {action=} 이벤트가 이미 존재함")
        except Exception as e:
            context.log.error(f"add_event_action() {action=} 에러: {e}")

    def remove_event(self, action):
        try:
            del self.actions[action]
        except Exception as e:
            context.log.error(f"remove_event() {action=} 에러: {e}")

    def add_event_handler(self, action, handler):
        try:
            if action not in self.actions:
                if self.event_manager_debug:
                    context.log.debug(f"add_event_handler() {action=} : 해당 이벤트가 없으므로 이벤트 액션 추가")
                self.add_event_action(action)
            if handler not in self.actions[action]:
                self.actions[action].append(handler)
            else:
                context.log.debug(
                    f"add_event_handler() {action=} : 해당 이벤트에 동일한 핸들러가 이미 등록되어 있으나 중복 추가 진행 {handler=} {self.actions[action]=}"
                )
                self.actions[action].append(handler)
        except Exception as e:
            context.log.error(f"add_event_handler() {action=} 에러: {e}")

    def on(self, action, handler):
        """add_event_handler 의 alias"""
        self.add_event_handler(action, handler)

    def remove_event_handler(self, action, handler):
        try:
            self.actions[action].remove(handler)
        except Exception as e:
            context.log.error(f"remove_event_handler() 에러 {action=} : {e}")

    def trigger_event(self, action, *args, **kwargs):
        try:
            if action in self.actions:
                for handler in self.actions[action]:
                    if self.event_manager_debug:
                        context.log.debug(f"trigger_event() 발생 - {action=} {self.actions[action]=} {args=} {kwargs=}")
                    handler(*args, **kwargs)
            else:
                context.log.info(f"trigger_event() {action=} 해당 이벤트 없음")
        except Exception as e:
            context.log.error(f"trigger_event() {action=} 에러: {e}")

    def emit(self, action, *args, **kwargs):
        """trigger_event 의 alias"""
        self.trigger_event(action, *args, **kwargs)
