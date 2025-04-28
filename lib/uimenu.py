# ---------------------------------------------------------------------------- #
from lib.buttonhandler import ButtonHandler
from lib.lib_tp import (
    tp_add_watcher,
    tp_hide_all_popup,
    tp_set_button_in_range,
    tp_set_page,
    tp_show_popup,
)


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
class UIMenu:
    def __init__(self, tp):
        self.tp = tp
        self.selected_menu = 0
        self.init()

    @handle_exception
    def init(self, *args):
        for i in range(1, 10):
            menu_btn = ButtonHandler()
            menu_btn.add_event_handler("push", lambda idx=int(i): self.select_menu(int(idx)))
            tp_add_watcher(self.tp, 1, i + 10, menu_btn.handle_event)
        tp_add_watcher(self.tp, 1, 100, self.close_menu)
        tp_set_button_in_range(self.tp, 1, 11, 10, False)

    @handle_exception
    def set_page(self, pagename, *args):
        tp_set_page(self.tp, pagename)

    @handle_exception
    def show_popup(self, popupname, *args):
        tp_show_popup(self.tp, popupname)  #
        self.selected_menu = int(popupname)

    @handle_exception
    def hide_all_popup(self, *args):
        self.selected_menu = 0
        tp_hide_all_popup(self.tp)

    @handle_exception
    def ui_refresh_menu_buttons(self, *args):
        tp_set_button_in_range(self.tp, 1, 11, 10, self.selected_menu)

    @handle_exception
    def select_menu(self, index_menu, *args):
        """
        select_menu()
        Args:
            index_menu (int): 1~100 까지 메뉴 번호, 001 ~ 100 까지 팝업 열기
        """
        self.selected_menu = int(index_menu)
        self.show_popup(f"{self.selected_menu:0>3d}")
        self.ui_refresh_menu_buttons()

    @handle_exception
    def close_menu(self, *args):
        if args[0].value:
            self.hide_all_popup()
            self.ui_refresh_menu_buttons()

    @handle_exception
    def show_notification(self, adr, txt, *args):
        self.tp.port[1].send_command(f"'^UNI-', {adr}, ',0,', {txt}")


# ---------------------------------------------------------------------------- #
if __name__ == "__main__":
    pass
