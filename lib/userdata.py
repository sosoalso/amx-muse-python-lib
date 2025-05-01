# ---------------------------------------------------------------------------- #
import json
import os

from lib.lib_yeoul import uni_log_debug, uni_log_error


# ---------------------------------------------------------------------------- #
def handle_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            uni_log_error(f"UserData 에러: {e}")
            return None

    return wrapper


# ---------------------------------------------------------------------------- #
class UserData:
    def __init__(self, filename="user_data.json", foldername=None):
        self.filename = filename
        self.foldername = foldername
        self.filepath = self.get_file_path()
        self.data = None
        self.init()

    @handle_exception
    def get_file_path(self):
        return f"{self.foldername}/" + self.filename if self.foldername is not None else self.filename

    @handle_exception
    def init(self):
        if self.foldername:
            if not os.path.exists(self.foldername):
                os.makedirs(self.foldername)
        if not os.path.exists(self.filepath):
            uni_log_debug(f"init() :: 파일 {self.filepath} 없음, 새 파일 생성")
            self.data = {}
            self.save_file()
        else:
            uni_log_debug(f"init() :: 파일 {self.filepath} 불러오기")
            self.load_file()

    @handle_exception
    def load_file(self):
        with open(self.filepath, "r", encoding="utf-8") as file:
            self.data = json.load(file)

    @handle_exception
    def save_file(self):
        with open(self.filepath, "w", encoding="utf-8") as output_file:
            json.dump(self.data, output_file, indent=2)

    @handle_exception
    def set_value(self, key, value):
        self.data[key] = value
        uni_log_debug(f"set_value() {key=} {value=}")
        self.save_file()

    @handle_exception
    def get_value(self, key):
        return self.data.get(key)

    @handle_exception
    def delete_value(self, key):
        if key in self.data:
            del self.data[key]
            uni_log_debug(f"delete_value() {key=} 삭제")
            self.save_file()
        else:
            uni_log_debug(f"delete_value() {key=} 없음")


# 간소화 버전
class Var:
    @classmethod
    def as_dict(cls):
        return {
            attr: getattr(cls, attr)
            for attr in dir(cls)
            if not attr.startswith("_") and not callable(getattr(cls, attr))
        }

    @classmethod
    def save_to_json(cls, filepath):
        with open(filepath, "w", encoding="UTF-8") as f:
            json.dump(cls.as_dict(), f, ensure_ascii=False, indent=4)

    @classmethod
    def from_dict(cls, data):
        # 저장된 키가 클래스에 존재하면 속성값을 재할당
        for key, value in data.items():
            if hasattr(cls, key):
                setattr(cls, key, value)
            else:
                uni_log_debug(f"{cls.__name__} 에서 키 {key} 를 찾을 수 없음.")

    @classmethod
    def load_from_json(cls, filepath):
        with open(filepath, "r", encoding="UTF-8") as f:
            data = json.load(f)
        cls.from_dict(data)


# ---------------------------------------------------------------------------- #
