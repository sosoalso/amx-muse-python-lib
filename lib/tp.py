# 마지막 수정일 : 20260713
"""AMX 터치패널(TP) 제어 헬퍼 함수 모음.

mojo 가 노출하는 TP 디바이스 객체를 감싸서
- 버튼/레벨 워처(핸들러) 등록: tp_add_watcher*, tp_add_notification*
- 피드백 전송: tp_set_button*(채널), tp_send_level*(레벨), tp_send_command*(^TXT, ^PGE 등)
을 함수 단위로 제공한다. 접미사 _ss 붙은 함수는 여러 TP 리스트에 일괄 적용용이고,
btn/lvl/txt 축약형은 동일 동작의 별칭 함수다.

참고: 워처 중복 등록을 여기서 막지 않는 것은 의도된 설계다.
중복 방지는 상위 계층(button.py 의 핸들러 캐시)이 책임진다.
모든 공개 함수는 tp_handle_exception 데코레이터로 감싸져
예외 발생 시 에러 로그만 남기고 None 을 반환한다 (시스템 전체 중단 방지).
"""

import functools

from lib.utility import CommonLogger


def _make_logger(name: str) -> CommonLogger:
    # 섹션별 CommonLogger 인스턴스 생성 (debug 플래그는 인스턴스별로 독립)
    logger = CommonLogger()
    logger.name = name
    logger.debug = False
    return logger


# 섹션별 로거 - 각자 독립된 debug 플래그로 로깅 제어
_LOG = _make_logger("tp")  # 공통(에러/일반) 로거
_LOG_ADD_WATCHER = _make_logger("tp.add_watcher")
_LOG_ADD_WATCHER_LEVEL = _make_logger("tp.add_watcher_level")
_LOG_ADD_NOTIFICATION = _make_logger("tp.add_notification")
_LOG_ADD_NOTIFICATION_LEVEL = _make_logger("tp.add_notification_level")
_LOG_SET_BUTTON = _make_logger("tp.set_button")
_LOG_SEND_LEVEL = _make_logger("tp.send_level")
_LOG_SEND_COMMAND = _make_logger("tp.send_command")


def tp_set_debug_flag(
    debug_tp_add_watcher,
    debug_tp_add_watcher_level,
    debug_tp_add_notification,
    debug_tp_add_notification_level,
    debug_tp_set_button,
    debug_tp_send_level,
    debug_tp_send_command,
):
    # 섹션별 로거의 debug 플래그 설정
    _LOG_ADD_WATCHER.debug = debug_tp_add_watcher
    _LOG_ADD_WATCHER_LEVEL.debug = debug_tp_add_watcher_level
    _LOG_ADD_NOTIFICATION.debug = debug_tp_add_notification
    _LOG_ADD_NOTIFICATION_LEVEL.debug = debug_tp_add_notification_level
    _LOG_SET_BUTTON.debug = debug_tp_set_button
    _LOG_SEND_LEVEL.debug = debug_tp_send_level
    _LOG_SEND_COMMAND.debug = debug_tp_send_command


def tp_handle_exception(func):
    # 함수 실행 중 예외 발생 시 에러 로그를 출력하고 None 반환하는 데코레이터
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            _LOG.log_error(f"{func.__name__} {e=}")
            return None

    return wrapper


@tp_handle_exception
def tp_add_notification(tp, port, button):
    # 버튼 상태 변화를 감지하는 워처 등록 (중복 등록 방지)

    def _notify(evt):
        _LOG_ADD_NOTIFICATION.log_debug(f"BUTTON {'    PUSH' if evt.value else ' RELEASE'} > {evt.path}")

    # _notify 는 매번 새 클로저라 in 비교는 무의미 - 함수 이름으로 중복 판정
    watchers = tp.port[port].button[button].pythonWatchers or []
    if not any(getattr(watcher, "__name__", "") == _notify.__name__ for watcher in watchers):
        tp.port[port].button[button].watch(_notify)


@tp_handle_exception
def tp_add_notification_ss(tp_list, port, button):
    # 여러 터치패널 장비에 동일한 버튼 알림 등록
    if not isinstance(tp_list, (list, tuple)):
        _LOG_ADD_NOTIFICATION.log_error("tp_add_notification_ss() -- tp_list must be a tuple or list of devices")
        return
    for tp in tp_list:
        tp_add_notification(tp, port, button)


