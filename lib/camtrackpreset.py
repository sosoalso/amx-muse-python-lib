from lib.lib_yeoul import handle_exception
from lib.userdata import Userdata

# ---------------------------------------------------------------------------- #
VERSION = "2025.06.27"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class CamtrackPreset:
    """
    CamtrackPreset 클래스는 카메라 트랙 프리셋을 저장하고 로드하는 기능을 제공합니다.
    Attributes:
        filename (str): 프리셋 데이터를 저장할 파일 이름. 기본값은 "camtrack_preset.json"입니다.
        max_preset_index (int): 최대 프리셋 인덱스. 기본값은 40입니다.
        data (Userdata): 파일 저장 및 로드에 사용되는 Userdata 객체.
        presets (list): 현재 로드된 프리셋 목록.
    Methods:
        __init__(filename="camtrack_preset.json", max_preset_index=40):
            CamtrackPreset 객체를 초기화합니다.
            파일 이름과 최대 프리셋 인덱스를 설정합니다.
        init():
            프리셋 데이터를 초기화합니다.
            저장된 데이터가 없으면 더미 프리셋을 생성합니다.
        make_dummy_presets():
            더미 프리셋 목록을 생성합니다.
            Returns:
                list: 기본값으로 설정된 프리셋 목록.
        sort_preset():
            프리셋 목록을 인덱스 기준으로 정렬합니다.
        get_preset(index):
            특정 인덱스에 해당하는 프리셋을 반환합니다.
            Args:
                index (int): 검색할 프리셋의 인덱스.
            Returns:
                dict or None: 해당 인덱스의 프리셋. 없으면 None.
                dict 구조:
                    - index (int): 프리셋의 인덱스.
                    - camera (int): 카메라 번호.
                    - preset (int): 프리셋 번호.
        set_preset(preset_index, cam_no, preset_no):
            특정 프리셋의 카메라 번호와 프리셋 번호를 설정합니다.
            Args:
                preset_index (int): 설정할 프리셋의 인덱스.
                cam_no (int): 설정할 카메라 번호.
                preset_no (int): 설정할 프리셋 번호.
        save_preset():
            현재 프리셋 데이터를 파일에 저장합니다.
    """

    def __init__(self, filename="camtrack_preset.json", max_preset_index=40):
        self.filename = filename
        self.max_preset_index = max_preset_index
        self.data = Userdata(filename=self.filename)
        self.presets = []
        self.init()

    @handle_exception
    def init(self):
        self.presets = self.data.get_value("presets", self.make_dummy_presets())

    @handle_exception
    def make_dummy_presets(self):
        return [
            {"index": preset_index + 1, "camera": 0, "preset": preset_index + 1}
            for preset_index in range(self.max_preset_index)
        ]

    @handle_exception
    def sort_preset(self):
        self.presets = sorted(self.presets or [], key=lambda x: x["index"])

    @handle_exception
    def get_preset(self, index):
        return next((preset for preset in self.presets or {} if preset["index"] == index), {})

    @handle_exception
    def set_preset(self, preset_index, cam_no, preset_no):
        target_preset = self.get_preset(preset_index)
        if target_preset:
            target_preset["camera"] = cam_no
            target_preset["preset"] = preset_no
            self.sort_preset()
            self.save_preset()

    @handle_exception
    def save_preset(self):
        self.data.set_value("presets", self.presets)
