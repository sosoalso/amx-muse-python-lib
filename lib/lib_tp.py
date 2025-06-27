from typing import Union

from mojo import context

from lib.lib_yeoul import handle_exception

# ---------------------------------------------------------------------------- #
VERSION = "2025.06.27"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
@handle_exception
def tp_add_notification(tp, port, button):
    def notify(evt):
        context.log.info(f"버튼 이벤트 {'눌림' if evt.value else '떼짐'} : {evt.device}/{evt.path}")

    if not notify in tp.port[port].button[button].pythonWatchers:
        tp.port[port].button[button].watch(notify)


@handle_exception
def tp_add_notification_ss(tp_list, port, button):
    if not isinstance(tp_list, (list, tuple)):
        raise TypeError("tp_add_watcher_ss error : tp_list must be a list or tuple")
    for tp in tp_list:
        tp_add_notification(tp, port, button)


@handle_exception
def tp_add_notification_level(tp, port, level):
    def notify(evt):
        context.log.info(f"레벨 이벤트 값:{evt.value} : {evt.device}/{evt.path}")

    if not notify in tp.port[port].level[level].pythonWatchers:
        tp.port[port].level[level].watch(notify)


@handle_exception
def tp_add_notification_level_ss(tp_list, port, level):
    if not isinstance(tp_list, (list, tuple)):
        raise TypeError("tp_add_watcher_ss error : tp_list must be a list or tuple")
    for tp in tp_list:
        tp_add_notification_level(tp, port, level)


# ---------------------------------------------------------------------------- #
@handle_exception
def tp_get_device_state(tp):
    return tp.isOnline() if tp.isOnline else False


# ---------------------------------------------------------------------------- #
@handle_exception
def tp_add_watcher(tp, index_port, index_button, handler):
    context.log.debug(f"tp_add_watcher : {tp.id} 포트:{index_port} 버튼:{index_button}")
    tp.port[index_port].button[index_button].watch(handler)
    tp_add_notification(tp, index_port, index_button)


@handle_exception
def tp_add_watcher_ss(tp_list: Union[list, tuple], index_port, index_button, handler):
    if not isinstance(tp_list, (list, tuple)):
        raise TypeError("tp_add_watcher_ss error : tp_list must be a list or tuple")
    for tp in tp_list:
        tp_add_watcher(tp, index_port, index_button, handler)


@handle_exception
def tp_clear_watcher(tp, index_port, index_button):
    if isinstance(tp.port[index_port].button[index_button].pythonWatchers, list):
        tp.port[index_port].button[index_button].pythonWatchers.clear()


@handle_exception
def tp_add_watcher_level(tp, index_port, index_level, handler):
    context.log.debug(f"tp_add_watcher_level : {tp.id} 포트:{index_port} 레벨:{index_level}")
    tp.port[index_port].level[index_level].watch(handler)
    tp_add_notification_level(tp, index_port, index_level)


@handle_exception
def tp_add_watcher_level_ss(tp_list: Union[list, tuple], index_port, index_level, handler):
    if not isinstance(tp_list, (list, tuple)):
        raise TypeError("tp_add_watcher_level_ss error : tp_list must be a list or tuple")
    for tp in tp_list:
        tp_add_watcher_level(tp, index_port, index_level, handler)


@handle_exception
def tp_clear_watcher_level(tp, index_port, index_level):
    if isinstance(tp.port[index_port].level[index_level].pythonWatchers, list):
        tp.port[index_port].level[index_level].pythonWatchers.clear()


@handle_exception
def tp_show_watcher(tp, index_port, index_button):
    if tp_get_device_state(tp):
        if tp.port[index_port].button[index_button].pythonWatchers:
            if isinstance(tp.port[index_port].button[index_button].pythonWatchers, list):
                context.log.debug(
                    f"name={tp.id} {index_port=} {index_button=} num_watcher={len(tp.port[index_port].button[index_button].pythonWatchers)}"
                )


# ---------------------------------------------------------------------------- #
@handle_exception
def tp_get_button_pushed(tp, index_port, index_button) -> bool:
    if tp_get_device_state(tp):
        return tp.port[index_port].button[index_button].value
    return False


