from mojo import context

# ---------------------------------------------------------------------------- #
VERSION = "2025.06.20"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class EventManager:
    def __init__(self, *initial_events_name_list):
        self.event_handlers = {event: [] for event in initial_events_name_list}

    def add_event_name(self, name):
        try:
            if name not in self.event_handlers:
                self.event_handlers[name] = []
            else:
                context.log.error(f"add_event_name 에러 : 이벤트가 이미 존재합니다. {name=}")
        except Exception as e:
            context.log.error(f"trigger_event {name=} 에러 : {e}")
            context.log.debug(f"trigger_event {name=} 에러 : {e.__traceback__}")

    def remove_event(self, name):
        try:
            del self.event_handlers[name]
        except Exception as e:
            context.log.error(f"trigger_event {name=} 에러 : {e}")
            context.log.debug(f"trigger_event {name=} 에러 : {e.__traceback__}")

    def add_event_handler(self, name, handler):
        try:
            if name not in self.event_handlers:
                self.event_handlers[name] = [handler]
            elif handler not in self.event_handlers[name]:
                self.event_handlers[name].append(handler)
            else:
                context.log.error(f"remove_event 에러 : 해당 이벤트에 동일한 핸들러가 이미 등록돼있습니다. {name=}")
        except Exception as e:
            context.log.error(f"trigger_event {name=} 에러 : {e}")
            context.log.debug(f"trigger_event {name=} 에러 : {e.__traceback__}")

    def remove_event_handler(self, name, handler):
        try:
            self.event_handlers[name].remove(handler)
        except Exception as e:
            context.log.error(f"trigger_event {name=} 에러 : {e}")
            context.log.debug(f"trigger_event {name=} 에러 : {e.__traceback__}")

    def trigger_event(self, name, *args, **kwargs):
        try:
            if name in self.event_handlers:
                for handler in self.event_handlers[name]:
                    context.log.debug(f"trigger_event {name=} 발생")
                    handler(*args, **kwargs)
            else:
                context.log.error(f"trigger_event 에러 : 해당 이벤트가 없습니다 {name=}")
        except Exception as e:
            context.log.error(f"trigger_event {name=} 에러 : {e}")
            context.log.debug(f"trigger_event {name=} 에러 : {e.__traceback__}")
