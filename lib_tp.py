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
    if tp_get_device_state(tp) is False:
        return
    try:
        button = tp.port[index_port].button[index_btn]
        if button.pythonWatchers and isinstance(button.pythonWatchers, list):
            for watcher in button.pythonWatchers:
                print(f"watcher: {watcher}")
    except Exception as e:
        return


# ---------------------------------------------------------------------------- #
def tp_add_watcher(tp, index_port, index_btn, callback):
    tp_clear_watcher(tp, index_port, index_btn)
    try:
        tp.port[index_port].button[index_btn].watch(callback)
    except Exception as e:
        return


def tp_clear_watcher(tp, index_port, index_btn):
    if isinstance(tp.port[index_port].button[index_btn].pythonWatchers, list):
        try:
            tp.port[index_port].button[index_btn].pythonWatchers.clear()
        except Exception as e:
            return


# ---------------------------------------------------------------------------- #
def tp_add_watcher_level(tp, index_port, index_level, callback):
    tp_clear_watcher_level(tp, index_port, index_level)
    try:
        tp.port[index_port].level[index_level].watch(callback)
    except Exception as e:
        return


def tp_clear_watcher_level(tp, index_port, index_level):
    if isinstance(tp.port[index_port].level[index_level].pythonWatchers, list):
        try:
            tp.port[index_port].level[index_level].pythonWatchers.clear()
        except Exception as e:
            return


# ---------------------------------------------------------------------------- #
def tp_send_command(tp, index_port, command_string):
    if tp_get_device_state(tp) is False:
        print(f"warn tp_send_command() {tp=} {index_port=} Device not running")
        return
    try:
        tp.port[index_port].send_command(command_string)
    except Exception as e:
        return


# ---------------------------------------------------------------------------- #
def tp_get_button_pushed(tp, index_port, index_btn):
    if tp_get_device_state(tp) is False:
        return False
    try:
        return tp.port[index_port].button[index_btn].value == True
    except Exception as e:
        return


# ---------------------------------------------------------------------------- #
def tp_get_button_state(tp, index_port, index_btn):
    if tp_get_device_state(tp) is False:
        return False
    try:
        return tp.port[index_port].channel[index_btn].value == True
    except Exception as e:
        return


# ---------------------------------------------------------------------------- #
def tp_set_button(tp, index_port, index_btn, value):
    if tp_get_device_state(tp) is False:
        return
    print(f"warn tp_set_button {tp=} {index_port=} {index_btn=} {value=}")
    try:
        if value is None:
            value = False
        tp.port[index_port].channel[index_btn].value = value
    except Exception as e:
        return


# ---------------------------------------------------------------------------- #m
def tp_set_button_in_range(tp, port, index_btn_start, index_btn_range, index_condition):
    for i in range(index_btn_start, index_btn_start + index_btn_range + 1):
        tp_set_button(tp, port, i, index_condition == (i - index_btn_start + 1))


# ---------------------------------------------------------------------------- #
def tp_send_level(tp, index_port, index_lvl, value):
    if tp_get_device_state(tp) is False:
        return
    try:
        if value is None:
            value = 0
        tp.port[index_port].level[index_lvl].value = value
        print(f"warn tp_send_level {tp=} {index_port=} {index_lvl=} {value=}")
    except Exception as e:
        return


# ---------------------------------------------------------------------------- #
def tp_get_level(tp, index_port, index_lvl):
    if tp_get_device_state(tp) is False:
        return
    try:
        return int(tp.port[index_port].level[index_lvl].value)
    except Exception as e:
        return


# ---------------------------------------------------------------------------- #
def convert_text_to_unicode(text):
    return "".join(format(ord(char), "04X") for char in text)


# ---------------------------------------------------------------------------- #
def tp_set_button_text_unicode(tp, index_port, index_addr, text):
    tp_send_command(tp, index_port, f"^UNI-{index_addr},0,{convert_text_to_unicode(text)}")


# ---------------------------------------------------------------------------- #
def tp_set_button_text(tp, index_port, index_addr, text):
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
