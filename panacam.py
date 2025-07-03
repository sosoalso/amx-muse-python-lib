from lib.simpleurlrequests import url_get


class PanaCam:
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.is_fast = False
        self.last_recall_preset = 0

    def toggle_speed(self):
        self.is_fast = not self.is_fast

    def set_speed(self, speed):
        self.is_fast = speed is True

    def get_speed(self):
        return 24 if self.is_fast else 12

    def get_tilt_speed(self):
        return 24 if self.is_fast else 12

    def get_pan_speed(self):
        return 24 if self.is_fast else 12

    def get_zoom_speed(self):
        return 24 if self.is_fast else 12

    # ---------------------------------------------------------------------------- #
    def move_up(self):
        url_get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23T{50+self.get_speed():02d}&res=1")

    def move_down(self):
        url_get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23T{50-self.get_speed():02d}&res=1")

    def move_left(self):
        url_get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23P{50-self.get_speed():02d}&res=1")

    def move_right(self):
        url_get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23P{50+self.get_speed():02d}&res=1")

    def move_stop(self):
        url_get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23PTS5050&res=1")

    def zoom_in(self):
        url_get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23Z&res=1")

    def zoom_out(self):
        url_get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23Z{50+self.get_zoom_speed():02d}&res=1")

    def zoom_stop(self):
        url_get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23Z{50-self.get_zoom_speed():02d}&res=1")

    def recall_preset(self, preset_no):
        url_get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23R{preset_no:02d}&res=1")
        self.last_recall_preset = preset_no

    def store_preset(self, preset_no):
        url_get(f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23M{preset_no:02d}&res=1")
