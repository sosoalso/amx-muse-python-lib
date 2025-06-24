from mojo import context

# ---------------------------------------------------------------------------- #
VERSION = "2025.06.24"


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
                context.log.error(f"add_event_action 에러 : 이벤트가 이미 존재합니다. {action=}")
        except Exception as e:
            context.log.error(f"trigger_event {action=} 에러 : {e}")
            context.log.debug(f"trigger_event {action=} 에러 : {e.__traceback__}")

    def remove_event(self, action):
        try:
            del self.actions[action]
        except Exception as e:
            context.log.error(f"trigger_event {action=} 에러 : {e}")
            context.log.debug(f"trigger_event {action=} 에러 : {e.__traceback__}")

    def add_event_handler(self, action, handler):
        try:
            if action not in self.actions:
                self.actions[action] = [handler]
            elif handler not in self.actions[action]:
                self.actions[action].append(handler)
            else:
                context.log.error(f"remove_event 에러 : 해당 이벤트에 동일한 핸들러가 이미 등록돼있습니다. {action=}")
        except Exception as e:
            context.log.error(f"trigger_event {action=} 에러 : {e}")
            context.log.debug(f"trigger_event {action=} 에러 : {e.__traceback__}")

    def remove_event_handler(self, action, handler):
        try:
            self.actions[action].remove(handler)
        except Exception as e:
            context.log.error(f"trigger_event {action=} 에러 : {e}")
            context.log.debug(f"trigger_event {action=} 에러 : {e.__traceback__}")

    def trigger_event(self, action, *args, **kwargs):
        try:
            if action in self.actions:
                for handler in self.actions[action]:
                    context.log.debug(f"trigger_event {action=} 발생")
                    handler(*args, **kwargs)
            else:
                context.log.error(f"trigger_event 에러 : 해당 이벤트가 없습니다 {action=}")
        except Exception as e:
            context.log.error(f"trigger_event {action=} 에러 : {e}")
            context.log.debug(f"trigger_event {action=} 에러 : {e.__traceback__}")
