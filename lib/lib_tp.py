from typing import Union

from mojo import context


# ---------------------------------------------------------------------------- #
def tp_get_device_state(tp):
    return tp.isOnline() if tp.isOnline else False


# ---------------------------------------------------------------------------- #
def tp_add_watcher(tp, index_port, index_button, handler):
    context.log.debug(f"tp_add_watcher : {tp=} {index_port=} {index_button=} {handler=}")
    tp.port[index_port].button[index_button].watch(handler)


def tp_add_watcher_ss(tp_list: Union[list, tuple], index_port, index_button, handler):
    for tp in tp_list:
        tp_add_watcher(tp, index_port, index_button, handler)


def tp_clear_watcher(tp, index_port, index_button):
    if isinstance(tp.port[index_port].button[index_button].pythonWatchers, list):
        tp.port[index_port].button[index_button].pythonWatchers.clear()


def tp_add_watcher_level(tp, index_port, index_level, handler):
    context.log.debug(f"tp_add_watcher_level : {tp=} {index_port=} {index_level=} {handler=}")
    tp.port[index_port].level[index_level].watch(handler)


def tp_add_watcher_level_ss(tp_list: Union[list, tuple], index_port, index_level, handler):
    for tp in tp_list:
        tp_add_watcher_level(tp, index_port, index_level, handler)


def tp_clear_watcher_level(tp, index_port, index_level):
    if isinstance(tp.port[index_port].level[index_level].pythonWatchers, list):
        tp.port[index_port].level[index_level].pythonWatchers.clear()


def tp_show_watcher(tp, index_port, index_button):
    if tp_get_device_state(tp):
        if tp.port[index_port].button[index_button].pythonWatchers:
            if isinstance(tp.port[index_port].button[index_button].pythonWatchers, list):
                context.log.debug(
                    f"name={tp.id} {index_port=} {index_button=} num_watcher={len(tp.port[index_port].button[index_button].pythonWatchers)}"
                )


# ---------------------------------------------------------------------------- #
def tp_get_button_pushed(tp, index_port, index_button):
    if tp_get_device_state(tp):
        return tp.port[index_port].button[index_button].value


def tp_get_button_state(tp, index_port, index_button):
    if tp_get_device_state(tp):
        return tp.port[index_port].channel[index_button].value


def tp_set_button(tp, index_port, index_button, value):
    if tp_get_device_state(tp):
        tp.port[index_port].channel[index_button].value = value


def tp_set_button_ss(tp: Union[list, tuple], index_port, index_button, value):
    for t in tp:
        tp_set_button(t, index_port, index_button, value)


def tp_set_button_state(tp, index_port, index_button, value, *args):
    if tp_get_device_state(tp):
        tp_set_button(tp, index_port, index_button, value, *args)


def tp_set_button_state_ss(tp: Union[list, tuple], index_port, index_button, value, *args):
    tp_set_button_ss(tp, index_port, index_button, value, *args)


def tp_set_button_in_range(tp, port, index_btn_start, index_btn_range, index_condition):
    for i in range(index_btn_start, index_btn_start + index_btn_range + 1):
        tp_set_button(tp, port, i, index_condition == (i - index_btn_start + 1))


def tp_set_button_in_range_ss(tp: Union[list, tuple], port, index_btn_start, index_btn_range, index_condition):
    for t in tp:
        tp_set_button_in_range(t, port, index_btn_start, index_btn_range, index_condition)


def tp_get_level(tp, index_port, index_level):
    if tp_get_device_state(tp):
        return int(tp.port[index_port].level[index_level].value)


def tp_send_level(tp, index_port, index_level, value):
    if tp_get_device_state(tp):
        tp.port[index_port].level[index_level].value = value


def tp_set_level(tp, index_port, index_level, value, *args):
    tp_send_level(tp, index_port, index_level, value, *args)


def tp_send_level_ss(tp: Union[list, tuple], index_port, index_level, value):
    for t in tp:
        tp_send_level(t, index_port, index_level, value)


def tp_set_level_ss(tp: Union[list, tuple], index_port, index_level, value, *args):
    tp_send_level_ss(tp, index_port, index_level, value, *args)


def convert_text_to_unicode(text):
    return "".join(format(ord(char), "04X") for char in text)


def tp_send_command(tp, index_port, command_string):
    if tp_get_device_state(tp):
        tp.port[index_port].send_command(command_string)
        context.log.debug(f"tp_send_command : {tp=} {index_port=} {command_string=}")


def tp_send_command_ss(tp: Union[list, tuple], index_port, command_string):
    for t in tp:
        tp_send_command(t, index_port, command_string)


def tp_set_button_text_unicode(tp, index_port, index_addr, text):
    tp_send_command(tp, index_port, f"^UNI-{index_addr},0,{convert_text_to_unicode(text)}")


def tp_set_button_text_unicode_ss(tp: Union[list, tuple], index_port, index_addr, text):
    for t in tp:
        tp_send_command(t, index_port, f"^UNI-{index_addr},0,{convert_text_to_unicode(text)}")


def tp_set_button_text(tp, index_port, index_addr, text):
    tp_send_command(tp, index_port, f"^TXT-{index_addr},0,{text}")


def tp_set_button_text_ss(tp: Union[list, tuple], index_port, index_addr, text):
    for t in tp:
        tp_send_command(t, index_port, f"^TXT-{index_addr},0,{text}")


def tp_set_button_show_hide(tp, index_port, index_addr, value):
    state_str = 1 if value else 0
    tp.port[index_port].send_command(f"^SHO-{index_addr},{state_str}")
    tp.port[index_port].send_command(f"^ENA-{index_addr},{state_str}")


def tp_set_page(tp, page_name):
    tp_send_command(tp, 1, f"^PGE-{page_name}")


def tp_show_popup(tp, popup_name):
    tp_send_command(tp, 1, f"^PPN-{popup_name}")


def tp_hide_all_popup(tp):
    tp_send_command(tp, 1, "^PPX")


def tp_set_page_ss(tp: Union[list, tuple], page_name):
    tp_send_command_ss(tp, 1, f"^PGE-{page_name}")


def tp_show_popup_ss(tp: Union[list, tuple], popup_name):
    tp_send_command_ss(tp, 1, f"^PPN-{popup_name}")


def tp_hide_all_popup_ss(tp: Union[list, tuple]):
    tp_send_command_ss(tp, 1, "^PPX")
