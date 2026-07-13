# 마지막 수정일 : 20260713
"""카메라 트래킹 프리셋 저장/조회 모듈.

프리셋 인덱스(예: 마이크/좌석 번호) → (카메라 번호, 카메라 프리셋 번호) 매핑을 관리한다.
마이크가 켜지면 해당 좌석의 카메라 프리셋으로 이동시키는 회의실 카메라 트래킹에 사용.
Userdata(JSON 파일)로 영속화되므로 컨트롤러 재시작 후에도 설정이 유지된다.
"""
from lib.userdata import Userdata


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
        self.userdata = Userdata(filename)
        loaded = self.userdata.get_value("camtrack_preset", None)
        # 저장된 파일이 없으면(첫 실행) 기본값으로 채운 더미 프리셋 생성
        self.camtrack_preset = loaded if loaded is not None else self.make_dummy_presets()

    def make_dummy_presets(self):
        """모든 프리셋을 기본값(camera=0, preset=0)으로 초기화하고 파일에 저장한다. 0 은 미설정 의미."""
        self.camtrack_preset = {f"preset_{i:03d}": {"camera": 0, "preset": 0} for i in range(1, self.max_preset_index + 1)}
        self.userdata.set_value("camtrack_preset", self.camtrack_preset)
        return self.camtrack_preset

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
        if not 1 <= preset_index <= self.max_preset_index:
            raise ValueError(f"set_preset() : preset_index must be in range 1 - {self.max_preset_index}, got {preset_index}")
        self.camtrack_preset[f"preset_{preset_index:03d}"] = {"camera": cam_no, "preset": preset_no, **kwargs}
        self.userdata.set_value("camtrack_preset", self.camtrack_preset)
