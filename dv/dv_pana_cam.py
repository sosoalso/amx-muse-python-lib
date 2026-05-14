# 마지막 수정일 : 20260508
from lib.simple_url_requests import url_get
from lib.utility import handle_exception


class PanaCam:
    def __init__(self, ip):
        self.ip = ip
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
    def get_speed(self):
        return 24 if self.is_fast else 16

    @handle_exception
    def get_tilt_speed(self):
        return 24 if self.is_fast else 16

    @handle_exception
    def get_pan_speed(self):
        return 24 if self.is_fast else 16

    @handle_exception
    def get_zoom_speed(self):
        return 32 if self.is_fast else 24

    @handle_exception
    def move_up(self):
        url_get(url=f"http://{self.ip}/cgi-bin/aw_ptz?cmd=%23T{50+self.get_tilt_speed():02d}&res=1")

    @handle_exception
    def move_down(self):
        url_get(url=f"http://{self.ip}/cgi-bin/aw_ptz?cmd=%23T{50-self.get_tilt_speed():02d}&res=1")

    @handle_exception
    def move_left(self):
        url_get(url=f"http://{self.ip}/cgi-bin/aw_ptz?cmd=%23P{50-self.get_pan_speed():02d}&res=1")

    @handle_exception
    def move_right(self):
        url_get(url=f"http://{self.ip}/cgi-bin/aw_ptz?cmd=%23P{50+self.get_pan_speed():02d}&res=1")

    @handle_exception
    def move_stop(self):
        url_get(url=f"http://{self.ip}/cgi-bin/aw_ptz?cmd=%23PTS5050&res=1")

    @handle_exception
    def zoom_in(self):
        url_get(url=f"http://{self.ip}/cgi-bin/aw_ptz?cmd=%23Z{50+self.get_zoom_speed():02d}&res=1")

    @handle_exception
    def zoom_out(self):
        url_get(url=f"http://{self.ip}/cgi-bin/aw_ptz?cmd=%23Z{50-self.get_zoom_speed():02d}&res=1")

    @handle_exception
    def zoom_stop(self):
        url_get(url=f"http://{self.ip}/cgi-bin/aw_ptz?cmd=%23Z50&res=1")

    @handle_exception
    def recall_preset(self, preset_no):
        url_get(url=f"http://{self.ip}/cgi-bin/aw_ptz?cmd=%23R{preset_no-1:02d}&res=1")
        self.last_recall_preset = preset_no

    @handle_exception
    def store_preset(self, preset_no):
        url_get(url=f"http://{self.ip}/cgi-bin/aw_ptz?cmd=%23M{preset_no-1:02d}&res=1")
