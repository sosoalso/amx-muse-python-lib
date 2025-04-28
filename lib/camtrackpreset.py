# ---------------------------------------------------------------------------- #
import json
import os


# ---------------------------------------------------------------------------- #
def handle_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Exception occurred in {func.__name__}: {e}")
            return None

    return wrapper


# ---------------------------------------------------------------------------- #
class CamtrackPreset:
    # 카메라 트랙 프리셋을 저장하고 로드하는 클래스
    def __init__(self, filename="camtrack_preset.json", max_preset_index=40):
        # 파일명 및 최대 프리셋 인덱스 설정
        self.filename = filename
        self.max_preset_index = max_preset_index
        self.presets = {}
        self.init()

    @handle_exception
    def init(self):
        # 설정 파일이 없으면 더미 프리셋 생성 후 저장, 있으면 로드
        if not os.path.exists(self.filename):
            self.presets = self.make_dummy_presets()
            self.save_file()
        else:
            self.load_file()

    @handle_exception
    def make_dummy_presets(self):
        # 더미 프리셋 목록 생성
        return {
            "presets": [
                {"index": preset_index + 1, "camera": 0, "preset": 0} for preset_index in range(self.max_preset_index)
            ]
        }

    @handle_exception
    def load_file(self):
        # 파일에서 프리셋 데이터 로드
        with open(self.filename, "r", encoding="utf-8") as file:
            self.presets = json.load(file)

    @handle_exception
    def save_file(self):
        # 프리셋 데이터를 파일에 저장
        with open(self.filename, "w", encoding="utf-8") as output_file:
            json.dump(self.presets, output_file, indent=2)
        return True

    @handle_exception
    def sort_presets(self):
        # 인덱스를 기준으로 프리셋 리스트 정렬
        self.presets["presets"].sort(key=lambda x: x["index"])

    @handle_exception
    def get_preset(self, index):
        # 특정 인덱스에 해당하는 프리셋 정보 반환
        return next((preset for preset in self.presets["presets"] if preset["index"] == index), None)

    @handle_exception
    def set_preset(self, preset_index, cam_no, preset_no):
        # 특정 인덱스의 프리셋 정보 수정 후 저장
        target_preset = self.get_preset(preset_index)
        if target_preset:
            target_preset["camera"] = cam_no
            target_preset["preset"] = preset_no
            self.sort_presets()
            self.save_file()


# ---------------------------------------------------------------------------- #
if __name__ == "__main__":
    pass
