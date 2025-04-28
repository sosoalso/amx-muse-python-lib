# ---------------------------------------------------------------------------- #
def handle_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Exception occurred in {func.__name__}: {e}")
            return None

    return wrapper


# ---------------------------------------------------------------------------- #
@handle_exception
def tp_get_device_state(tp):
    return tp.isOnline() if tp.isOnline else False


# ---------------------------------------------------------------------------- #
@handle_exception
def tp_add_watcher(tp, index_port, index_btn, callback):
    tp.port[index_port].button[index_btn].watch(callback)


@handle_exception
def tp_clear_watcher(tp, index_port, index_btn):
    if isinstance(tp.port[index_port].button[index_btn].pythonWatchers, list):
        tp.port[index_port].button[index_btn].pythonWatchers.clear()


@handle_exception
def tp_add_watcher_level(tp, index_port, index_level, callback):
    tp.port[index_port].level[index_level].watch(callback)


@handle_exception
def tp_clear_watcher_level(tp, index_port, index_level):
    if isinstance(tp.port[index_port].level[index_level].pythonWatchers, list):
        tp.port[index_port].level[index_level].pythonWatchers.clear()


@handle_exception
def tp_show_watcher(tp, index_port, index_btn):
    if tp_get_device_state(tp):
        button = tp.port[index_port].button[index_btn]
        if button.pythonWatchers and isinstance(button.pythonWatchers, list):
            print(f"name={tp.id} {index_port=} {index_btn=} num_watcher={len(button.pythonWatchers)}")


# ---------------------------------------------------------------------------- #
@handle_exception
def tp_get_button_pushed(tp, index_port, index_btn):
    if tp_get_device_state(tp):
        return tp.port[index_port].button[index_btn].value


@handle_exception
def tp_get_button_state(tp, index_port, index_btn):
    if tp_get_device_state(tp):
        return tp.port[index_port].channel[index_btn].value


@handle_exception
def tp_set_button(tp, index_port, index_btn, value):
    if tp_get_device_state(tp):
        tp.port[index_port].channel[index_btn].value = value


def tp_set_button_state(tp, index_port, index_btn, value, *args):
    if tp_get_device_state(tp):
        tp_set_button(tp, index_port, index_btn, value, *args)


@handle_exception
def tp_set_button_in_range(tp, port, index_btn_start, index_btn_range, index_condition):
    for i in range(index_btn_start, index_btn_start + index_btn_range + 1):
        tp_set_button(tp, port, i, index_condition == (i - index_btn_start + 1))


@handle_exception
def tp_get_level(tp, index_port, index_lvl):
    if tp_get_device_state(tp):
        return int(tp.port[index_port].level[index_lvl].value)


@handle_exception
def tp_send_level(tp, index_port, index_lvl, value):
    if tp_get_device_state(tp):
        tp.port[index_port].level[index_lvl].value = value


def tp_set_level(tp, index_port, index_lvl, value, *args):
    tp_send_level(tp, index_port, index_lvl, value, *args)


# ---------------------------------------------------------------------------- #
@handle_exception
def tp_send_command(tp, index_port, command_string):
    if tp_get_device_state(tp):
        tp.port[index_port].send_command(command_string)


@handle_exception
def convert_text_to_unicode(text):
    return "".join(format(ord(char), "04X") for char in text)


@handle_exception
def tp_set_button_text_unicode(tp, index_port, index_addr, text):
    tp_send_command(tp, index_port, f"^UNI-{index_addr},0,{convert_text_to_unicode(text)}")


@handle_exception
def tp_set_button_text(tp, index_port, index_addr, text):
    tp_send_command(tp, index_port, f"^TXT-{index_addr},0,{text}")


@handle_exception
def tp_set_button_show_hide(tp, index_port, index_addr, value):
    state_str = 1 if value else 0
    tp.port[index_port].send_command(f"^SHO-{index_addr},{state_str}")
    tp.port[index_port].send_command(f"^ENA-{index_addr},{state_str}")


@handle_exception
def tp_set_page(tp, page_name):
    tp_send_command(tp, 1, f"^PGE-{page_name}")


@handle_exception
def tp_show_popup(tp, popup_name):
    tp_send_command(tp, 1, f"^PPN-{popup_name}")


@handle_exception
def tp_hide_all_popup(tp):
    tp_send_command(tp, 1, "^PPX")


# ---------------------------------------------------------------------------- #
if __name__ == "__main__":
    pass
