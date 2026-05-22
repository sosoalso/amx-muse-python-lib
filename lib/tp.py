# 마지막 수정일 : 20260514
class DebugFlags:
    debug_tp_add_watcher = False
    debug_tp_add_watcher_level = False
    debug_tp_add_notification = False
    debug_tp_add_notification_level = False
    debug_tp_set_button = False
    debug_tp_send_level = False
    debug_tp_send_command = False


def tp_set_debug_flag(
    debug_tp_add_watcher,
    debug_tp_add_watcher_level,
    debug_tp_add_notification,
    debug_tp_add_notification_level,
    debug_tp_set_button,
    debug_tp_send_level,
    debug_tp_send_command,
):
    # 디버그 플래그 클래스 변수들을 인자 값으로 설정
    DebugFlags.debug_tp_add_watcher = debug_tp_add_watcher
    DebugFlags.debug_tp_add_watcher_level = debug_tp_add_watcher_level
    DebugFlags.debug_tp_add_notification = debug_tp_add_notification
    DebugFlags.debug_tp_add_notification_level = debug_tp_add_notification_level
    DebugFlags.debug_tp_set_button = debug_tp_set_button
    DebugFlags.debug_tp_send_level = debug_tp_send_level
    DebugFlags.debug_tp_send_command = debug_tp_send_command


def tp_handle_exception(func):
    # 함수 실행 중 예외 발생 시 에러 로그를 출력하고 None 반환하는 데코레이터
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"mojo_tp (ERROR) -- {func.__name__} {e=}")
            return None

    return wrapper


def tp_log_debug(message):
    print(f"(DEBUG) - mojo_tp : {message}")


def tp_log_error(message):
    print(f"(ERROR) - mojo_tp : {message}")


def _notify(evt):
    # 버튼 상태 변화 이벤트를 디버그 로깅
    if DebugFlags.debug_tp_add_notification:
        # 이벤트 경로를 '/'로 분할하여 포트와 버튼 번호 추출
        _, port, _, button = (int(x) if x.isdigit() else x for x in evt.path.split("/"))
        tp_log_debug(f"BUTTON {'    PUSH' if evt.value else ' RELEASE'} > {evt.device} {port=} {button=}")


@tp_handle_exception
def tp_add_notification(tp, port, button):
    # 버튼 상태 변화를 감지하는 워처 등록 (중복 등록 방지)
    if not _notify in tp.port[port].button[button].pythonWatchers or not any(
        watcher.__name__ == _notify.__name__ for watcher in tp.port[port].button[button].pythonWatchers
    ):
        tp.port[port].button[button].watch(_notify)
    # else:
    #     tp_log_debug(f"tp_add_notification() 중복 알림 등록됨. 기존 알림을 유지함 {tp.id=} {port=} {button=}")


@tp_handle_exception
def tp_add_notification_ss(tp_list, port, button):
    # 여러 터치패널 장비에 동일한 버튼 알림 등록
    if not isinstance(tp_list, (list, tuple)):
        tp_log_error("tp_add_notification_ss() -- tp_list must be a tuple or list of devices")
        raise TypeError
    for tp in tp_list:
        tp_add_notification(tp, port, button)


@tp_handle_exception
def tp_add_notification_level(tp, port, level):
    # 레벨(슬라이더) 값 변화를 감지하는 내부 워처 함수
    def _notify(evt):
        if DebugFlags.debug_tp_add_notification_level:
            # 이벤트 경로에서 포트와 버튼 번호 추출
            _, port, _, button = (int(x) if x.isdigit() else x for x in evt.path.split("/"))
            tp_log_debug(f"LEVEL VALUE={evt.value} : {evt.device} {port=} {button=}")

    # 레벨 값 변화 워처 등록 (중복 등록 방지)
    if not _notify in tp.port[port].level[level].pythonWatchers or not any(
        watcher.__name__ == _notify.__name__ for watcher in tp.port[port].level[level].pythonWatchers
    ):
        tp.port[port].level[level].watch(_notify)


@tp_handle_exception
def tp_add_notification_level_ss(tp_list, port, level):
    # 여러 터치패널 장비에 동일한 레벨 알림 등록
    if not isinstance(tp_list, (list, tuple)):
        tp_log_error("tp_add_notification_level_ss() -- tp_list must be a tuple or list of devices")
        raise TypeError
    for tp in tp_list:
        tp_add_notification_level(tp, port, level)


@tp_handle_exception
def tp_get_device_state(tp):
    # 터치패널 온라인 상태 확인 (isOnline이 메서드인 경우와 프로퍼티인 경우 모두 처리)
    return tp.isOnline() if tp.isOnline else False


