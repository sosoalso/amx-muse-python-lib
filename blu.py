# ---------------------------------------------------------------------------- #
from mojo import context

from lib.blucontroller import BluController
from lib.buttonhandler import ButtonHandler
from lib.lib_tp import tp_add_watcher, tp_send_level, tp_set_button, tp_set_button_text

# ---------------------------------------------------------------------------- #
DV_MUSE = context.devices.get("idevice")
DV_BLU = context.devices.get("SoundwebLondonBLU-100-101")
DV_TP_10001 = context.devices.get("AMX-10001")
# ---------------------------------------------------------------------------- #
BLU_PATH = [("Gain Block Name", f"Channel 1", "Mute"), ("Gain Block Name", f"Channel 1", "Gain")]
# ---------------------------------------------------------------------------- #
blu_controller = BluController(DV_BLU)


def handle_blu_controller_online(*args):
    blu_controller.init(BLU_PATH)


blu_controller.device.online(handle_blu_controller_online)


# ---------------------------------------------------------------------------- #
# INFO : 터치판넬 피드백
# ---------------------------------------------------------------------------- #
def ui_refresh_blu_button_by_path(path):
    if path in BLU_PATH:
        idx = BLU_PATH.index(path)
        ch_index = idx + 1
        val = blu_controller.component_states.get_state(path)
        if val is not None:
            if ch_index == 1:
                tp_set_button(DV_TP_10001, 2, 101, val == "Muted")
            elif ch_index == 2:
                tp_send_level(DV_TP_10001, 2, 101, int(round(blu_controller.db_to_tp(float(val)), 0)))
                tp_set_button_text(DV_TP_10001, 2, 101, f"{round(val, 1)} db")


blu_controller.component_states.subscribe(ui_refresh_blu_button_by_path)


# ---------------------------------------------------------------------------- #
def ui_register():
    for idx, path in enumerate(BLU_PATH):
        if idx == 0:
            mute_toggle_button = ButtonHandler()
            mute_toggle_button.add_event_handler("push", lambda path=path: blu_controller.toggle_muted_unmuted(path))
            tp_add_watcher(DV_TP_10001, 2, 101, mute_toggle_button.handle_event)
            ui_refresh_blu_button_by_path(path)
        elif idx == 1:
            vol_up_button = ButtonHandler(repeat_interval=0.2)
            vol_down_button = ButtonHandler(repeat_interval=0.2)
            vol_up_button.add_event_handler("repeat", lambda path=path: blu_controller.vol_up(path))
            vol_down_button.add_event_handler("repeat", lambda path=path: blu_controller.vol_down(path))
            tp_add_watcher(DV_TP_10001, 2, 201, vol_up_button.handle_event)
            tp_add_watcher(DV_TP_10001, 2, 301, vol_down_button.handle_event)
            ui_refresh_blu_button_by_path(path)


def start(*args):
    ui_register()


DV_MUSE.online(start)
# ---------------------------------------------------------------------------- #
