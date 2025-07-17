from lib.lib_yeoul import handle_exception, log_debug, log_error, log_info

# ---------------------------------------------------------------------------- #
VERSION = "2025.07.17"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class DebugFlags:
    enable_debug_tp_add_watcher = True
    enable_debug_tp_add_watcher_level = True
    enable_debug_tp_add_notification = True
    enable_debug_tp_add_notification_level = True
    enable_debug_tp_set_button = False
    enable_debug_tp_send_level = False
    enable_debug_tp_send_command = False


def tp_set_debug_flag(
    tp_add_watcher=True,
    tp_add_watcher_level=True,
    tp_add_notification=True,
    tp_add_notification_level=True,
    tp_set_button=False,
    tp_send_level=False,
    enable_debug_tp_send_command=False,
):
    DebugFlags.enable_debug_tp_add_watcher = tp_add_watcher
    DebugFlags.enable_debug_tp_add_watcher_level = tp_add_watcher_level
    DebugFlags.enable_debug_tp_add_notification = tp_add_notification
    DebugFlags.enable_debug_tp_add_notification_level = tp_add_notification_level
    DebugFlags.enable_debug_tp_set_button = tp_set_button
    DebugFlags.enable_debug_tp_send_level = tp_send_level
    DebugFlags.enable_debug_tp_send_command = enable_debug_tp_send_command


# ---------------------------------------------------------------------------- #
def _notify(evt):
    if DebugFlags.enable_debug_tp_add_notification:
        _, port, _, button = (int(x) if x.isdigit() else x for x in evt.path.split("/"))
        log_debug(f"버튼 {'누름' if evt.value else '떼짐'} : {evt.device} {port=} {button=}")


@handle_exception
def tp_add_notification(tp, port, button):

    if not _notify in tp.port[port].button[button].pythonWatchers or not any(
        watcher.__name__ == _notify.__name__ for watcher in tp.port[port].button[button].pythonWatchers
    ):
        tp.port[port].button[button].watch(_notify)
    # else:
    #     log_debug(f"tp_add_notification() 중복 알림 등록됨. 기존 알림을 유지합니다. {tp.id=} {port=} {button=}")


@handle_exception
def tp_add_notification_ss(tp_list, port, button):
    if not isinstance(tp_list, (list, tuple)):
        log_error("tp_add_notification_ss() 에러 : tp_list 는 장비로 튜플이나 리스트여야합니다.")
        raise TypeError
    for tp in tp_list:
        tp_add_notification(tp, port, button)


@handle_exception
def tp_add_notification_level(tp, port, level):
    def _notify(evt):
        if DebugFlags.enable_debug_tp_add_notification_level:
            _, port, _, button = (int(x) if x.isdigit() else x for x in evt.path.split("/"))
            log_info(f"레벨 값={evt.value} : {evt.device} {port=} {button=}")

    if not _notify in tp.port[port].level[level].pythonWatchers or not any(
        watcher.__name__ == _notify.__name__ for watcher in tp.port[port].level[level].pythonWatchers
    ):
        tp.port[port].level[level].watch(_notify)


@handle_exception
def tp_add_notification_level_ss(tp_list, port, level):
    if not isinstance(tp_list, (list, tuple)):
        log_error("tp_add_notification_level_ss() 에러 : tp_list 는 장비로 튜플이나 리스트여야합니다.")
        raise TypeError
    for tp in tp_list:
        tp_add_notification_level(tp, port, level)


# ---------------------------------------------------------------------------- #
@handle_exception
def tp_get_device_state(tp):
    return tp.isOnline() if tp.isOnline else False


# ---------------------------------------------------------------------------- #
@handle_exception
def tp_add_watcher(tp, port, button, handler):
    if DebugFlags.enable_debug_tp_add_watcher:
        log_debug(f"tp_add_watcher() : {tp.id} {port=} {button=}")
    if not tp.port[port].button[button].pythonWatchers or not handler in tp.port[port].button[button].pythonWatchers:
        tp.port[port].button[button].watch(handler)
    else:
        log_debug(f"tp_add_watcher() 중복 등록됨. {tp.id=} {port=} {button=}")
        log_debug("그래도 추가는 할겁니다.")
        tp.port[port].button[button].watch(handler)

    tp_add_notification(tp, port, button)