@tp_handle_exception
def tp_add_watcher(tp, port, button, handler):
    # 버튼에 사용자 정의 핸들러 함수 등록 (중복 등록 방지 로직이 있으나 항상 등록함)
    if DebugFlags.debug_tp_add_watcher:
        tp_log_debug(f"tp_add_watcher() : {tp.id} {port=} {button=}")
    if not tp.port[port].button[button].pythonWatchers or not handler in tp.port[port].button[button].pythonWatchers:
        tp.port[port].button[button].watch(handler)
    else:
        tp_log_debug(f"tp_add_watcher() Duplicate registered but added {tp.id=} {port=} {button=}")
        tp.port[port].button[button].watch(handler)
    tp_add_notification(tp, port, button)


@tp_handle_exception
def tp_add_watcher_ss(tp_list: list | tuple, port, button, handler):
    # 여러 터치패널 장비에 동일한 버튼 핸들러 등록
    if not isinstance(tp_list, (list, tuple)):
        tp_log_error("tp_add_watcher_ss() -- tp_list must be a tuple or list of devices")
        raise TypeError
    for tp in tp_list:
        tp_add_watcher(tp, port, button, handler)


@tp_handle_exception
def tp_clear_watcher(tp, port, button):
    # 버튼의 모든 워처 제거
    if isinstance(tp.port[port].button[button].pythonWatchers, list):
        tp.port[port].button[button].pythonWatchers.clear()


@tp_handle_exception
def tp_add_watcher_level(tp, port, level, handler):
    # 레벨에 사용자 정의 핸들러 함수 등록 (중복 등록 방지 로직이 있으나 항상 등록함)
    if DebugFlags.debug_tp_add_watcher_level:
        tp_log_debug(f"tp_add_watcher_level() : {tp.id} {port=} {level=}")
    if not tp.port[port].level[level].pythonWatchers or not handler in tp.port[port].level[level].pythonWatchers:
        tp.port[port].level[level].watch(handler)
    else:
        tp_log_debug(f"tp_add_watcher() -- Duplicate registered but added {tp.id=} {port=} {level=}")
        tp.port[port].level[level].watch(handler)
    tp_add_notification_level(tp, port, level)


@tp_handle_exception
def tp_add_watcher_level_ss(tp_list: list | tuple, port, level, handler):
    # 여러 터치패널 장비에 동일한 레벨 핸들러 등록
    if not isinstance(tp_list, (list, tuple)):
        tp_log_error("tp_add_watcher_level_ss() -- tp_list must be a tuple or list of devices")
        raise TypeError
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
    if tp_get_device_state(tp):
        if tp.port[port].button[button].pythonWatchers:
            if isinstance(tp.port[port].button[button].pythonWatchers, list):
                tp_log_debug(f"{tp.id} {port=} {button=} num_watcher={len(tp.port[port].button[button].pythonWatchers)}")


@tp_handle_exception
def tp_get_button_pushed(tp, port, button):
    # 버튼의 현재 상태 값(누르지 않음=False, 누름=True) 반환
    if tp_get_device_state(tp):
        return tp.port[port].button[button].value
    return False


# 별칭 함수
def tp_get_btn_pushed(tp, port, button):
    return tp_get_button_pushed(tp, port, button)


@tp_handle_exception
def tp_get_button_state(tp, port, button):
    # 채널 상태 값 반환
    if tp_get_device_state(tp):
        return tp.port[port].channel[button].value
    tp_log_error(f"tp_get_button_state() : {tp.id} is not online")
    return False


# 별칭 함수
def tp_get_btn_state(tp, port, button):
    return tp_get_button_state(tp, port, button)


@tp_handle_exception
def tp_set_button(tp, port, button, value):
    # 버튼 피드백(채널 값) 설정
    if tp_get_device_state(tp):
        tp.port[port].channel[button].value = value
        if DebugFlags.debug_tp_set_button:
            tp_log_debug(f"BUTTON FEEDBACK < {tp.id} {port=} {button=} {value=}")


# 별칭 함수
def tp_set_btn(tp, port, button, value):
    tp_set_button(tp, port, button, value)


@tp_handle_exception
def tp_set_button_ss(tp_list: list | tuple, port, button, value):
    # 여러 터치패널 장비에 동일한 버튼 피드백 설정
    if not isinstance(tp_list, (list, tuple)):
        tp_log_error("tp_set_button_ss() -- tp_list must be a tuple or list of devices")
        raise TypeError
    for tp in tp_list:
        tp_set_button(tp, port, button, value)


# 별칭 함수
def tp_set_btn_ss(tp_list: list | tuple, port, button, value):
    tp_set_button_ss(tp_list, port, button, value)


@tp_handle_exception
def tp_set_button_state(tp, port, button, value):
    # 버튼 상태 설정 (장치 온라인 확인 후 tp_set_button 호출)
    if tp_get_device_state(tp):
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
        tp_log_error("tp_set_button_in_array() -- btn_list must be a list or tuple of button indices")
        raise TypeError
    for idx, btn in enumerate(btn_list):
        tp_set_button(tp, port, btn, index_condition == (idx + 1))