@handle_exception
def tp_get_btn_pushed(tp, index_port, index_button) -> bool:
    tp_get_button_pushed(tp, index_port, index_button)


@handle_exception
def tp_get_button_state(tp, index_port, index_button):
    if tp_get_device_state(tp):
        return tp.port[index_port].channel[index_button].value


@handle_exception
def tp_get_btn_state(tp, index_port, index_button):
    tp_get_button_state(tp, index_port, index_button)


@handle_exception
def tp_set_button(tp, index_port, index_button, value):
    if tp_get_device_state(tp):
        tp.port[index_port].channel[index_button].value = value


@handle_exception
def tp_set_btn(tp, index_port, index_button, value):
    tp_set_button(tp, index_port, index_button, value)


@handle_exception
def tp_set_button_ss(tp_list: Union[list, tuple], index_port, index_button, value):
    if not isinstance(tp_list, (list, tuple)):
        raise TypeError("tp_set_button_ss error : tp_list must be a list or tuple")
    for tp in tp_list:
        tp_set_button(tp, index_port, index_button, value)


@handle_exception
def tp_set_btn_ss(tp_list: Union[list, tuple], index_port, index_button, value):
    tp_set_button_ss(tp_list, index_port, index_button, value)


@handle_exception
def tp_set_button_state(tp, index_port, index_button, value):
    if tp_get_device_state(tp):
        tp_set_button(tp, index_port, index_button, value)


@handle_exception
def tp_set_btn_state(tp, index_port, index_button, value):
    tp_set_button_state(tp, index_port, index_button, value)


@handle_exception
def tp_set_button_state_ss(tp: Union[list, tuple], index_port, index_button, value):
    tp_set_button_ss(tp, index_port, index_button, value)


@handle_exception
def tp_set_btn_state_ss(tp: Union[list, tuple], index_port, index_button, value):
    tp_set_button_state_ss(tp, index_port, index_button, value)


@handle_exception
def tp_set_button_in_range(tp, port, index_btn_start, index_btn_range, index_condition):
    for index in range(index_btn_start, index_btn_start + index_btn_range):
        tp_set_button(tp, port, index, index_condition == (index - index_btn_start + 1))


@handle_exception
def tp_set_btn_in_range(tp, port, index_btn_start, index_btn_range, index_condition):
    tp_set_button_in_range(tp, port, index_btn_start, index_btn_range, index_condition)


@handle_exception
def tp_set_button_in_range_ss(tp_list: Union[list, tuple], port, index_btn_start, index_btn_range, index_condition):
    if not isinstance(tp_list, (list, tuple)):
        raise TypeError("tp_send_level_ss error : tp_list must be a list or tuple")
    for tp in tp_list:
        tp_set_button_in_range(tp, port, index_btn_start, index_btn_range, index_condition)


@handle_exception
def tp_set_btn_in_range_ss(tp_list: Union[list, tuple], port, index_btn_start, index_btn_range, index_condition):
    tp_set_button_in_range_ss(tp_list, port, index_btn_start, index_btn_range, index_condition)


@handle_exception
def tp_get_level(tp, index_port, index_level):
    if tp_get_device_state(tp):
        return int(tp.port[index_port].level[index_level].value)


@handle_exception
def tp_get_lvl(tp, index_port, index_level):
    return tp_get_level(tp, index_port, index_level)


@handle_exception
def tp_send_level(tp, index_port, index_level, value):
    if tp_get_device_state(tp):
        tp.port[index_port].level[index_level].value = value


@handle_exception
def tp_send_lvl(tp, index_port, index_level, value):
    tp_send_level(tp, index_port, index_level, value)


@handle_exception
def tp_set_level(tp, index_port, index_level, value, *args):
    tp_send_level(tp, index_port, index_level, value, *args)


@handle_exception
def tp_set_lvl(tp, index_port, index_level, value, *args):
    tp_send_level(tp, index_port, index_level, value, *args)


@handle_exception
def tp_send_level_ss(tp_list: Union[list, tuple], index_port, index_level, value):
    if not isinstance(tp_list, (list, tuple)):
        raise TypeError("tp_send_level_ss error : tp_list must be a list or tuple")
    for tp in tp_list:
        tp_send_level(tp, index_port, index_level, value)