@handle_exception
def tp_add_watcher_ss(tp_list: list | tuple, port, button, handler):
    if not isinstance(tp_list, (list, tuple)):
        log_error("tp_add_watcher_ss() 에러 : tp_list 는 장비로 튜플이나 리스트여야합니다.")
        raise TypeError
    for tp in tp_list:
        tp_add_watcher(tp, port, button, handler)


@handle_exception
def tp_clear_watcher(tp, port, button):
    if isinstance(tp.port[port].button[button].pythonWatchers, list):
        tp.port[port].button[button].pythonWatchers.clear()


@handle_exception
def tp_add_watcher_level(tp, port, level, handler):
    if DebugFlags.enable_debug_tp_add_watcher_level:
        log_debug(f"tp_add_watcher_level() : {tp.id} {port=} {level=}")
    if not tp.port[port].level[level].pythonWatchers or not handler in tp.port[port].level[level].pythonWatchers:
        tp.port[port].level[level].watch(handler)
    else:
        log_debug(f"tp_add_watcher() 중복 등록됨. {tp.id=} {port=} {level=}")
        log_debug("그래도 추가는 할겁니다.")
        tp.port[port].level[level].watch(handler)

    tp_add_notification_level(tp, port, level)


@handle_exception
def tp_add_watcher_level_ss(tp_list: list | tuple, port, level, handler):
    if not isinstance(tp_list, (list, tuple)):
        log_error("tp_add_watcher_level_ss() 에러 : tp_list 는 장비로 튜플이나 리스트여야합니다.")
        raise TypeError
    for tp in tp_list:
        tp_add_watcher_level(tp, port, level, handler)


@handle_exception
def tp_clear_watcher_level(tp, port, level):
    if isinstance(tp.port[port].level[level].pythonWatchers, list):
        tp.port[port].level[level].pythonWatchers.clear()


@handle_exception
def tp_show_watcher(tp, port, button):
    if tp_get_device_state(tp):
        if tp.port[port].button[button].pythonWatchers:
            if isinstance(tp.port[port].button[button].pythonWatchers, list):
                log_debug(f"{tp.id} {port=} {button=} num_watcher={len(tp.port[port].button[button].pythonWatchers)}")


# ---------------------------------------------------------------------------- #
@handle_exception
def tp_get_button_pushed(tp, port, button):
    if tp_get_device_state(tp):
        return tp.port[port].button[button].value
    return False


# info - alias
def tp_get_btn_pushed(tp, port, button):
    tp_get_button_pushed(tp, port, button)


@handle_exception
def tp_get_button_state(tp, port, button):
    if tp_get_device_state(tp):
        return tp.port[port].channel[button].value
    log_error(f"tp_get_button_state() : {tp.id} 은/는 온라인 상태가 아닙니다.")
    return False


# info - alias
def tp_get_btn_state(tp, port, button):
    tp_get_button_state(tp, port, button)


@handle_exception
def tp_set_button(tp, port, button, value):
    if tp_get_device_state(tp):
        tp.port[port].channel[button].value = value
        if DebugFlags.enable_debug_tp_set_button:
            log_debug(f"버튼 피드백 : {tp.id} {port=} {button=} {value=}")


# info - alias
def tp_set_btn(tp, port, button, value):
    tp_set_button(tp, port, button, value)


@handle_exception
def tp_set_button_ss(tp_list: list | tuple, port, button, value):
    if not isinstance(tp_list, (list, tuple)):
        log_error("tp_set_button_ss() 에러 : tp_list 는 장비로 튜플이나 리스트여야합니다.")
        raise TypeError
    for tp in tp_list:
        tp_set_button(tp, port, button, value)


# info - alias
def tp_set_btn_ss(tp_list: list | tuple, port, button, value):
    tp_set_button_ss(tp_list, port, button, value)


@handle_exception
def tp_set_button_state(tp, port, button, value):
    if tp_get_device_state(tp):
        tp_set_button(tp, port, button, value)


# info - alias
def tp_set_btn_state(tp, port, button, value):
    tp_set_button_state(tp, port, button, value)


@handle_exception
def tp_set_button_state_ss(tp: list | tuple, port, button, value):
    tp_set_button_ss(tp, port, button, value)


# info - alias
def tp_set_btn_state_ss(tp: list | tuple, port, button, value):
    tp_set_button_state_ss(tp, port, button, value)


@handle_exception
def tp_set_button_in_range(tp, port, index_btn_start, index_btn_range, index_condition):
    for index in range(index_btn_start, index_btn_start + index_btn_range):
        tp_set_button(tp, port, index, index_condition == (index - index_btn_start + 1))