@tp_handle_exception
def tp_add_notification_level(tp, port, level):
    # 레벨(슬라이더) 값 변화를 감지하는 워처 등록 (중복 등록 방지)

    def _notify(evt):
        _LOG_ADD_NOTIFICATION_LEVEL.log_debug(f"{evt.path=} {evt.value=}")

    # _notify 는 매번 새 클로저라 in 비교는 무의미 - 함수 이름으로 중복 판정
    watchers = tp.port[port].level[level].pythonWatchers or []
    if not any(getattr(watcher, "__name__", "") == _notify.__name__ for watcher in watchers):
        tp.port[port].level[level].watch(_notify)


@tp_handle_exception
def tp_add_notification_level_ss(tp_list, port, level):
    # 여러 터치패널 장비에 동일한 레벨 알림 등록
    if not isinstance(tp_list, (list, tuple)):
        _LOG_ADD_NOTIFICATION_LEVEL.log_error("tp_add_notification_level_ss() -- tp_list must be a tuple or list of devices")
        return
    for tp in tp_list:
        tp_add_notification_level(tp, port, level)


@tp_handle_exception
def tp_get_device_state(tp):
    # 터치패널 온라인 상태 확인 (isOnline이 메서드인 경우와 프로퍼티인 경우 모두 처리)
    result = tp.isOnline
    return result() if callable(result) else bool(result)


@tp_handle_exception
def tp_add_watcher(tp, port, button, handler):
    # 버튼에 사용자 정의 핸들러 함수 등록 (중복이어도 항상 등록함 - 의도된 동작)
    if tp.port[port].button[button].pythonWatchers and handler in tp.port[port].button[button].pythonWatchers:
        _LOG_ADD_WATCHER.log_debug(f"tp_add_watcher() : duplicate handler, registering anyway {tp.id=} {port=} {button=}")
    tp.port[port].button[button].watch(handler)
    _LOG_ADD_WATCHER.log_debug(f"tp_add_watcher() : {tp.id} {port=} {button=}")
    tp_add_notification(tp, port, button)


@tp_handle_exception
def tp_add_watcher_ss(tp_list: list | tuple, port, button, handler):
    # 여러 터치패널 장비에 동일한 버튼 핸들러 등록
    if not isinstance(tp_list, (list, tuple)):
        _LOG_ADD_WATCHER.log_error("tp_add_watcher_ss() -- tp_list must be a tuple or list of devices")
        return
    for tp in tp_list:
        tp_add_watcher(tp, port, button, handler)


@tp_handle_exception
def tp_clear_watcher(tp, port, button):
    # 버튼의 모든 워처 제거
    if isinstance(tp.port[port].button[button].pythonWatchers, list):
        tp.port[port].button[button].pythonWatchers.clear()


@tp_handle_exception
def tp_add_watcher_level(tp, port, level, handler):
    # 레벨에 사용자 정의 핸들러 함수 등록 (중복이어도 항상 등록함 - 의도된 동작)
    if tp.port[port].level[level].pythonWatchers and handler in tp.port[port].level[level].pythonWatchers:
        _LOG_ADD_WATCHER_LEVEL.log_debug(f"tp_add_watcher_level() : duplicate handler, registering anyway {tp.id=} {port=} {level=}")
    tp.port[port].level[level].watch(handler)
    _LOG_ADD_WATCHER_LEVEL.log_debug(f"tp_add_watcher_level() : {tp.id} {port=} {level=}")
    tp_add_notification_level(tp, port, level)


@tp_handle_exception
def tp_add_watcher_level_ss(tp_list: list | tuple, port, level, handler):
    # 여러 터치패널 장비에 동일한 레벨 핸들러 등록
    if not isinstance(tp_list, (list, tuple)):
        _LOG_ADD_WATCHER_LEVEL.log_error("tp_add_watcher_level_ss() -- tp_list must be a tuple or list of devices")
        return
    for tp in tp_list:
        tp_add_watcher_level(tp, port, level, handler)


