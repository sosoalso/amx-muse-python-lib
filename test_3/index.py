from mojo import context

from lib.button import add_btn
from lib.lib_tp import tp_set_btn_in_range, tp_set_debug_flag, tp_show_popup

context.log.level = "DEBUG"
tp_set_debug_flag(True, True, True, True, True, True, True)
DV_TP = context.devices.get("AMX-10001")

add_btn(DV_TP, 1, 11, "push", lambda: tp_show_popup(DV_TP, "01_home"))
add_btn(DV_TP, 1, 11, "push", lambda: tp_set_btn_in_range(DV_TP, 1, 11, 5, 1))
add_btn(DV_TP, 1, 12, "push", lambda: tp_show_popup(DV_TP, "02_matrix1"))
add_btn(DV_TP, 1, 12, "push", lambda: tp_set_btn_in_range(DV_TP, 1, 11, 5, 2))


# leave this as the last line in the Python script
context.run(globals())