# info - alias
def tp_set_btn_in_range(tp, port, index_btn_start, index_btn_range, index_condition):
    tp_set_button_in_range(tp, port, index_btn_start, index_btn_range, index_condition)


@handle_exception
def tp_set_button_in_array(tp, port, btn_list: list | tuple, index_condition):
    if not isinstance(btn_list, (list, tuple)):
        log_error("tp_set_button_in_array() 에러 : btn_list 는 버튼 인덱스 리스트여야합니다.")
        raise TypeError
    for idx, btn in enumerate(btn_list):
        tp_set_button(tp, port, btn, index_condition == (idx + 1))


# info - alias
def tp_set_btn_in_array(tp, port, btn_list: list | tuple, index_condition):
    tp_set_button_in_array(tp, port, btn_list, index_condition)


@handle_exception
def tp_set_button_in_array_ss(tp_list: list | tuple, port, btn_list: list | tuple, index_condition):
    if not isinstance(tp_list, (list, tuple)):
        log_error("tp_set_button_in_array_ss() 에러 : tp_list 는 장비로 튜플이나 리스트여야합니다.")
        raise TypeError
    for tp in tp_list:
        tp_set_button_in_array(tp, port, btn_list, index_condition)


# info - alias
def tp_set_btn_in_array_ss(tp_list: list | tuple, port, btn_list: list | tuple, index_condition):
    tp_set_button_in_array_ss(tp_list, port, btn_list, index_condition)


@handle_exception
def tp_set_button_in_list(tp, port, btn_list: list | tuple, index_condition):
    tp_set_button_in_array(tp, port, btn_list, index_condition)


# info - alias
def tp_set_btn_in_list(tp, port, btn_list: list | tuple, index_condition):
    tp_set_button_in_array(tp, port, btn_list, index_condition)


@handle_exception
def tp_set_button_in_list_ss(tp_list: list | tuple, port, btn_list: list | tuple, index_condition):
    tp_set_button_in_array_ss(tp_list, port, btn_list, index_condition)


# info - alias
def tp_set_btn_in_list_ss(tp_list: list | tuple, port, btn_list: list | tuple, index_condition):
    tp_set_button_in_array_ss(tp_list, port, btn_list, index_condition)


@handle_exception
def tp_set_button_in_range_ss(tp_list: list | tuple, port, index_btn_start, index_btn_range, index_condition):
    if not isinstance(tp_list, (list, tuple)):
        log_error("tp_send_level_ss() 에러 : tp_list 는 장비로 튜플이나 리스트여야합니다.")
        raise TypeError
    for tp in tp_list:
        tp_set_button_in_range(tp, port, index_btn_start, index_btn_range, index_condition)


# info - alias
def tp_set_btn_in_range_ss(tp_list: list | tuple, port, index_btn_start, index_btn_range, index_condition):
    tp_set_button_in_range_ss(tp_list, port, index_btn_start, index_btn_range, index_condition)


@handle_exception
def tp_get_level(tp, port, level):
    if tp_get_device_state(tp):
        return int(tp.port[port].level[level].value)
    log_error(f"tp_get_level() : {tp.id} 은/는 온라인 상태가 아닙니다.")
    return 0


# info - alias
def tp_get_lvl(tp, port, level):
    return tp_get_level(tp, port, level)


@handle_exception
def tp_send_level(tp, port, level, value):
    if tp_get_device_state(tp):
        tp.port[port].level[level].value = value
        if DebugFlags.enable_debug_tp_send_level:
            log_debug(f"레벨 값 변경 : {tp.id} {port=} {level=} {value=}")


# info - alias
def tp_send_lvl(tp, port, level, value):
    tp_send_level(tp, port, level, value)


@handle_exception
def tp_set_level(tp, port, level, value, *args):
    tp_send_level(tp, port, level, value, *args)


# info - alias
def tp_set_lvl(tp, port, level, value, *args):
    tp_send_level(tp, port, level, value, *args)


@handle_exception
def tp_send_level_ss(tp_list: list | tuple, port, level, value):
    if not isinstance(tp_list, (list, tuple)):
        log_error("tp_send_level_ss() 에러 : tp_list는 튜플이나 리스트여야합니다.")
        raise TypeError
    for tp in tp_list:
        tp_send_level(tp, port, level, value)


