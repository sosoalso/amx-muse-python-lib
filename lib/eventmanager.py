# ---------------------------------------------------------------------------- #
from mojo import context


# ---------------------------------------------------------------------------- #
def handle_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            context.log.error(f"Exception occurred in {func.__name__}: {e}")
            return None

    return wrapper


# ---------------------------------------------------------------------------- #
class EventManager:
    def __init__(self, *initial_events_name_list):
        self.event_handlers = {event: [] for event in initial_events_name_list}

    @handle_exception
    def add_event_name(self, name):
        if name not in self.event_handlers:
            self.event_handlers[name] = []
        else:
            context.log.debug(f"Event already exists: {name=}")

    @handle_exception
    def remove_event(self, name):
        del self.event_handlers[name]

    def add_event_handler(self, name, handler):
        if name not in self.event_handlers:
            self.event_handlers[name] = [handler]
        elif handler not in self.event_handlers[name]:
            self.event_handlers[name].append(handler)
        else:
            context.log.debug(f"Handler already registered for event: {name=}")

    @handle_exception
    def remove_event_handler(self, name, handler):
        self.event_handlers[name].remove(handler)

    @handle_exception
    def trigger_event(self, name, *args, **kwargs):
        if name in self.event_handlers:
            for handler in self.event_handlers[name]:
                handler(*args, **kwargs)
        else:
            context.log.debug(f"No such event: {name=}")


# ---------------------------------------------------------------------------- #
