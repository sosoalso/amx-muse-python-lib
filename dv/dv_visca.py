class Visca:
    def __init__(self, dv, cam_id):
        self.dv = dv
        self.cam_id = cam_id
        self.is_fast = False
        self.last_recall_preset = 0

    def toggle_speed(self):
        self.is_fast = not self.is_fast

    def set_speed(self, speed):
        self.is_fast = speed is True

    def get_move_speed(self):
        return [0x14, 0x12] if self.is_fast else [0x07, 0x06]

    def get_zoom_speed(self):
        return [0x07] if self.is_fast else [0x04]

    def send(self, msg: bytearray):
        msg.append(0xFF)
        # fixme
        print(msg)
        self.dv.send(msg)

    # ---------------------------------------------------------------------------- #
    def move_up(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x06, 0x01] + self.get_move_speed() + [0x03, 0x01]))

    def move_down(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x06, 0x01] + self.get_move_speed() + [0x03, 0x02]))

    def move_left(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x06, 0x01] + self.get_move_speed() + [0x01, 0x03]))

    def move_right(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x06, 0x01] + self.get_move_speed() + [0x02, 0x03]))

    def move_stop(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x06, 0x01] + [0x00, 0x00] + [0x03, 0x03]))

    def zoom_in(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x07] + [self.get_zoom_speed()[0] | 0x20]))

    def zoom_out(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x07] + [self.get_zoom_speed()[0] | 0x30]))

    def zoom_stop(self):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x07] + [0x00]))

    def recall_preset(self, preset_no):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x3F, 0x02, preset_no - 1]))

    def store_preset(self, preset_no):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x3F, 0x01, preset_no - 1]))

    def set_autofocus(self, cam_idx):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x18, 0x01, 0xFF]))

    def set_power_on(self, cam_idx):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x00, 0x02, 0xFF]))

    def set_power_off(self, cam_idx):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x00, 0x03, 0xFF]))

    def reboot(self, cam_idx):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x00, 0x00, 0xFF]))

    def custom_track_on(self, cam_idx):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x7D, 0x02, 0x00, 0xFF]))

    def custom_track_off(self, cam_idx):
        self.send(bytearray([self.cam_id + 0x80, 0x01] + [0x04, 0x7D, 0x03, 0x00, 0xFF]))
