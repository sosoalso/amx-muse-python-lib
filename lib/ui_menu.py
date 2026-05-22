# 마지막 수정일 : 20260505
from lib.button import add_button
from lib.tp import (
    tp_hide_all_popup,
    tp_set_button_in_range,
    tp_set_page,
    tp_show_popup,
)
from lib.utility import handle_exception


class UiMenu:
    def __init__(self, tp):
        self.tp = tp
        self.selected_menu = 0
        self.debug = False
        self.init()

    def log_error(self, message):
        print(f"ui_menu(ERROR) -- {message}")

    def log_debug(self, message):
        if self.debug:
            print(f"ui_menu(DEBUG) -- {message}")

    @handle_exception
    def init(self):
        # 모든 팝업 닫기 버튼 (버튼 번호 100)
        add_button(self.tp, 1, 100, "push", self.hide_all_menu_popup)

        # 페이지 1 ~ 9 전환 버튼 (버튼 번호 1 ~ 9)
        for idx in range(1, 10):
            add_button(self.tp, 1, idx, "push", lambda idx=idx: self.show_page(idx))

        # 팝업 1 ~ 19 전환 버튼 (버튼 번호 11 ~ 29)
        for idx in range(1, 20):
            add_button(self.tp, 1, idx + 10, "push", lambda idx=idx: self.show_menu_popup(idx))
        self.selected_menu = 0
        self.refresh_menu_popup_button()

    @handle_exception
    def show_page(self, index_page):
        # 페이지 인덱스는 정수여야 함
        if not isinstance(index_page, int):
            self.log_error("show_page() -- index_page must be an integer.")
            raise ValueError
        # 페이지 인덱스는 1 ~ 9 범위 내여야 함
        if not 1 <= index_page <= 9:
            self.log_error("show_page() -- index_page must be an integer between 1 - 9.")
            raise ValueError
        self.hide_all_menu_popup()
        tp_set_page(self.tp, f"{index_page:02d}")

    @handle_exception
    def show_menu_popup(self, index_popup):
        # 팝업 인덱스는 정수여야 함
        if not isinstance(index_popup, int):
            self.log_error("show_menu_popup() -- index_popup must be an integer.")
            raise ValueError
        # 팝업 인덱스는 1 ~ 20 범위 내여야 함
        if not 1 <= index_popup <= 20:
            self.log_error("show_menu_popup() -- index_popup must be an integer between 1 - 20.")
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
        # 팝업 버튼 범위(11 ~ 29)에서 선택된 메뉴 버튼만 활성화
        tp_set_button_in_range(self.tp, 1, 1 + 10, 20 + 10, self.selected_menu)
