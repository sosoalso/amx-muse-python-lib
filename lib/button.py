from mojo import context

from lib.buttonhandler import ButtonHandler, LevelHandler
from lib.lib_tp import (
    tp_add_watcher,
    tp_add_watcher_level,
    tp_add_watcher_level_ss,
    tp_add_watcher_ss,
)

# ---------------------------------------------------------------------------- #
VERSION = "2026.04.10"


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
    # 디버그 플래그 전역 설정
    DebugFlags.enable_debug_add_button = enable_debug_add_button
    DebugFlags.enable_debug_add_level = enable_debug_add_level


# ---------------------------------------------------------------------------- #
def add_button(tp, port, button, action, callback, comment=None):
    # ButtonHandler 인스턴스 생성 및 이벤트 핸들러 등록
    new_button = ButtonHandler(init_action=action, init_handler=callback)
    tp_add_watcher(tp, port, button, new_button.handle_event)
    if DebugFlags.enable_debug_add_button:
        context.log.debug(f"add_button() -- {tp.id} {port=} {button=} {action=} {': ' + comment if comment else ''}")
    return new_button


# 별칭 함수
def add_btn(tp, port, button, action, callback, comment=None):
    return add_button(tp, port, button, action, callback, comment)


def add_button_ss(tp_list, port, button, action, callback, comment=None):
    # 여러 터치패널(tp_list)에 동시에 동일한 버튼 핸들러 등록
    new_button = ButtonHandler(init_action=action, init_handler=callback)
    tp_add_watcher_ss(tp_list, port, button, new_button.handle_event)
    if DebugFlags.enable_debug_add_button:
        context.log.debug(f"add_button_ss() -- {[tp.id for tp in tp_list]} {port=} {button=} {action=} {': ' + comment if comment else ''}")
    return new_button


# 별칭 함수
def add_btn_ss(tp_list, port, button, action, callback, comment=None):
    return add_button_ss(tp_list, port, button, action, callback, comment)


def add_level(tp, port, level, callback, debounce_ms, comment=None):
    # LevelHandler 생성 및 레벨 변화 감지 등록 (debounce_ms로 노이즈 필터링)
    level_handler = LevelHandler(init_handler=callback, debounce_ms=debounce_ms)
    tp_add_watcher_level(tp, port, level, level_handler.handle_event)
    if DebugFlags.enable_debug_add_level:
        context.log.debug(f"add_level() -- {tp.id} {port=} {level=} {': ' + comment if comment else ''}")
    return level_handler


# 별칭 함수
def add_lvl(tp, port, level, callback, debounce_ms, comment=None):
    return add_level(tp, port, level, callback, debounce_ms, comment)


def add_level_ss(tp_list, port, level, callback, debounce_ms, comment=None):
    # 여러 터치패널(tp_list)에 동시에 동일한 레벨 핸들러 등록
    level_handler = LevelHandler(init_handler=callback, debounce_ms=debounce_ms)
    tp_add_watcher_level_ss(tp_list, port, level, level_handler.handle_event)
    if DebugFlags.enable_debug_add_level:
        context.log.debug(f"add_level_ss() -- {[tp.id for tp in tp_list]} {port=} {level=} {': ' + comment if comment else ''}")
    return level_handler


# 별칭 함수
def add_lvl_ss(tp_list, port, level, callback, debounce_ms, comment=None):
    return add_level_ss(tp_list, port, level, callback, debounce_ms, comment)
