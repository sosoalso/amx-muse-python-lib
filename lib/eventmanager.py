# ---------------------------------------------------------------------------- #
def handle_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Exception occurred in {func.__name__}: {e}")
            return None

    return wrapper


# ---------------------------------------------------------------------------- #
class EventManager:
    """Event 관리 클래스
    이 클래스는 이벤트의 등록, 삭제, 트리거 및 이벤트 핸들러 관리를 담당합니다.
    Attributes:
        event_handlers (dict): 이벤트 이름을 키로 하고 해당 이벤트에 등록된 핸들러 리스트를 값으로 가지는 딕셔너리
    Methods:
    add_event_name(name: str) -> None:
        새로운 이벤트를 등록합니다. 이미 존재하는 이벤트인 경우 메시지를 출력합니다.
    remove_event(name: str) -> None:
        기존 이벤트를 제거합니다. 존재하지 않는 이벤트를 제거하려 할 경우 예외가 발생합니다.
    add_event_handler(name: str, handler: callable) -> None:
        특정 이벤트에 핸들러를 등록합니다. 이벤트가 존재하지 않을 경우 새로 생성합니다.
        이미 등록된 핸들러의 경우 중복 등록되지 않습니다.
    remove_event_handler(name: str, handler: callable) -> None:
        특정 이벤트에서 핸들러를 제거합니다. 존재하지 않는 핸들러를 제거하려 할 경우 예외가 발생합니다.
    trigger_event(name: str, *args, **kwargs) -> None:
        특정 이벤트를 트리거하고 등록된 모든 핸들러를 실행합니다.
        각 핸들러는 전달된 인자들을 받아 실행됩니다.
    Args:
        *initial_events_name_list: 초기화 시 등록할 이벤트 이름들의 가변 인자
    Example:
        >>> em = EventManager('event1', 'event2')
        >>> em.add_event_handler('event1', lambda x: print(x))
        >>> em.trigger_event('event1', 'Hello World')
        Hello World
    """

    def __init__(self, *initial_events_name_list):
        self.event_handlers = {event: [] for event in initial_events_name_list}

    @handle_exception
    def add_event_name(self, name):
        if name not in self.event_handlers:
            self.event_handlers[name] = []
        else:
            print(f"Event already exists: {name=}")

    @handle_exception
    def remove_event(self, name):
        del self.event_handlers[name]

    def add_event_handler(self, name, handler):
        if name not in self.event_handlers:
            self.event_handlers[name] = [handler]
        elif handler not in self.event_handlers[name]:
            self.event_handlers[name].append(handler)
        else:
            print(f"Handler already registered for event: {name=}")

    @handle_exception
    def remove_event_handler(self, name, handler):
        self.event_handlers[name].remove(handler)

    @handle_exception
    def trigger_event(self, name, *args, **kwargs):
        if name in self.event_handlers:
            for handler in self.event_handlers[name]:
                # print(f"{name=} {handler=}")
                handler(*args, **kwargs)
        else:
            print(f"No such event: {name=}")


# ---------------------------------------------------------------------------- #