# 별칭 함수
def tp_set_btn_in_array(tp, port, btn_list: list | tuple, index_condition):
    tp_set_button_in_array(tp, port, btn_list, index_condition)


@tp_handle_exception
def tp_set_button_in_array_ss(tp_list: list | tuple, port, btn_list: list | tuple, index_condition):
    # 여러 터치패널의 버튼 배열 설정
    if not isinstance(tp_list, (list, tuple)):
        tp_log_error("tp_set_button_in_array_ss() -- tp_list must be a tuple or list of devices")
        raise TypeError
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
        tp_log_error("tp_set_button_in_range_ss() -- tp_list must be a tuple or list of devices")
        raise TypeError
    for tp in tp_list:
        tp_set_button_in_range(tp, port, index_btn_start, index_btn_range, index_condition)


# 별칭 함수
def tp_set_btn_in_range_ss(tp_list: list | tuple, port, index_btn_start, index_btn_range, index_condition):
    tp_set_button_in_range_ss(tp_list, port, index_btn_start, index_btn_range, index_condition)


@tp_handle_exception
def tp_get_level(tp, port, level):
    # 레벨(슬라이더) 값을 정수로 반환
    if tp_get_device_state(tp):
        return int(tp.port[port].level[level].value)
    tp_log_error(f"tp_get_level() : {tp.id} is not online")
    return 0


# 별칭 함수
def tp_get_lvl(tp, port, level):
    return tp_get_level(tp, port, level)


@tp_handle_exception
def tp_send_level(tp, port, level, value):
    # 레벨 값 전송/설정
    if tp_get_device_state(tp):
        tp.port[port].level[level].value = value
        if DebugFlags.debug_tp_send_level:
            print(f"LEVEL VALUE CHANGE - {tp.id} {port=} {level=} {value=}")


# 별칭 함수
def tp_send_lvl(tp, port, level, value):
    tp_send_level(tp, port, level, value)


@tp_handle_exception
def tp_set_level(tp, port, level, value, *args):
    # 레벨 설정 (tp_send_level 호출)
    tp_send_level(tp, port, level, value, *args)


# 별칭 함수
def tp_set_lvl(tp, port, level, value, *args):
    tp_send_level(tp, port, level, value, *args)


@tp_handle_exception
def tp_send_level_ss(tp_list: list | tuple, port, level, value):
    # 여러 터치패널에 동일한 레벨 값 전송
    if not isinstance(tp_list, (list, tuple)):
        tp_log_error("tp_send_level_ss() -- tp_list must be a tuple or list of devices")
        raise TypeError
    for tp in tp_list:
        tp_send_level(tp, port, level, value)


# 별칭 함수
def tp_send_lvl_ss(tp_list: list | tuple, port, level, value):
    tp_send_level_ss(tp_list, port, level, value)


@tp_handle_exception
def tp_set_level_ss(tp: list | tuple, port, level, value, *args):
    # 여러 터치패널의 레벨 설정
    tp_send_level_ss(tp, port, level, value, *args)


# 별칭 함수
def tp_set_lvl_ss(tp: list | tuple, port, level, value, *args):
    tp_send_lvl_ss(tp, port, level, value, *args)


@tp_handle_exception
def convert_text_to_unicode(text):
    # 텍스트를 유니코드 포맷 문자열로 변환 (각 문자를 4자리 16진수로 표현)
    return "".join(format(ord(char), "04X") for char in text)


# 별칭 함수
def convert_txt_to_unicode(text):
    return convert_text_to_unicode(text)


@tp_handle_exception
def tp_send_command(tp, port, command):
    # 터치패널에 명령어 전송
    if tp_get_device_state(tp):
        tp.port[port].send_command(command)
        if DebugFlags.debug_tp_send_command:
            print(f"tp_send_command() : {tp.id} {port=} {command=}")


# 별칭 함수
def tp_send_cmd(tp, port, command):
    tp_send_command(tp, port, command)


@tp_handle_exception
def tp_send_command_ss(tp_list: list | tuple, port, command):
    # 여러 터치패널에 동일한 명령어 전송
    if not isinstance(tp_list, (list, tuple)):
        tp_log_error(f"tp_send_command_ss() {command=} -- tp_list must be a tuple or list of devices")
        raise TypeError
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


# 별칭 함수
def tp_set_button_text_unicode_ss(tp_list: list | tuple, port, index_addr, text):
    # 여러 터치패널의 버튼 텍스트를 유니코드로 설정
    tp_send_command_ss(tp_list, port, f"^UNI-{index_addr},0,{convert_text_to_unicode(text)}")


@tp_handle_exception
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