@tp_handle_exception
def tp_clear_watcher_level(tp, port, level):
    # 레벨의 모든 워처 제거
    if isinstance(tp.port[port].level[level].pythonWatchers, list):
        tp.port[port].level[level].pythonWatchers.clear()


@tp_handle_exception
def tp_show_watcher(tp, port, button):
    # 등록된 버튼 워처의 개수를 디버그 로깅
    if tp.port[port].button[button].pythonWatchers:
        if isinstance(tp.port[port].button[button].pythonWatchers, list):
            _LOG_ADD_WATCHER.log_debug(f"{tp.id} {port=} {button=} num_watcher={len(tp.port[port].button[button].pythonWatchers)}")


@tp_handle_exception
def tp_get_button_pushed(tp, port, button):
    # 버튼의 현재 상태 값(누르지 않음=False, 누름=True) 반환.
    # 없는 버튼(zombie)이면 조용히 False 반환.
    if tp.port[port].button[button].kind == "unknown":
        return False
    return tp.port[port].button[button].value


# 별칭 함수
def tp_get_btn_pushed(tp, port, button):
    return tp_get_button_pushed(tp, port, button)


@tp_handle_exception
def tp_get_button_state(tp, port, button):
    # 채널 상태 값 반환.
    # 없는 채널(zombie)이면 조용히 False 반환.
    if tp.port[port].channel[button].kind == "unknown":
        return False
    return tp.port[port].channel[button].value


# 별칭 함수
def tp_get_btn_state(tp, port, button):
    return tp_get_button_state(tp, port, button)


@tp_handle_exception
def tp_set_button(tp, port, button, value):
    # 버튼 피드백(채널 값) 설정.
    # 오프라인이면 스킵한다 (오프라인 상태에서 값을 쓰면 무의미하고 로그만 쌓임).
    # 또한 TP 디자인에 없는 채널에 value 를 쓰면 zombie 가 생성되며 Java 가
    # ThingAccessException 을 콘솔에 찍으므로, 존재하는 채널일 때만 쓴다.
    if not tp_get_device_state(tp):
        _LOG_SET_BUTTON.log_debug(f"tp_set_button() : device offline, skipped {tp.id} {port=} {button=}")
        return
    if not _tp_channel_exists(tp, port, button):
        _LOG_SET_BUTTON.log_debug(f"tp_set_button() : channel not found, skipped {tp.id} {port=} {button=}")
        return
    tp.port[port].channel[button].value = value
    _LOG_SET_BUTTON.log_debug(f"BUTTON FEEDBACK < {tp.id} {port=} {button=} {value=}")


def _tp_channel_exists(tp, port, button):
    # channel[button] 이 실제 TP 디자인에 존재하는지 확인.
    # mojo 래퍼에서 존재하지 않는 인덱스는 zombie 를 만든다 (kind == "unknown").
    # 실제 파라미터/컴포넌트는 kind 가 "param"/"object" 등이므로 "unknown" 이 아니면 존재로 본다.
    # 확인 자체가 실패하면 True 로 간주하여 기존 동작(값 쓰기)을 유지한다.
    try:
        return tp.port[port].channel[button].kind != "unknown"
    except Exception:
        return True


# 별칭 함수
def tp_set_btn(tp, port, button, value):
    tp_set_button(tp, port, button, value)


@tp_handle_exception
def tp_set_button_ss(tp_list: list | tuple, port, button, value):
    # 여러 터치패널 장비에 동일한 버튼 피드백 설정
    if not isinstance(tp_list, (list, tuple)):
        _LOG_SET_BUTTON.log_error("tp_set_button_ss() -- tp_list must be a tuple or list of devices")
        return
    for tp in tp_list:
        tp_set_button(tp, port, button, value)


# 별칭 함수
def tp_set_btn_ss(tp_list: list | tuple, port, button, value):
    tp_set_button_ss(tp_list, port, button, value)


@tp_handle_exception
def tp_set_button_state(tp, port, button, value):
    # 버튼 상태 설정 (tp_set_button 이 채널 존재 여부를 확인함)
    tp_set_button(tp, port, button, value)


