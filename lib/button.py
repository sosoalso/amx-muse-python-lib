# 마지막 수정일 : 20260713
"""터치패널 버튼/레벨 이벤트 등록의 진입점(파사드) 모듈.

add_button()/add_level() 로 (tp, port, 번호)에 콜백을 연결한다.
같은 물리 버튼/레벨은 캐시(_button_handlers/_level_handlers)를 통해
하나의 ButtonHandler/LevelHandler 만 만들어 재사용하며, 이 캐시가
tp 워처 중복 등록을 걸러주는 계층 역할을 한다 (의도된 설계).
_ss 접미사 함수들은 여러 터치패널에 같은 콜백을 한 번에 등록한다.
"""
from lib.button_handler import ButtonHandler, LevelHandler
from lib.tp import (
    tp_add_watcher,
    tp_add_watcher_level,
    tp_add_watcher_level_ss,
)
from lib.utility import CommonLogger

# ---------------------------------------------------------------------------- #
button_logger = CommonLogger()
# ---------------------------------------------------------------------------- #


def log_debug(message):
    button_logger.log_debug(message)


# ---------------------------------------------------------------------------- #
# 핸들러 캐시: (tp, port, 번호) → 핸들러. 같은 물리 버튼/레벨에 대한 중복 생성을 막는다.
_button_handlers = {}
_level_handlers = {}
# ---------------------------------------------------------------------------- #


class ButtonGroup(list):
    """여러 ButtonHandler 를 묶어 한 번의 on() 호출로 일괄 등록하게 해주는 리스트."""

    def on(self, action, callback):
        """그룹 내 모든 핸들러에 같은 콜백 등록. 체이닝을 위해 self 반환."""
        for handler in self:
            handler.on(action, callback)
        return self


# ---------------------------------------------------------------------------- #
def _button_key(tp, port, button):
    return (tp, port, button)


# ---------------------------------------------------------------------------- #


def get_button(tp, port, button):
    """같은 물리 버튼은 하나의 ButtonHandler를 재사용."""
    key = _button_key(tp, port, button)
    handler = _button_handlers.get(key)
    if handler:
        return handler

    handler = ButtonHandler()
    _button_handlers[key] = handler
    tp_add_watcher(tp, port, button, handler.handle_event)

    log_debug(f"get_button() {tp.id} {port=} {button=}")
    return handler


def add_button(tp, port, button, action, callback):
    """ButtonHandler 이벤트 핸들러 등록"""
    handler = get_button(tp, port, button)
    handler.on(action, callback)
    log_debug(f"add_button() {tp.id} {port=} {button=} {action=}")
    return handler


# 별칭 함수
def add_btn(tp, port, button, action, callback):
    """ButtonHandler 인스턴스 생성 및 이벤트 핸들러 등록"""
    return add_button(tp, port, button, action, callback)


def add_button_ss(tp_list, port, button, action, callback):
    """여러 터치패널(tp_list)에 동일한 버튼 핸들러 등록"""
    handlers = ButtonGroup(add_button(tp, port, button, action, callback) for tp in tp_list)
    log_debug(f"add_button_ss() {[tp.id for tp in tp_list]} {port=} {button=} {action=}")
    return handlers


# 별칭 함수
def add_btn_ss(tp_list, port, button, action, callback):
    """여러 터치패널(tp_list)에 동시에 동일한 버튼 핸들러 등록"""
    return add_button_ss(tp_list, port, button, action, callback)


def get_level(tp, port, level, debounce_ms=100):
    """같은 물리 레벨은 하나의 LevelHandler를 재사용. debounce_ms는 최초 생성 시에만 적용됨."""
    key = (tp, port, level)
    handler = _level_handlers.get(key)
    if handler:
        return handler

    handler = LevelHandler(debounce_ms=debounce_ms)
    _level_handlers[key] = handler
    tp_add_watcher_level(tp, port, level, handler.handle_event)

    log_debug(f"get_level() {tp.id} {port=} {level=}")
    return handler


def add_level(tp, port, level, callback, debounce_ms=100):
    """LevelHandler 이벤트 핸들러 등록 (debounce_ms로 불필요한 동작 필터링)"""
    handler = get_level(tp, port, level, debounce_ms)
    handler.on("level", callback)
    log_debug(f"add_level() {tp.id} {port=} {level=}")
    return handler


# 별칭 함수
def add_lvl(tp, port, level, callback, debounce_ms=100):
    """LevelHandler 이벤트 핸들러 등록 (debounce_ms로 불필요한 동작 필터링)"""
    return add_level(tp, port, level, callback, debounce_ms)


def add_level_ss(tp_list, port, level, callback, debounce_ms=100):
    """여러 터치패널(tp_list)에 동시에 동일한 레벨 핸들러 등록. debounce_ms는 최초 생성 시에만 적용됨."""
    # 개별 tp 키와 달리 tp 목록 전체를 하나의 키로 묶어 캐시한다
    key = (tuple(tp_list), port, level)
    handler = _level_handlers.get(key)
    if handler is None:
        handler = LevelHandler(debounce_ms=debounce_ms)
        _level_handlers[key] = handler
        tp_add_watcher_level_ss(tp_list, port, level, handler.handle_event)
    handler.on("level", callback)
    log_debug(f"add_level_ss() {[tp.id for tp in tp_list]} {port=} {level=}")
    return handler


# 별칭 함수
def add_lvl_ss(tp_list, port, level, callback, debounce_ms=100):
    return add_level_ss(tp_list, port, level, callback, debounce_ms)
