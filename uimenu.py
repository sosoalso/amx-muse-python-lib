# ---------------------------------------------------------------------------- #
from buttonhandler import ButtonHandler
from lib_tp import (
    tp_add_watcher,
    tp_hide_all_popup,
    tp_set_button_in_range,
    tp_set_page,
    tp_show_popup,
)


# ---------------------------------------------------------------------------- #
class UIMenu:
    def __init__(self, dv_tp):
        self.dv_tp = dv_tp
        self.selected_menu = 0
        self.setup()

    def set_page(self, pagename):
        tp_set_page(self.dv_tp, pagename)

    def show_popup(self, popupname):
        tp_show_popup(self.dv_tp, popupname)  #
        self.selected_menu = int(popupname)

    def hide_all_popup(self):
        self.selected_menu = 0
        tp_hide_all_popup(self.dv_tp)

    def fb_menu(self):
        tp_set_button_in_range(self.dv_tp, 1, 11, 10, self.selected_menu)

    def select_menu(self, idx_menu):
        self.selected_menu = int(idx_menu)
        self.show_popup("{0:0>3d}".format(idx_menu))
        self.fb_menu()

    def close_menu(self, evt):
        if evt.value:
            self.hide_all_popup()
            self.fb_menu()

    def show_notification(self, adr, txt):
        self.dv_tp.port[1].send_command(f"'^UNI-', {adr}, ',0,', {txt}")

    def setup(self):
        for idx in range(1, 10):
            menu_btn = ButtonHandler()
            menu_btn.add_event_handler("push", lambda idx=int(idx): self.select_menu(int(idx)))
            tp_add_watcher(self.dv_tp, 1, idx + 10, menu_btn.handle_event)

        tp_add_watcher(self.dv_tp, 1, 100, self.close_menu)
        tp_set_button_in_range(self.dv_tp, 1, 11, 10, False)


# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
