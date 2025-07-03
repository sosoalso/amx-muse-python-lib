from mojo import context

from lib.buttonhandler import ButtonHandler, LevelHandler
from lib.lib_tp import (
    tp_add_watcher,
    tp_add_watcher_level,
    tp_add_watcher_level_ss,
    tp_add_watcher_ss,
)
from lib.lib_yeoul import handle_exception

# ---------------------------------------------------------------------------- #
VERSION = "2025.07.03"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
@handle_exception
def add_button(tp, port, button, action, callback):
    new_button = ButtonHandler(init_action=action, init_handler=callback)
    tp_add_watcher(tp, port, button, new_button.handle_event)
    context.log.debug(f"add_button() {tp.id} {port=} {button=} {action=}")
    return new_button


@handle_exception
def add_button_ss(tp_list, port, button, action, callback):
    new_button = ButtonHandler(init_action=action, init_handler=callback)
    tp_add_watcher_ss(tp_list, port, button, new_button.handle_event)
    context.log.debug(f"add_button_ss() {[tp.id for tp in tp_list]} {port=} {button=} {action=}")
    return new_button


@handle_exception
def add_level(tp, port, level, callback):
    level_handler = LevelHandler(init_handler=callback)
    tp_add_watcher_level(tp, port, level, level_handler.handle_event)
    context.log.debug(f"add_level() {tp.id} {port=} {level=} ")
    return level_handler


@handle_exception
def add_level_ss(tp_list, port, level, callback):
    level_handler = LevelHandler(init_handler=callback)
    tp_add_watcher_level_ss(tp_list, port, level, level_handler.handle_event)
    context.log.debug(f"add_level_ss() {[tp.id for tp in tp_list]} {port=} {level=}")
    return level_handler
