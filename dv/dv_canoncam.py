from lib.simpleurlrequests import url_get


class CanonCam:
    def __init__(self, ip_address):
        self.ip_address = ip_address
        self.is_fast = False
        self.last_recall_preset = 0

    def toggle_speed(self):
        self.is_fast = not self.is_fast

    def set_speed(self, speed):
        self.is_fast = speed is True

    def get_speed(self):
        return "5000" if self.is_fast else "2500"

    def get_tilt_speed(self):
        return "5000" if self.is_fast else "2500"

    def get_pan_speed(self):
        return "5000" if self.is_fast else "2500"

    # ---------------------------------------------------------------------------- #
    def move_up(self):
        url_get(
            f"http://{self.ip_address}/-wvhttp-01-/control.cgi?tilt=up&tilt.speed={self.get_speed()}",
        )

    def move_down(self):
        url_get(
            f"http://{self.ip_address}/-wvhttp-01-/control.cgi?tilt=down&tilt.speed={self.get_speed()}",
        )

    def move_left(self):
        url_get(
            f"http://{self.ip_address}/-wvhttp-01-/control.cgi?pan=left&pan.speed={self.get_speed()}",
        )

    def move_right(self):
        url_get(
            f"http://{self.ip_address}/-wvhttp-01-/control.cgi?pan=right&pan.speed={self.get_speed()}",
        )

    def move_stop(self):
        url_get(f"http://{self.ip_address}/-wvhttp-01-/control.cgi?pan=stop&tilt=stop")

    def zoom_in(self):
        url_get(f"http://{self.ip_address}/-wvhttp-01-/control.cgi?zoom=tele")

    def zoom_out(self):
        url_get(f"http://{self.ip_address}/-wvhttp-01-/control.cgi?zoom=wide")

    def zoom_stop(self):
        url_get(f"http://{self.ip_address}/-wvhttp-01-/control.cgi?zoom=stop")

    def recall_preset(self, preset_no):
        url_get(f"http://{self.ip_address}/-wvhttp-01-/control.cgi?p={preset_no}")
        self.last_recall_preset = preset_no

    def store_preset(self, preset_no):
        url_get(f"http://{self.ip_address}/-wvhttp-01-/preset/set?p={preset_no}&all=enabled")
