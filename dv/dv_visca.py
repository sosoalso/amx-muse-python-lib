# 마지막 수정일 : 20260514
from lib.utility import CommonLogger, handle_exception


class Visca(CommonLogger):
    def __init__(self, dv, cam_id):
        self.dv = dv
        self.cam_id = cam_id
        self.is_fast = False
        self.last_recall_preset = 0

    @handle_exception
    def init(self):
        pass

    @handle_exception
    def toggle_speed(self):
        self.is_fast = not self.is_fast

    @handle_exception
    def set_speed(self, speed):
        self.is_fast = speed is True

    @handle_exception
    def get_move_speed(self):
        return [0x14, 0x12] if self.is_fast else [0x07, 0x06]

    @handle_exception
    def get_zoom_speed(self):
        return [0x07] if self.is_fast else [0x04]

    @handle_exception
    def send(self, msg: bytearray):
        msg.append(0xFF)
        self.log_debug(f"send() : {msg=}")
        self.dv.send(msg)

    @handle_exception
    def move_up(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x06, 0x01] + self.get_move_speed() + [0x03, 0x01]))

    @handle_exception
    def move_down(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x06, 0x01] + self.get_move_speed() + [0x03, 0x02]))

    @handle_exception
    def move_left(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x06, 0x01] + self.get_move_speed() + [0x01, 0x03]))

    @handle_exception
    def move_right(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x06, 0x01] + self.get_move_speed() + [0x02, 0x03]))

    @handle_exception
    def move_stop(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x06, 0x01] + [0x00, 0x00] + [0x03, 0x03]))

    @handle_exception
    def zoom_in(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x07] + [self.get_zoom_speed()[0] | 0x20]))

    @handle_exception
    def zoom_out(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x07] + [self.get_zoom_speed()[0] | 0x30]))

    @handle_exception
    def zoom_stop(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x07] + [0x00]))

    @handle_exception
    def recall_preset(self, preset_no):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x3F, 0x02, preset_no - 1]))

    @handle_exception
    def store_preset(self, preset_no):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x3F, 0x01, preset_no - 1]))

    @handle_exception
    def set_autofocus(self, cam_idx):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x18, 0x01, 0xFF]))

    @handle_exception
    def set_power_on(self, cam_idx):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x00, 0x02, 0xFF]))

    @handle_exception
    def set_power_off(self, cam_idx):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x00, 0x03, 0xFF]))

    @handle_exception
    def reboot(self, cam_idx):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x00, 0x00, 0xFF]))

    @handle_exception
    def custom_track_on(self, cam_idx):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x7D, 0x02, 0x00, 0xFF]))

    @handle_exception
    def custom_track_off(self, cam_idx):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x7D, 0x03, 0x00, 0xFF]))