# 별칭 함수
def tp_set_btn_state(tp, port, button, value):
    tp_set_button_state(tp, port, button, value)


@tp_handle_exception
def tp_set_button_state_ss(tp: list | tuple, port, button, value):
    # 여러 터치패널의 버튼 상태 설정
    tp_set_button_ss(tp, port, button, value)


# 별칭 함수
def tp_set_btn_state_ss(tp: list | tuple, port, button, value):
    tp_set_button_state_ss(tp, port, button, value)


@tp_handle_exception
def tp_set_button_in_range(tp, port, index_btn_start, index_btn_range, index_condition):
    # 버튼 범위 설정: 조건에 해당하는 버튼만 True, 나머지는 False
    for index in range(index_btn_start, index_btn_start + index_btn_range):
        tp_set_button(tp, port, index, index_condition == (index - index_btn_start + 1))


# 별칭 함수
def tp_set_btn_in_range(tp, port, index_btn_start, index_btn_range, index_condition):
    tp_set_button_in_range(tp, port, index_btn_start, index_btn_range, index_condition)


@tp_handle_exception
def tp_set_button_in_array(tp, port, btn_list: list | tuple, index_condition):
    # 버튼 배열 설정: 조건에 해당하는 버튼만 True, 나머지는 False
    if not isinstance(btn_list, (list, tuple)):
        _LOG_SET_BUTTON.log_error("tp_set_button_in_array() -- btn_list must be a list or tuple of button indices")
        return
    for idx, btn in enumerate(btn_list):
        tp_set_button(tp, port, btn, index_condition == (idx + 1))


# 별칭 함수
def tp_set_btn_in_array(tp, port, btn_list: list | tuple, index_condition):
    tp_set_button_in_array(tp, port, btn_list, index_condition)


@tp_handle_exception
def tp_set_button_in_array_ss(tp_list: list | tuple, port, btn_list: list | tuple, index_condition):
    # 여러 터치패널의 버튼 배열 설정
    if not isinstance(tp_list, (list, tuple)):
        _LOG_SET_BUTTON.log_error("tp_set_button_in_array_ss() -- tp_list must be a tuple or list of devices")
        return
    for tp in tp_list:
        tp_set_button_in_array(tp, port, btn_list, index_condition)


# 별칭 함수
def tp_set_btn_in_array_ss(tp_list: list | tuple, port, btn_list: list | tuple, index_condition):
    tp_set_button_in_array_ss(tp_list, port, btn_list, index_condition)


@tp_handle_exception
def tp_set_button_in_list(tp, port, btn_list: list | tuple, index_condition):
    # 버튼 리스트 설정 (배열 설정과 동일)
    tp_set_button_in_array(tp, port, btn_list, index_condition)


# 별칭 함수
def tp_set_btn_in_list(tp, port, btn_list: list | tuple, index_condition):
    tp_set_button_in_array(tp, port, btn_list, index_condition)


@tp_handle_exception
def tp_set_button_in_list_ss(tp_list: list | tuple, port, btn_list: list | tuple, index_condition):
    # 여러 터치패널의 버튼 리스트 설정
    tp_set_button_in_array_ss(tp_list, port, btn_list, index_condition)


# 별칭 함수
def tp_set_btn_in_list_ss(tp_list: list | tuple, port, btn_list: list | tuple, index_condition):
    tp_set_button_in_array_ss(tp_list, port, btn_list, index_condition)


@tp_handle_exception
def tp_set_button_in_range_ss(tp_list: list | tuple, port, index_btn_start, index_btn_range, index_condition):
    # 여러 터치패널의 버튼 범위 설정
    if not isinstance(tp_list, (list, tuple)):
        _LOG_SET_BUTTON.log_error("tp_set_button_in_range_ss() -- tp_list must be a tuple or list of devices")
        return
    for tp in tp_list:
        tp_set_button_in_range(tp, port, index_btn_start, index_btn_range, index_condition)


# 별칭 함수
def tp_set_btn_in_range_ss(tp_list: list | tuple, port, index_btn_start, index_btn_range, index_condition):
    tp_set_button_in_range_ss(tp_list, port, index_btn_start, index_btn_range, index_condition)


