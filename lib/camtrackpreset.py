from lib.userdata import Userdata

# ---------------------------------------------------------------------------- #
VERSION = "2025.07.05"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class CamtrackPreset:
    """
    self.camtrack_preset 구조:
    {
        "preset_001": {"camera": 0, "preset": 1},
        ...
        "preset_MAX": {"camera": 0, "preset": MAX}
    }
    - preset_index는 1부터 시작하며, 최대값은 max_preset_index입니다.
    - 각 preset은 "camera"와 "preset" 키를 가지며, 값은 해당 카메라와 프리셋 번호입니다.
    - 예시: "preset_001": {"camera": 0, "preset": 1}은 첫 번째 프리셋이 카메라 0의 프리셋 1을 의미합니다.
    - camtrack_preset.db에 저장되어 있으며, 프로그램 시작 시 불러옵니다.
    - 프리셋을 설정할 때는 set_preset(preset_index, cam_no, preset_no)를 사용합니다.
    - 프리셋을 가져올 때는 get_preset(preset_index) 또는 get_preset_cam(preset_index), get_preset_cam_preset(preset_index)를 사용합니다.
    """

    def __init__(self, max_preset_index=40, db_path="camtrack_preset.db"):
        self.max_preset_index = max_preset_index
        self.userdata = Userdata(db_path=db_path)
        self.camtrack_preset = self.userdata.get_value("camtrack_preset", self.make_dummy_presets())

    def make_dummy_presets(self):
        return {
            f"preset_{preset_index:03d}": {"camera": 0, "preset": 0}
            for preset_index in range(1, self.max_preset_index + 1)
        }

    def get_preset(self, preset_index):
        return self.camtrack_preset.get(f"preset_{preset_index:03d}", {})
        # return next((preset for preset in self.camtrack_preset or {} if preset["index"] == index), {})

    def get_preset_cam(self, preset_index):
        preset = self.get_preset(preset_index)
        return preset.get("camera", 0)

    def get_preset_cam_preset(self, preset_index):
        preset = self.get_preset(preset_index)
        return preset.get("preset", 0)

    def set_preset(self, preset_index, cam_no, preset_no):
        self.camtrack_preset[f"preset_{preset_index:03d}"] = {"camera": cam_no, "preset": preset_no}
        self.userdata.set_value("camtrack_preset", self.camtrack_preset)  # camtrack_preset.db에 저장
