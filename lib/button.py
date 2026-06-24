# 마지막 수정일 : 20260514
from lib.button_handler import ButtonHandler, LevelHandler
from lib.tp import (
    tp_add_watcher,
    tp_add_watcher_level,
    tp_add_watcher_level_ss,
)


class ButtonDebugFlags:
    debug_add_button = False
    debug_add_level = False


_button_handlers = {}


class ButtonGroup(list):
    def on(self, action, callback):
        for handler in self:
            handler.on(action, callback)
        return self


def add_button_set_debug_flag(
    debug_add_button=False,
    debug_add_level=False,
):
    # 디버그 플래그 전역 설정
    ButtonDebugFlags.debug_add_button = debug_add_button
    ButtonDebugFlags.debug_add_level = debug_add_level


def button_log_debug(message):
    print(f"(DEBUG) - button : {message}")


def _button_key(tp, port, button):
    return (tp, port, button)


def get_button(tp, port, button):
    """같은 물리 버튼은 하나의 ButtonHandler를 재사용."""
    key = _button_key(tp, port, button)
    handler = _button_handlers.get(key)
    if handler:
        return handler

    handler = ButtonHandler()
    _button_handlers[key] = handler
    tp_add_watcher(tp, port, button, handler.handle_event)

    if ButtonDebugFlags.debug_add_button:
        button_log_debug(f"get_button() {tp.id} {port=} {button=}")
    return handler


def add_button(tp, port, button, action, callback):
    """ButtonHandler 이벤트 핸들러 등록"""
    handler = get_button(tp, port, button)
    handler.on(action, callback)
    if ButtonDebugFlags.debug_add_button:
        button_log_debug(f"add_button() {tp.id} {port=} {button=} {action=}")
    return handler


# 별칭 함수
def add_btn(tp, port, button, action, callback):
    """ButtonHandler 인스턴스 생성 및 이벤트 핸들러 등록"""
    return add_button(tp, port, button, action, callback)


def add_button_ss(tp_list, port, button, action, callback):
    """여러 터치패널(tp_list)에 동일한 버튼 핸들러 등록"""
    handlers = ButtonGroup(add_button(tp, port, button, action, callback) for tp in tp_list)
    if ButtonDebugFlags.debug_add_button:
        button_log_debug(f"add_button_ss() {[tp.id for tp in tp_list]} {port=} {button=} {action=}")
    return handlers


# 별칭 함수
def add_btn_ss(tp_list, port, button, action, callback):
    """여러 터치패널(tp_list)에 동시에 동일한 버튼 핸들러 등록"""
    return add_button_ss(tp_list, port, button, action, callback)


def add_level(tp, port, level, callback, debounce_ms=100):
    """LevelHandler 생성 및 레벨 변화 감지 등록 (debounce_ms로 불필요한 동작 필터링)"""
    level_handler = LevelHandler(init_handler=callback, debounce_ms=debounce_ms)
    tp_add_watcher_level(tp, port, level, level_handler.handle_event)
    if ButtonDebugFlags.debug_add_level:
        button_log_debug(f"add_level() {tp.id} {port=} {level=}")
    return level_handler


# 별칭 함수
def add_lvl(tp, port, level, callback, debounce_ms=100):
    """LevelHandler 생성 및 레벨 변화 감지 등록 (debounce_ms로 불필요한 동작 필터링)"""
    return add_level(tp, port, level, callback, debounce_ms)


def add_level_ss(tp_list, port, level, callback, debounce_ms=100):
    """여러 터치패널(tp_list)에 동시에 동일한 레벨 핸들러 등록"""
    level_handler = LevelHandler(init_handler=callback, debounce_ms=debounce_ms)
    tp_add_watcher_level_ss(tp_list, port, level, level_handler.handle_event)
    if ButtonDebugFlags.debug_add_level:
        button_log_debug(f"add_level_ss() {[tp.id for tp in tp_list]} {port=} {level=}")
    return level_handler


# 별칭 함수
def add_lvl_ss(tp_list, port, level, callback, debounce_ms=100):
    return add_level_ss(tp_list, port, level, callback, debounce_ms)