@tp_handle_exception
def tp_get_level(tp, port, level):
    # 레벨(슬라이더) 값을 정수로 반환.
    # 없는 레벨(zombie)이면 조용히 0 반환.
    if tp.port[port].level[level].kind == "unknown":
        return 0
    return int(tp.port[port].level[level].value)


# 별칭 함수
def tp_get_lvl(tp, port, level):
    return tp_get_level(tp, port, level)


@tp_handle_exception
def tp_send_level(tp, port, level, value):
    # 레벨 값 전송/설정.
    if not tp_get_device_state(tp):
        _LOG_SEND_LEVEL.log_debug(f"tp_send_level() : device offline, skipped {tp.id} {port=} {level=} {value=}")
        return

    if not _tp_level_exists(tp, port, level):
        _LOG_SEND_LEVEL.log_debug(f"tp_send_level() : level not found, skipped {tp.id} {port=} {level=}")
        return
    tp.port[port].level[level].value = value
    _LOG_SEND_LEVEL.log_debug(f"LEVEL VALUE CHANGE - {tp.id} {port=} {level=} {value=}")


def _tp_level_exists(tp, port, level):
    # level[level] 이 실제 TP 디자인에 존재하는지 확인 (_tp_channel_exists 와 동일한 방식).
    # 존재하지 않는 인덱스는 zombie(kind == "unknown") 가 되므로 그때만 없다고 판단하고,
    # 확인 자체가 실패하면 True 로 간주해 기존 동작(값 쓰기)을 유지한다.
    try:
        return tp.port[port].level[level].kind != "unknown"
    except Exception:
        return True


# 별칭 함수
def tp_send_lvl(tp, port, level, value):
    tp_send_level(tp, port, level, value)


@tp_handle_exception
def tp_set_level(tp, port, level, value):
    # 레벨 설정 (tp_send_level 호출)
    tp_send_level(tp, port, level, value)


# 별칭 함수
def tp_set_lvl(tp, port, level, value):
    tp_send_level(tp, port, level, value)


@tp_handle_exception
def tp_send_level_ss(tp_list: list | tuple, port, level, value):
    # 여러 터치패널에 동일한 레벨 값 전송
    if not isinstance(tp_list, (list, tuple)):
        _LOG_SEND_LEVEL.log_error("tp_send_level_ss() -- tp_list must be a tuple or list of devices")
        return
    for tp in tp_list:
        tp_send_level(tp, port, level, value)


# 별칭 함수
def tp_send_lvl_ss(tp_list: list | tuple, port, level, value):
    tp_send_level_ss(tp_list, port, level, value)


@tp_handle_exception
def tp_set_level_ss(tp: list | tuple, port, level, value):
    # 여러 터치패널의 레벨 설정
    tp_send_level_ss(tp, port, level, value)


# 별칭 함수
def tp_set_lvl_ss(tp: list | tuple, port, level, value):
    tp_send_lvl_ss(tp, port, level, value)


@tp_handle_exception
def convert_text_to_unicode(text):
    # 텍스트를 유니코드 포맷 문자열로 변환 (각 문자를 4자리 16진수로 표현)
    return "".join(format(ord(char), "04X") for char in text)


# 별칭 함수
def convert_txt_to_unicode(text):
    return convert_text_to_unicode(text)


@tp_handle_exception
def tp_send_command(tp, port, command):
    # TP 에 문자열 명령어(^TXT, ^PGE, ^PPN 등) 전송. 오프라인이면 스킵.
    if not tp_get_device_state(tp):
        _LOG_SEND_COMMAND.log_debug(f"tp_send_command() : device offline, skipped {tp.id} {port=} {command=}")
        return
    tp.port[port].send_command(command)
    _LOG_SEND_COMMAND.log_debug(f"tp_send_command() : {tp.id} {port=} {command=}")


# 별칭 함수
def tp_send_cmd(tp, port, command):
    tp_send_command(tp, port, command)


@tp_handle_exception
def tp_send_command_ss(tp_list: list | tuple, port, command):
    # 여러 터치패널에 동일한 명령어 전송
    if not isinstance(tp_list, (list, tuple)):
        _LOG_SEND_COMMAND.log_error(f"tp_send_command_ss() {command=} -- tp_list must be a tuple or list of devices")
        return
    for tp in tp_list:
        tp_send_command(tp, port, command)


