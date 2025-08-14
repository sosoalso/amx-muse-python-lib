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
VERSION = "2025.07.15"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class DebugFlags:
    enable_debug_add_button = False
    enable_debug_add_level = False


def add_button_set_debug_flag(
    enable_debug_add_button=False,
    enable_debug_add_level=False,
):
    DebugFlags.enable_debug_add_button = enable_debug_add_button
    DebugFlags.enable_debug_add_level = enable_debug_add_level


# ---------------------------------------------------------------------------- #
@handle_exception
def add_button(tp, port, button, action, callback, comment=None):
    new_button = ButtonHandler(init_action=action, init_handler=callback)
    tp_add_watcher(tp, port, button, new_button.handle_event)
    if DebugFlags.enable_debug_add_button:
        context.log.debug(f"add_button() {tp.id} {port=} {button=} {action=} {': ' + comment if comment else ''}")
    return new_button


def add_btn(tp, port, button, action, callback, comment=None):
    return add_button(tp, port, button, action, callback, comment)


@handle_exception
def add_button_ss(tp_list, port, button, action, callback, comment=None):
    new_button = ButtonHandler(init_action=action, init_handler=callback)
    tp_add_watcher_ss(tp_list, port, button, new_button.handle_event)
    if DebugFlags.enable_debug_add_button:
        context.log.debug(
            f"add_button_ss() {[tp.id for tp in tp_list]} {port=} {button=} {action=} {': ' + comment if comment else ''}"
        )
    return new_button


def add_btn_ss(tp_list, port, button, action, callback, comment=None):
    return add_button_ss(tp_list, port, button, action, callback, comment)


@handle_exception
def add_level(tp, port, level, callback, comment=None):
    level_handler = LevelHandler(init_handler=callback)
    tp_add_watcher_level(tp, port, level, level_handler.handle_event)
    if DebugFlags.enable_debug_add_level:
        context.log.debug(f"add_level() {tp.id} {port=} {level=} {': ' + comment if comment else ''}")
    return level_handler


def add_lvl(tp, port, level, callback, comment=None):
    return add_level(tp, port, level, callback, comment)


@handle_exception
def add_level_ss(tp_list, port, level, callback, comment=None):
    level_handler = LevelHandler(init_handler=callback)
    tp_add_watcher_level_ss(tp_list, port, level, level_handler.handle_event)
    if DebugFlags.enable_debug_add_level:
        context.log.debug(
            f"add_level_ss() {[tp.id for tp in tp_list]} {port=} {level=} {': ' + comment if comment else ''}"
        )
    return level_handler


def add_lvl_ss(tp_list, port, level, callback, comment=None):
    return add_level_ss(tp_list, port, level, callback, comment)
