# ---------------------------------------------------------------------------- #
def simple_exception_handler(*exceptions):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                print(f"Exception occurred in {func.__name__}: {e}")
                return None
            except Exception as e:
                print(f"Exception occurred in {func.__name__}: {e}")
                return None

        return wrapper

    return decorator


# ---------------------------------------------------------------------------- #
class EventManager:
    def __init__(self, *initial_events_name_list):
        self.event_handlers = {event: [] for event in initial_events_name_list}

    @simple_exception_handler(KeyError)
    def add_event_name(self, name):
        if name not in self.event_handlers:
            self.event_handlers[name] = []
        else:
            print(f"Event already exists: {name=}")

    @simple_exception_handler(KeyError)
    def remove_event(self, name):
        del self.event_handlers[name]

    def add_event_handler(self, name, handler):
        if name not in self.event_handlers:
            self.event_handlers[name] = [handler]
        elif handler not in self.event_handlers[name]:
            self.event_handlers[name].append(handler)
        else:
            print(f"Handler already registered for event: {name=}")

    @simple_exception_handler(KeyError, ValueError)
    def remove_event_handler(self, name, handler):
        self.event_handlers[name].remove(handler)

    @simple_exception_handler
    def trigger_event(self, name, *args, **kwargs):
        if name in self.event_handlers:
            for handler in self.event_handlers[name]:
                # print(f"{name=} {handler=}")
                handler(*args, **kwargs)
            print(f"No such event: {name=}")


# ---------------------------------------------------------------------------- #
