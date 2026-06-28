# 마지막 수정일 : 20260629
import threading

from lib.utility import handler_loc


class EventManagerDebugFlags:
    debug = False


class EventManager:
    def __init__(self, *initial_actions):
        self.actions = {event: [] for event in initial_actions}
        self._actions_lock = threading.RLock()

    def evt_log_debug(self, message):
        if EventManagerDebugFlags.debug:
            print(f"(DEBUG) - {self.__class__.__name__} : {message}")

    def evt_log_error(self, message):
        print(f"(ERROR) - {self.__class__.__name__} : {message}")

    def evt_log_warn(self, message):
        print(f"( WARN) - {self.__class__.__name__} : {message}")

    def evt_log_info(self, message):
        print(f"( INFO) - {self.__class__.__name__} : {message}")

    def add_event_action(self, action):
        try:
            with self._actions_lock:
                if action not in self.actions:
                    self.actions[action] = []
                else:
                    self.evt_log_warn(f"add_event_action() -- event already exists {action=}")
        except Exception as e:
            self.evt_log_error(f"add_event_action() {action=} -- {e=}")

    def remove_event(self, action):
        try:
            with self._actions_lock:
                del self.actions[action]
        except Exception as e:
            self.evt_log_error(f"remove_event() {action=} {e=}")

    def on(self, action, handler):
        try:
            with self._actions_lock:
                if action not in self.actions:
                    self.evt_log_debug(f"on() -- event does not exist, adding {action=}")
                    self.actions[action] = []
                self.actions[action].append(handler)
            self.evt_log_debug(f"on() {action=} handler={handler_loc(handler)}")
        except Exception as e:
            self.evt_log_error(f"on() {action=} handler={handler_loc(handler)} {e=}")

    def remove_event_handler(self, action, handler):
        try:
            with self._actions_lock:
                self.actions[action].remove(handler)
        except Exception as e:
            self.evt_log_error(f"remove_event_handler() {action=} handler={handler_loc(handler)} {e=}")

    def emit(self, action, *args, **kwargs):
        try:
            with self._actions_lock:
                if action not in self.actions:
                    self.evt_log_info(f"emit() -- event does not exist {action=}")
                    return
                handlers = list(self.actions[action])
            self.evt_log_debug(f"emit() {action=} {args=} {kwargs=}")
            for handler in handlers:
                try:
                    handler(*args, **kwargs)
                except Exception as e:
                    self.evt_log_error(f"emit() {action=} handler={handler_loc(handler)} {e=}")
        except Exception as e:
            self.evt_log_error(f"emit() {action=} {e=}")
            raise

    def add_event_handler(self, action, handler):
        """on의 예전 메서드 이름"""
        self.on(action, handler)

    def trigger_event(self, action, *args, **kwargs):
        """emit 의 예전 메서드 이름"""
        self.emit(action, *args, **kwargs)
