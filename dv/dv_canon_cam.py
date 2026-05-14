# 마지막 수정일 : 20260508
from lib.simpleurlrequests import url_get
from lib.utility import handle_exception


class CanonCam:
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
        return "5000" if self.is_fast else "2500"

    @handle_exception
    def get_tilt_speed(self):
        return "5000" if self.is_fast else "2500"

    @handle_exception
    def get_pan_speed(self):
        return "5000" if self.is_fast else "2500"

    @handle_exception
    def move_up(self):
        url_get(
            f"http://{self.ip}/-wvhttp-01-/control.cgi?tilt=up&tilt.speed={self.get_speed()}",
        )

    @handle_exception
    def move_down(self):
        url_get(
            f"http://{self.ip}/-wvhttp-01-/control.cgi?tilt=down&tilt.speed={self.get_speed()}",
        )

    @handle_exception
    def move_left(self):
        url_get(
            f"http://{self.ip}/-wvhttp-01-/control.cgi?pan=left&pan.speed={self.get_speed()}",
        )

    @handle_exception
    def move_right(self):
        url_get(
            f"http://{self.ip}/-wvhttp-01-/control.cgi?pan=right&pan.speed={self.get_speed()}",
        )

    @handle_exception
    def move_stop(self):
        url_get(f"http://{self.ip}/-wvhttp-01-/control.cgi?pan=stop&tilt=stop")

    @handle_exception
    def zoom_in(self):
        url_get(f"http://{self.ip}/-wvhttp-01-/control.cgi?zoom=tele")

    @handle_exception
    def zoom_out(self):
        url_get(f"http://{self.ip}/-wvhttp-01-/control.cgi?zoom=wide")

    @handle_exception
    def zoom_stop(self):
        url_get(f"http://{self.ip}/-wvhttp-01-/control.cgi?zoom=stop")

    @handle_exception
    def recall_preset(self, preset_no):
        url_get(f"http://{self.ip}/-wvhttp-01-/control.cgi?p={preset_no}")
        self.last_recall_preset = preset_no

    @handle_exception
    def store_preset(self, preset_no):
        url_get(f"http://{self.ip}/-wvhttp-01-/preset/set?p={preset_no}&all=enabled")