# info - alias
def tp_send_lvl_ss(tp_list: list | tuple, port, level, value):
    tp_send_level_ss(tp_list, port, level, value)


@handle_exception
def tp_set_level_ss(tp: list | tuple, port, level, value, *args):
    tp_send_level_ss(tp, port, level, value, *args)


# info - alias
def tp_set_lvl_ss(tp: list | tuple, port, level, value, *args):
    tp_send_level_ss(tp, port, level, value, *args)


@handle_exception
def convert_text_to_unicode(text):
    return "".join(format(ord(char), "04X") for char in text)


@handle_exception
def tp_send_command(tp, port, command):
    if tp_get_device_state(tp):
        tp.port[port].send_command(command)
        if DebugFlags.enable_debug_tp_send_command:
            log_debug(f"tp_send_command() : {tp.id} {port=} {command=}")


# info - alias
def tp_send_cmd(tp, port, command):
    tp_send_command(tp, port, command)


@handle_exception
def tp_send_command_ss(tp_list: list | tuple, port, command):
    if not isinstance(tp_list, (list, tuple)):
        log_error(f"tp_send_command_ss() {command=} 에러 : tp_list는 튜플이나 리스트여야합니다.")
        raise TypeError
    for tp in tp_list:
        tp_send_command(tp, port, command)


# info - alias
def tp_send_cmd_ss(tp_list: list | tuple, port, command):
    tp_send_command_ss(tp_list, port, command)


@handle_exception
def tp_set_button_text_unicode(tp, port, index_addr, text):
    tp_send_command(tp, port, f"^UNI-{index_addr},0,{convert_text_to_unicode(text)}")


# info - alias
def tp_set_btn_txt_unicode(tp, port, index_addr, text):
    tp_set_button_text_unicode(tp, port, index_addr, text)


# info - alias
def tp_set_button_text_unicode_ss(tp_list: list | tuple, port, index_addr, text):
    tp_send_command_ss(tp_list, port, f"^UNI-{index_addr},0,{convert_text_to_unicode(text)}")


@handle_exception
def tp_set_btn_txt_unicode_ss(tp_list: list | tuple, port, index_addr, text):
    tp_set_button_text_unicode_ss(tp_list, port, index_addr, text)


@handle_exception
def tp_set_button_text(tp, port, index_addr, text):
    tp_send_command(tp, port, f"^TXT-{index_addr},0,{text}")


# info - alias
def tp_set_btn_txt(tp, port, index_addr, text):
    tp_set_button_text(tp, port, index_addr, text)


@handle_exception
def tp_set_button_text_ss(tp_list: list | tuple, port, index_addr, text):
    tp_send_command_ss(tp_list, port, f"^TXT-{index_addr},0,{text}")


# info - alias
def tp_set_btn_txt_ss(tp_list: list | tuple, port, index_addr, text):
    tp_set_button_text_ss(tp_list, port, index_addr, text)


@handle_exception
def tp_set_button_show_hide(tp, port, index_addr, value):
    state_str = 1 if value else 0
    tp.port[port].send_command(f"^SHO-{index_addr},{state_str}")
    tp.port[port].send_command(f"^ENA-{index_addr},{state_str}")


# info - alias
def tp_set_btn_show_hide(tp, port, index_addr, value):
    tp_set_button_show_hide(tp, port, index_addr, value)


@handle_exception
def tp_set_page(tp, page_name):
    tp_send_command(tp, 1, f"^PGE-{page_name}")


@handle_exception
def tp_show_popup(tp, popup_name):
    tp_send_command(tp, 1, f"^PPN-{popup_name}")


@handle_exception
def tp_hide_popup(tp, popup_name):
    tp_send_command(tp, 1, f"^PPF-{popup_name}")


@handle_exception
def tp_hide_all_popup(tp):
    tp_send_command(tp, 1, "^PPX")


@handle_exception
def tp_set_page_ss(tp: list | tuple, page_name):
    tp_send_command_ss(tp, 1, f"^PGE-{page_name}")


@handle_exception
def tp_show_popup_ss(tp: list | tuple, popup_name):
    tp_send_command_ss(tp, 1, f"^PPN-{popup_name}")


@handle_exception
def tp_hide_popup_ss(tp: list | tuple, popup_name):
    tp_send_command_ss(tp, 1, f"^PPF-{popup_name}")


@handle_exception
def tp_hide_all_popup_ss(tp: list | tuple):
    tp_send_command_ss(tp, 1, "^PPX")
