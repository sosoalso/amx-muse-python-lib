from mojo import context

from lib.button import add_button
from lib.lib_tp import (
    tp_hide_all_popup,
    tp_set_button_in_range,
    tp_set_page,
    tp_show_popup,
)
from lib.lib_yeoul import handle_exception

# ---------------------------------------------------------------------------- #
VERSION = "2025.09.27"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class UIMenu:
    def __init__(self, tp):
        self.tp = tp
        self.selected_menu = 0
        self.init()

    @handle_exception
    def init(self):
        add_button(self.tp, 1, 100, "push", self.hide_all_menu_popup, comment="모든 팝업 닫기 버튼")
        for idx in range(1, 10):  # 1 ~ 9
            add_button(
                self.tp, 1, idx, "push", lambda idx=idx: self.show_page(idx), comment=f"페이지 {idx+1} 번 전환 버튼"
            )
        for idx in range(1, 20):  # 11 ~ 39
            add_button(
                self.tp,
                1,
                idx + 10,
                "push",
                lambda idx=idx: self.show_menu_popup(idx),
                comment=f"팝업 {idx+1:02d} 번 전환 버튼",
            )
        self.selected_menu = 0
        self.refresh_menu_popup_button()

    @handle_exception
    def show_page(self, index_page):
        if not isinstance(index_page, int):
            context.log.error("UIMenu show_page() index_page 는 정수여야합니다.")
            raise ValueError
        if not 1 <= index_page <= 9:
            context.log.error("UIMenu show_page() index_page 는 1 - 9 사이의 정수여야합니다.")
            raise ValueError
        self.hide_all_menu_popup()
        tp_set_page(self.tp, f"{index_page:02d}")

    @handle_exception
    def show_menu_popup(self, index_popup):
        if not isinstance(index_popup, int):
            context.log.error("UIMenu show_page() index_popup 은 정수여야합니다.")
            raise ValueError
        if not 1 <= index_popup <= 20:
            context.log.error("UIMenu show_page() index_popup 은 1 - 20 사이의 정수여야합니다.")
            raise ValueError
        self.selected_menu = index_popup
        self.refresh_menu_popup_button()
        tp_show_popup(self.tp, f"{index_popup:03d}")

    @handle_exception
    def hide_all_menu_popup(self):
        tp_hide_all_popup(self.tp)
        self.selected_menu = 0
        self.refresh_menu_popup_button()

    @handle_exception
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
#         tp_send_lvl_ss(TP_LIST, 1, 1, count)
#         count += 1
#     s.set_interval(loading_bar, 0.1)
#     return loading_bar()