@handle_exception
def tp_send_lvl_ss(tp_list: Union[list, tuple], index_port, index_level, value):
    tp_send_level_ss(tp_list, index_port, index_level, value)


@handle_exception
def tp_set_level_ss(tp: Union[list, tuple], index_port, index_level, value, *args):
    tp_send_level_ss(tp, index_port, index_level, value, *args)


@handle_exception
def tp_set_lvl_ss(tp: Union[list, tuple], index_port, index_level, value, *args):
    tp_send_level_ss(tp, index_port, index_level, value, *args)


@handle_exception
def convert_text_to_unicode(text):
    return "".join(format(ord(char), "04X") for char in text)


@handle_exception
def tp_send_command(tp, index_port, command_string):
    if tp_get_device_state(tp):
        tp.port[index_port].send_command(command_string)
        context.log.debug(f"tp_send_command : {tp=} {index_port=} {command_string=}")


@handle_exception
def tp_send_cmd(tp, index_port, command_string):
    tp_send_command(tp, index_port, command_string)


@handle_exception
def tp_send_command_ss(tp_list: Union[list, tuple], index_port, command_string):
    if not isinstance(tp_list, (list, tuple)):
        raise TypeError("tp_send_command_ss error : tp_list must be a list or tuple")
    for tp in tp_list:
        tp_send_command(tp, index_port, command_string)


@handle_exception
def tp_send_cmd_ss(tp_list: Union[list, tuple], index_port, command_string):
    tp_send_command_ss(tp_list, index_port, command_string)


@handle_exception
def tp_set_button_text_unicode(tp, index_port, index_addr, text):
    tp_send_command(tp, index_port, f"^UNI-{index_addr},0,{convert_text_to_unicode(text)}")


@handle_exception
def tp_set_btn_text_unicode(tp, index_port, index_addr, text):
    tp_set_button_text_unicode(tp, index_port, index_addr, text)


@handle_exception
def tp_set_button_text_unicode_ss(tp_list: Union[list, tuple], index_port, index_addr, text):
    tp_send_command_ss(tp_list, index_port, f"^UNI-{index_addr},0,{convert_text_to_unicode(text)}")


@handle_exception
def tp_set_btn_text_unicode_ss(tp_list: Union[list, tuple], index_port, index_addr, text):
    tp_set_button_text_unicode_ss(tp_list, index_port, index_addr, text)


@handle_exception
def tp_set_button_text(tp, index_port, index_addr, text):
    tp_send_command(tp, index_port, f"^TXT-{index_addr},0,{text}")


@handle_exception
def tp_set_btn_text(tp, index_port, index_addr, text):
    tp_set_button_text(tp, index_port, index_addr, text)


@handle_exception
def tp_set_button_text_ss(tp_list: Union[list, tuple], index_port, index_addr, text):
    tp_send_command_ss(tp_list, index_port, f"^TXT-{index_addr},0,{text}")


@handle_exception
def tp_set_btn_text_ss(tp_list: Union[list, tuple], index_port, index_addr, text):
    tp_set_button_text_ss(tp_list, index_port, index_addr, text)


@handle_exception
def tp_set_button_show_hide(tp, index_port, index_addr, value):
    state_str = 1 if value else 0
    tp.port[index_port].send_command(f"^SHO-{index_addr},{state_str}")
    tp.port[index_port].send_command(f"^ENA-{index_addr},{state_str}")


@handle_exception
def tp_set_btn_show_hide(tp, index_port, index_addr, value):
    tp_set_button_show_hide(tp, index_port, index_addr, value)


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
def tp_set_page_ss(tp: Union[list, tuple], page_name):
    tp_send_command_ss(tp, 1, f"^PGE-{page_name}")


@handle_exception
def tp_show_popup_ss(tp: Union[list, tuple], popup_name):
    tp_send_command_ss(tp, 1, f"^PPN-{popup_name}")


@handle_exception
def tp_hide_popup_ss(tp: Union[list, tuple], popup_name):
    tp_send_command_ss(tp, 1, f"^PPF-{popup_name}")


@handle_exception
def tp_hide_all_popup_ss(tp: Union[list, tuple]):
    tp_send_command_ss(tp, 1, "^PPX")
