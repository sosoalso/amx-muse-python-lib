# 마지막 수정일 : 20260627
import json
import os
import threading
import time

from lib.utility import CommonLogger

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
_SRC_DIR = os.path.dirname(_LIB_DIR)
_BASE_DIR = os.path.dirname(_SRC_DIR)  # src/ → 프로젝트루트
_PROGRAM_NAME = os.path.basename(_SRC_DIR)  # 프로젝트루트 폴더명
_DEFAULT_FOLDER = f"{_PROGRAM_NAME}_userdata"  # e.g. "(2026_06)_HSW_KHNP_CRI_userdata"


class Userdata(CommonLogger):
    def __init__(self, filename="userdata.json", foldername=_DEFAULT_FOLDER, default_value=None):
        self.filename = filename if filename.endswith(".json") else filename + ".json"
        self.foldername = foldername
        self.filepath = self.get_file_path()
        self.data = {}
        self._lock = threading.RLock()
        self.init(default_value)

    def get_file_path(self):
        folder = os.path.join(_BASE_DIR, self.foldername) if self.foldername else _BASE_DIR
        return os.path.join(folder, self.filename)

    def init(self, default_value=None):
        # 폴더가 없으면 생성
        folder = os.path.dirname(self.filepath)
        if not os.path.exists(folder):
            os.makedirs(folder)
        # 파일이 없으면 새로 생성, 있으면 로드
        if not os.path.exists(self.filepath):
            self.log_debug(f"init() : file {self.filepath} not found, creating new file")
            self.data = default_value if default_value is not None else {}
            self.save_file()
        else:
            self.log_debug(f"init() : load file {self.filepath}")
            loaded = self.load_file()
            if loaded is None:
                self._backup_broken_file()
                self.data = default_value if default_value is not None else {}
                self.save_file()

    def load_file(self):
        # JSON 파일을 읽어 self.data에 로드
        try:
            with self._lock:
                with open(self.filepath, "r", encoding="utf-8") as file:
                    self.data = json.load(file)
            return True
        except json.JSONDecodeError as e:
            self.log_error(f"load_file() : invalid json {self.filepath=} {e=}")
            return None
        except OSError as e:
            self.log_error(f"load_file() : failed to load {self.filepath=} {e=}")
            return None

    def _backup_broken_file(self):
        if not os.path.exists(self.filepath):
            return
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        backup_path = f"{self.filepath}.broken_{timestamp}"
        os.replace(self.filepath, backup_path)
        self.log_error(f"_backup_broken_file() : moved broken file to {backup_path}")

    def save_file(self):
        # self.data를 JSON 파일로 저장
        try:
            with self._lock:
                with open(self.filepath, "w", encoding="utf-8") as output_file:
                    json.dump(self.data, output_file, indent=2)
        except OSError as e:
            self.log_error(f"save_file() : failed to save {self.filepath=} {e=}")

    def set_value(self, key, value):
        # 주의: value가 dict이면 JSON 직렬화 시 int 키가 str로 변환됨. 읽을 때도 str 키로 접근할 것.
        key = str(key)
        with self._lock:
            self.data[key] = value
        self.log_debug(f"set_value() : {key=} {value=}")
        self.save_file()

    def get_value(self, key, default):
        key = str(key)
        with self._lock:
            return self.data[key] if key in self.data else default

    def delete_value(self, key):
        key = str(key)
        # 키가 존재하면 삭제하고 저장, 없으면 로그만 출력
        with self._lock:
            found = key in self.data
            if found:
                del self.data[key]
        if found:
            self.log_debug(f"delete_value() : deleted {key=}")
            self.save_file()
        else:
            self.log_debug(f"delete_value() : not found {key=}")


# 간소화 버전: 클래스 변수를 JSON으로 관리
class Var:
    @classmethod
    def as_dict(cls):
        # 클래스의 모든 공개 속성(메서드 제외)을 딕셔너리로 반환
        return {attr: getattr(cls, attr) for attr in dir(cls) if not attr.startswith("_") and not callable(getattr(cls, attr))}

    @classmethod
    def save_to_json(cls, filepath):
        # 클래스 속성을 JSON 파일로 저장
        try:
            with open(filepath, "w", encoding="UTF-8") as f:
                json.dump(cls.as_dict(), f, ensure_ascii=False, indent=2)
        except OSError as e:
            print(f"(ERROR) - userdata : Var.save_to_json() failed {filepath=} {e=}")

    @classmethod
    def from_dict(cls, data):
        # 딕셔너리 데이터로부터 클래스 속성 업데이트 (기존 속성만)
        for key, value in data.items():
            if hasattr(cls, key):
                setattr(cls, key, value)
            else:
                print(f"( WARN) - userdata : Key {key} not found in {cls.__name__}.")

    @classmethod
    def load_from_json(cls, filepath):
        # JSON 파일을 읽어 클래스 속성으로 로드
        try:
            with open(filepath, "r", encoding="UTF-8") as f:
                data = json.load(f)
            cls.from_dict(data)
        except OSError as e:
            print(f"(ERROR) - userdata : Var.load_from_json() failed {filepath=} {e=}")
        except json.JSONDecodeError as e:
            print(f"(ERROR) - userdata : Var.load_from_json() invalid json {filepath=} {e=}")
