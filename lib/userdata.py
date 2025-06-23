# ---------------------------------------------------------------------------- #
import json
import os

from mojo import context

# ---------------------------------------------------------------------------- #
VERSION = "2025.06.23"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class Userdata:
    def __init__(
        self,
        filename="user_data.json",
        foldername="userdata",
        default_value=None,
    ):
        self.filename = filename
        self.foldername = foldername
        self.default_value = default_value
        self.filepath = self.get_file_path()
        self.data = {} if default_value is None else default_value
        self.init()

    def get_file_path(self):
        return f"{self.foldername}/{self.filename}" if self.foldername is not None else self.filename

    def init(self):
        if self.foldername:
            if not os.path.exists(self.foldername):
                os.makedirs(self.foldername)
        if not os.path.exists(self.filepath):
            context.log.debug(f"init() : 파일 {self.filepath} 없음. 새 파일 생성")
            self.data = self.default_value
            self.save_file()
        else:
            context.log.debug(f"init() : 파일 {self.filepath} 불러오기")
            self.load_file()

    def load_file(self):
        with open(self.filepath, "r", encoding="utf-8") as file:
            self.data = json.load(file)
        context.log.debug(f"load_file() {self.filepath} 로드 완료")

    def save_file(self):
        with open(self.filepath, "w", encoding="UTF-8") as f:
            json.dump(self.data, f, ensure_ascii=False, indent=2)
        context.log.debug(f"save_file() {self.filepath} 저장 완료")

    def set_value(self, key, value):
        if self.data is None:
            self.data = {}
        self.data[key] = value
        context.log.debug(f"set_value() {key=} {value=}")
        self.save_file()

    def get_value(self, key, default=None):
        if self.data:
            if key in self.data:
                context.log.debug(f"get_value() 존재하는 키:{key} 값:{self.data[key]}")
                return self.data[key]
            context.log.debug(f"get_value() 키 {key} 없음. 기본값 생성 값 반환:{default}")
            self.set_value(key, default)
        return default

    def delete_value(self, key):
        if self.data is not None:
            if key in self.data:
                del self.data[key]
                context.log.debug(f"delete_value() 키 {key} 삭제")
                self.save_file()
            else:
                context.log.debug(f"delete_value() 키 {key} 없음")


# # 간소화 버전
# class Vars:
#     @classmethod
#     def as_dict(cls):
#         return {
#             attr: getattr(cls, attr)
#             for attr in dir(cls)
#             if not attr.startswith("_") and not callable(getattr(cls, attr))
#         }
#     @classmethod
#     def save_to_json(cls, filepath):
#         with open(filepath, "w", encoding="UTF-8") as f:
#             json.dump(cls.as_dict(), f, ensure_ascii=False, indent=2)
#     @classmethod
#     def from_dict(cls, data):
#         # 저장된 키가 클래스에 존재하면 속성값을 재할당
#         for key, value in data.items():
#             if hasattr(cls, key):
#                 setattr(cls, key, value)
#             else:
#                 context.log.debug(f"{cls.__name__} 에서 키 {key} 를 찾을 수 없음.")
#     @classmethod
#     def load_from_json(cls, filepath):
#         with open(filepath, "r", encoding="UTF-8") as f:
#             data = json.load(f)
#         cls.from_dict(data)
