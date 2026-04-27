from lib.userdata import Userdata

# ---------------------------------------------------------------------------- #
VERSION = "2026.04.23"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class CamtrackPreset:
    """
    self.camtrack_preset 구조:
    {
        "preset_001": {"camera": 1, "preset": 1},
        ...
        "preset_MAX": {"camera": N, "preset": MAX}
    }
    - preset_index는 1부터 시작하며, 최대값은 max_preset_index
    - 각 preset은 "camera"와 "preset" 키를 가지며, 값은 해당 카메라와 프리셋 번호
    - 예시: "preset_001": {"camera": 1, "preset": 1} 은 첫 번째 프리셋이 카메라 1의 프리셋 1을 의미
    - camtrack_preset.json에 저장되어 있으며, 인스턴스 생성 시 자동으로 불러오기
    - 프리셋을 설정할 때는 set_preset(preset_index, cam_no, preset_no)를 사용
    - 프리셋을 가져올 때는 get_preset(preset_index) 또는 get_preset_cam(preset_index), get_preset_cam_preset(preset_index)를 사용
    """

    def __init__(self, max_preset_index=40, filename="camtrack_preset.json"):
        self.max_preset_index = max_preset_index
        self.userdata = Userdata(filename=filename)
        # JSON 파일에서 camtrack_preset 데이터를 로드하거나, 없으면 더미 데이터로 초기화
        self.camtrack_preset = self.userdata.get_value("camtrack_preset", self.make_dummy_presets())

    def make_dummy_presets(self):
        # 초기 프리셋 딕셔너리 생성: preset_001~preset_MAX 형식으로 카메라와 프리셋 번호를 0으로 초기화
        return {f"preset_{preset_index:03d}": {"camera": 0, "preset": 0} for preset_index in range(1, self.max_preset_index + 1)}

    def get_preset(self, preset_index):
        # 입력된 preset_index에 해당하는 프리셋 딕셔너리 반환 (없으면 빈 딕셔너리)
        return self.camtrack_preset.get(f"preset_{preset_index:03d}", {})

    def get_preset_cam(self, preset_index):
        # 해당 프리셋에 설정된 카메라 번호 반환
        preset = self.get_preset(preset_index)
        return preset.get("camera", 0)

    def get_preset_cam_preset(self, preset_index):
        # 해당 프리셋에 설정된 카메라 프리셋 번호 반환
        preset = self.get_preset(preset_index)
        return preset.get("preset", 0)

    def set_preset(self, preset_index, cam_no, preset_no, **kwargs):
        # 프리셋 설정: 카메라 번호, 프리셋 번호 및 추가 옵션(**kwargs)을 저장 후 JSON 파일에 동기화
        self.camtrack_preset[f"preset_{preset_index:03d}"] = {"camera": cam_no, "preset": preset_no, **kwargs}
        self.userdata.set_value("camtrack_preset", self.camtrack_preset)
