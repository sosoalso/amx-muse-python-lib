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
        return 24 if self.is_fast else 16

    def get_tilt_speed(self):
        return 24 if self.is_fast else 16

    def get_pan_speed(self):
        return 24 if self.is_fast else 16

    def get_zoom_speed(self):
        return 32 if self.is_fast else 24

    # ---------------------------------------------------------------------------- #
    def move_up(self):
        url_get(url=f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23T{50+self.get_tilt_speed():02d}&res=1", header={})

    def move_down(self):
        url_get(url=f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23T{50-self.get_tilt_speed():02d}&res=1", header={})

    def move_left(self):
        url_get(url=f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23P{50-self.get_pan_speed():02d}&res=1", header={})

    def move_right(self):
        url_get(url=f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23P{50+self.get_pan_speed():02d}&res=1", header={})

    def move_stop(self):
        url_get(url=f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23PTS5050&res=1", header={})

    def zoom_in(self):
        url_get(url=f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23Z{50+self.get_zoom_speed():02d}&res=1", header={})

    def zoom_out(self):
        url_get(url=f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23Z{50-self.get_zoom_speed():02d}&res=1", header={})

    def zoom_stop(self):
        url_get(url=f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23Z50&res=1", header={})

    def recall_preset(self, preset_no):
        url_get(url=f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23R{preset_no-1:02d}&res=1", header={})
        self.last_recall_preset = preset_no

    def store_preset(self, preset_no):
        url_get(url=f"http://{self.ip_address}/cgi-bin/aw_ptz?cmd=%23M{preset_no-1:02d}&res=1", header={})
