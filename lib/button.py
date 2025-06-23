from mojo import context

from lib.buttonhandler import ButtonHandler, LevelHandler
from lib.lib_tp import (
    tp_add_notification,
    tp_add_notification_ss,
    tp_add_watcher,
    tp_add_watcher_level,
    tp_add_watcher_level_ss,
    tp_add_watcher_ss,
)

# ---------------------------------------------------------------------------- #
VERSION = "2025.06.20"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
def make_button_handler(action, callback, *args, **kwargs):
    button_handler = ButtonHandler()
    if action == "push":
        a = "push"
    elif action == "release":
        a = "release"
    elif action.startswith("hold_"):
        a = "hold"
        try:
            hold_time = float(action.split("_")[1])
            if hold_time <= 0 or hold_time > 30:
                raise ValueError("hold time is out of range (0 < hold_time <= 30)")
        except Exception as exc:
            raise ValueError(f"Invalid hold time format in action: {action}") from exc
        button_handler.hold_time = hold_time
    elif action.startswith("repeat_"):
        a = "repeat"
        try:
            repeat_interval = float(action.split("_")[1])
            if repeat_interval <= 0 or repeat_interval > 5:
                raise ValueError("repeat interval is out of range (0 < hold_time <= 5)")
            button_handler.repeat_interval = repeat_interval
        except Exception as exc:
            raise ValueError(f"Invalid repeat interval format in action: {action}") from exc
    else:
        raise ValueError(f"make_button_handler : Unknown action : {action}")
    button_handler.add_event_handler(a, lambda: callback(*args, **kwargs))
    return button_handler


def add_button(tp, port, channel, action, callback, *args, **kwargs):
    button_handler = make_button_handler(action, callback, *args, **kwargs)
    tp_add_watcher(tp, port, channel, button_handler.handle_event)
    context.log.debug(
        f"add_button() {tp=} 포트:{port} 채널:{channel} 액션:{action} 콜백:{callback.__name__} 인자: {args=} {kwargs=}"
    )
    return button_handler


def add_button_ss(tp_list, port, channel, action, callback, *args, **kwargs):
    button_handler = make_button_handler(action, callback, *args, **kwargs)
    tp_add_watcher_ss(tp_list, port, channel, button_handler.handle_event)
    context.log.debug(
        f"add_button_ss() {tp_list=} 포트:{port} 채널:{channel} 액션:{action} 콜백:{callback.__name__} 인자: {args=} {kwargs=}"
    )
    return button_handler


def make_level_handler(callback, *args, **kwargs):
    level_handler = LevelHandler()
    level_handler.add_event_handler("level", lambda value: callback(value, *args, **kwargs))
    return level_handler


def add_level(tp, port, channel, callback, *args, **kwargs):
    level_handler = make_level_handler(callback, *args, **kwargs)
    tp_add_watcher_level(tp, port, channel, level_handler.handle_event)
    context.log.debug(f"add_level() {tp=} 포트:{port} 채널:{channel} 콜백:{callback.__name__} 인자: {args=} {kwargs=}")
    return level_handler


def add_level_ss(tp_list, port, channel, callback, *args, **kwargs):
    level_handler = make_level_handler(callback, *args, **kwargs)
    tp_add_watcher_level_ss(tp_list, port, channel, level_handler.handle_event)
    context.log.debug(
        f"add_level_ss() {tp_list=} 포트:{port} 채널:{channel} 콜백:{callback.__name__} 인자: {args=} {kwargs=}"
    )
    return level_handler
