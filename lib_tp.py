# ---------------------------------------------------------------------------- #
def tp_get_device_state(tp):
    try:
        if tp.isOnline:
            return tp.isOnline() is True
        else:
            return False
    except AttributeError:
        return False


def tp_show_watcher(tp, index_port, index_btn):
    """
    tp_show_watcher 함수는 tp 객체의 모든 요소에 대해 지정된 port와 btn의 상태를 반환합니다.
    """
    if tp_get_device_state(tp) is False:
        return
    try:
        button = tp.port[index_port].button[index_btn]
        print(button)
        if button.pythonWatchers and isinstance(button.pythonWatchers, list):
            print(button.pythonWatchers)
            for watcher in button.pythonWatchers:
                print(f"watcher: {watcher}")
    except Exception as e:
        print(f"Error showing watcher: {e}")


# ---------------------------------------------------------------------------- #
def tp_add_watcher(tp, index_port, index_btn, callback):
    """
    tp_add_watcher 함수는 tp 객체의 모든 요소에 대해 지정된 idx_port와 idx_btn에 대한 callback 함수를 등록합니다.
    """
    if tp_get_device_state(tp) is False:
        return
    tp_clear_watcher(tp, index_port, index_btn)
    try:
        tp.port[index_port].button[index_btn].watch(callback)
    except Exception as e:
        print(f"Error adding watcher: {e}")


def tp_clear_watcher(tp, index_port, index_btn):
    if tp_get_device_state(tp) is False:
        return
    if isinstance(tp.port[index_port].button[index_btn].pythonWatchers, list):
        try:
            tp.port[index_port].button[index_btn].pythonWatchers.clear()
        except Exception as e:
            print(f"Error removing watcher: {e}")


def tp_add_watcher_level(tp, index_port, index_level, callback):
    """
    tp_add_watcher 함수는 tp 객체의 모든 요소에 대해 지정된 port와 btn에 대한 callback 함수를 등록합니다.
    """
    if tp_get_device_state(tp) is False:
        return
    tp_clear_watcher_level(tp, index_port, index_level)
    try:
        tp.port[index_port].button[index_level].watch(callback)
    except Exception as e:
        print(f"Error adding watcher: {e}")


def tp_clear_watcher_level(tp, index_port, index_level):
    if tp_get_device_state(tp) is False:
        return
    if isinstance(tp.port[index_port].level[index_level].pythonWatchers, list):
        try:
            tp.port[index_port].level[index_level].pythonWatchers.clear()
        except Exception as e:
            print(f"Error removing watcher: {e}")


# ---------------------------------------------------------------------------- #
def tp_send_command(tp, index_port, command_string):
    """
    tp_send_command 함수는 tp 객체의 모든 요소에 대해 지정된 index_port command를 전송합니다.
    """
    pass
    if tp_get_device_state(tp) is False:
        # print(f"warn tp_send_command() {tp=} {index_port=} Device not running")
        return
    try:
        tp.port[index_port].send_command(command_string)
    except Exception as e:
        print(f"Error sending command_string: {e}")


# ---------------------------------------------------------------------------- #
def tp_set_button(tp, index_port, index_btn, value):
    """
    tp_set_button 함수는 tp 객체의 모든 요소에 대해 지정된 port와 btn의 상태[켜짐|꺼짐] 를 설정합니다.
    """
    if tp_get_device_state(tp) is False:
        # print(f"warn tp_set_button() {tp=} {index_port=} {index_btn=} Device not running")
        return
    # print(f"warn tp_set_button {tp=} {index_port=} {index_btn=} {value=}")
    try:
        if value is None:
            value = False
        tp.port[index_port].channel[index_btn].value = value
    except Exception as e:
        print(f"Error setting button {__name__=} {index_port=} {index_btn=} : {e}")


# ---------------------------------------------------------------------------- #
def tp_set_button_in_range(tp, port, index_btn_start, index_btn_range, index_condition):
    """
    tp_set_button_in_range 함수는 tp 객체의 모든 요소에 대해 지정된 port와 btn의 상태[켜짐|꺼짐] 를 설정합니다.
    """
    for i in range(index_btn_start, index_btn_start + index_btn_range + 1):
        tp_set_button(tp, port, i, index_condition == (i - index_btn_start + 1))


# ---------------------------------------------------------------------------- #
def tp_send_level(tp, index_port, index_lvl, value):
    """
    tp_send_level 함수는 tp 객체의 모든 요소에 대해 지정된 port와 idx_btn에 value를 전송합니다.
    """
    if tp_get_device_state(tp) is False:
        # print(f"warn tp_send_level() {tp=} {index_port=} {index_lvl=} Device not running")
        return
    try:
        if value is None:
            value = 0
        tp.port[index_port].level[index_lvl].value = value
        # print(f"warn tp_send_level {tp=} {index_port=} {index_lvl=} {value=}")
    except Exception as e:
        print(f"Error setting level {__name__=} {index_port=} {index_lvl=} : {e}")


# ---------------------------------------------------------------------------- #
def convert_text_to_unicode(text):
    """
    convert_text_to_unicode 함수는 주어진 텍스트를 유니코드 아스키로 변환하여 반환합니다.
    """
    return "".join(format(ord(char), "04X") for char in text)


# ---------------------------------------------------------------------------- #
def tp_set_button_text_unicode(tp, index_port, index_addr, text):
    """
    tp_set_button_text_unicode 함수는 tp 객체의 모든 요소에 대해 지정된 port, index_addr, text를 이용하여 버튼에 유니코드 텍스트를 표시합니다.
    """
    tp_send_command(tp, index_port, f"^UNI-{index_addr},0,{convert_text_to_unicode(text)}")


# ---------------------------------------------------------------------------- #
def tp_set_button_text(tp, index_port, index_addr, text):
    """
    tp_set_button_text 함수는 tp 객체의 모든 요소에 대해 지정된 port, index_addr, text를 이용하여 버튼에 텍스트를 표시합니다.
    """
    tp_send_command(tp, index_port, f"^TXT-{index_addr},0,{text}")


# ---------------------------------------------------------------------------- #
def tp_set_button_show_hide(tp, index_port, index_addr, value):
    state_str = 1 if value else 0
    tp.port[index_port].send_command(f"^SHO-{index_addr},{state_str}")
    tp.port[index_port].send_command(f"^ENA-{index_addr},{state_str}")


# ---------------------------------------------------------------------------- #
def tp_set_page(tp, page_name):
    tp_send_command(tp, 1, f"^PGE-{page_name}")


# ---------------------------------------------------------------------------- #
def tp_show_popup(tp, popup_name):
    tp_send_command(tp, 1, f"^PPN-{popup_name}")


# ---------------------------------------------------------------------------- #
def tp_hide_all_popup(tp):
    tp_send_command(tp, 1, "^PPX")


# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
