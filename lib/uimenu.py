from lib.button import add_button
from lib.lib_tp import (
    tp_hide_all_popup,
    tp_set_button_in_range,
    tp_set_page,
    tp_show_popup,
)

# ---------------------------------------------------------------------------- #
VERSION = "2025.06.23"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class UIMenu:
    def __init__(self, tp):
        self.tp = tp
        self.selected_menu = 0
        self.init()

    def init(self):
        add_button(self.tp, 1, 100, "push", self.hide_all_menu_popup)
        for idx in range(1, 10):
            add_button(self.tp, 1, idx, "push", self.show_page, idx)
        for idx in range(1, 20):
            add_button(self.tp, 1, idx + 10, "push", self.show_menu_popup, idx)
        self.selected_menu = 0
        self.refresh_menu_popup_button()

    def show_page(self, idx_page):
        if not isinstance(idx_page, int):
            raise ValueError("show_page idx_page must be an integer")
        if not (1 <= idx_page <= 9):
            raise ValueError("show_page idx_page must be between 1 and 9")
        self.hide_all_menu_popup()
        tp_set_page(self.tp, f"{idx_page:02d}")

    def show_menu_popup(self, idx_popup):
        if not isinstance(idx_popup, int):
            raise ValueError("show_menu_popup idx_popup must be an integer")
        if not (1 <= idx_popup <= 20):
            raise ValueError("show_menu_popup idx_popup must be between 1 and 20")
        self.selected_menu = idx_popup
        self.refresh_menu_popup_button()
        tp_show_popup(self.tp, f"{idx_popup:03d}")

    def hide_all_menu_popup(self):
        tp_hide_all_popup(self.tp)
        self.selected_menu = 0
        self.refresh_menu_popup_button()

    def refresh_menu_popup_button(self):
        tp_set_button_in_range(self.tp, 1, 1 + 10, 20 + 10, self.selected_menu)


# def create_loading_bar_closure():
#     s = Scheduler()
#     count = 0
#     def loading_bar():
#         nonlocal count
#         if count > 100:
#             s.shutdown()
#             return
#         tp_send_level_ss(TP_LIST, 1, 1, count)
#         count += 1
#     s.set_interval(loading_bar, 0.1)
#     return loading_bar()