# 별칭 함수
def tp_send_cmd_ss(tp_list: list | tuple, port, command):
    tp_send_command_ss(tp_list, port, command)


@tp_handle_exception
def tp_set_button_text_unicode(tp, port, index_addr, text):
    # 버튼 텍스트를 유니코드로 설정하는 명령어 전송
    tp_send_command(tp, port, f"^UNI-{index_addr},0,{convert_text_to_unicode(text)}")


# 별칭 함수
def tp_set_btn_txt_unicode(tp, port, index_addr, text):
    tp_set_button_text_unicode(tp, port, index_addr, text)


@tp_handle_exception
def tp_set_button_text_unicode_ss(tp_list: list | tuple, port, index_addr, text):
    # 여러 터치패널의 버튼 텍스트를 유니코드로 설정
    tp_send_command_ss(tp_list, port, f"^UNI-{index_addr},0,{convert_text_to_unicode(text)}")


# 별칭 함수
def tp_set_btn_txt_unicode_ss(tp_list: list | tuple, port, index_addr, text):
    tp_set_button_text_unicode_ss(tp_list, port, index_addr, text)


@tp_handle_exception
def tp_set_button_text(tp, port, index_addr, text):
    # 버튼 텍스트 설정
    tp_send_command(tp, port, f"^TXT-{index_addr},0,{text}")


# 별칭 함수
def tp_set_btn_txt(tp, port, index_addr, text):
    tp_set_button_text(tp, port, index_addr, text)


@tp_handle_exception
def tp_set_button_text_ss(tp_list: list | tuple, port, index_addr, text):
    # 여러 터치패널의 버튼 텍스트 설정
    tp_send_command_ss(tp_list, port, f"^TXT-{index_addr},0,{text}")


# 별칭 함수
def tp_set_btn_txt_ss(tp_list: list | tuple, port, index_addr, text):
    tp_set_button_text_ss(tp_list, port, index_addr, text)


@tp_handle_exception
def tp_set_button_show_hide(tp, port, index_addr, value):
    # 버튼 표시/숨김 및 활성화/비활성화 설정
    state_str = 1 if value else 0
    tp.port[port].send_command(f"^SHO-{index_addr},{state_str}")
    tp.port[port].send_command(f"^ENA-{index_addr},{state_str}")


# 별칭 함수
def tp_set_btn_show_hide(tp, port, index_addr, value):
    tp_set_button_show_hide(tp, port, index_addr, value)


@tp_handle_exception
def tp_set_page(tp, page_name):
    # 터치패널 페이지 변경
    tp_send_command(tp, 1, f"^PGE-{page_name}")


@tp_handle_exception
def tp_show_popup(tp, popup_name):
    # 팝업 표시
    tp_send_command(tp, 1, f"^PPN-{popup_name}")


@tp_handle_exception
def tp_hide_popup(tp, popup_name):
    # 팝업 숨김
    tp_send_command(tp, 1, f"^PPF-{popup_name}")


@tp_handle_exception
def tp_hide_all_popup(tp):
    # 모든 팝업 숨김
    tp_send_command(tp, 1, "^PPX")


@tp_handle_exception
def tp_set_page_ss(tp: list | tuple, page_name):
    # 여러 터치패널의 페이지 변경
    tp_send_command_ss(tp, 1, f"^PGE-{page_name}")


@tp_handle_exception
def tp_show_popup_ss(tp: list | tuple, popup_name):
    # 여러 터치패널에 팝업 표시
    tp_send_command_ss(tp, 1, f"^PPN-{popup_name}")


@tp_handle_exception
def tp_hide_popup_ss(tp: list | tuple, popup_name):
    # 여러 터치패널의 팝업 숨김
    tp_send_command_ss(tp, 1, f"^PPF-{popup_name}")


@tp_handle_exception
def tp_hide_all_popup_ss(tp: list | tuple):
    # 여러 터치패널의 모든 팝업 숨김
    tp_send_command_ss(tp, 1, "^PPX")
