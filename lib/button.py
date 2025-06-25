from mojo import context

from lib.buttonhandler import ButtonHandler, LevelHandler
from lib.lib_tp import (
    tp_add_watcher,
    tp_add_watcher_level,
    tp_add_watcher_level_ss,
    tp_add_watcher_ss,
)

# ---------------------------------------------------------------------------- #
VERSION = "2025.06.25"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
def add_button(tp, port, channel, action, callback):
    new_button = ButtonHandler(init_action=action, init_handler=callback)
    tp_add_watcher(tp, port, channel, new_button.handle_event)
    context.log.debug(f"add_button() {tp.id} 포트:{port} 채널:{channel} 액션:{action}")
    return new_button


def add_button_ss(tp_list, port, channel, action, callback):
    new_button = ButtonHandler(init_action=action, init_handler=callback)
    tp_add_watcher_ss(tp_list, port, channel, new_button.handle_event)

    context.log.debug(f"add_button_ss() {[tp.id for tp in tp_list]} 포트:{port} 채널:{channel} 액션:{action}")
    return new_button


def add_level(tp, port, channel, callback):
    level_handler = LevelHandler(init_handler=callback)
    tp_add_watcher_level(tp, port, channel, level_handler.handle_event)
    context.log.debug(f"add_level() {tp=} 포트:{port} 채널:{channel} 콜백:{callback}")
    return level_handler


def add_level_ss(tp_list, port, channel, callback):
    level_handler = LevelHandler(init_handler=callback)
    tp_add_watcher_level_ss(tp_list, port, channel, level_handler.handle_event)
    context.log.debug(f"add_level_ss() {[tp.id for tp in tp_list]} 포트:{port} 레벨:{channel}")
    return level_handler
