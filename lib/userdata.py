# ---------------------------------------------------------------------------- #
import json
import os

# ---------------------------------------------------------------------------- #
VERSION = "2026.04.24"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
def handle_exception(func):
    # 함수 실행 중 예외 발생 시 로깅하고 None 반환하는 데코레이터
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"timeline (ERROR) -- {func.__name__=} {e=}")
            return None

    return wrapper


# ---------------------------------------------------------------------------- #
class Userdata:
    def __init__(self, filename="user_data.json", foldername=None, default_value=None):
        self.filename = filename
        self.foldername = foldername
        self.filepath = self.get_file_path()
        self.data = {}
        self.debug = False
        self.init(default_value=default_value)

    def log_debug(self, message):
        if self.debug:
            print(f"DEBUG -- {message}")

    @handle_exception
    def get_file_path(self):
        # foldername이 있으면 경로에 포함, 없으면 파일명만 반환
        return f"{self.foldername}/" + self.filename if self.foldername is not None else self.filename

    @handle_exception
    def init(self, default_value=None):
        # 폴더가 없으면 생성
        if self.foldername:
            if not os.path.exists(self.foldername):
                os.makedirs(self.foldername)
        # 파일이 없으면 새로 생성, 있으면 로드
        if not os.path.exists(self.filepath):
            self.log_debug(f"init() -- file {self.filepath} not found, creating new file")
            self.data = default_value if default_value is not None else {}
            self.save_file()
        else:
            self.log_debug(f"init() -- load file {self.filepath}")
            self.load_file()

    @handle_exception
    def load_file(self):
        # JSON 파일을 읽어 self.data에 로드
        with open(self.filepath, "r", encoding="utf-8") as file:
            self.data = json.load(file)

    @handle_exception
    def save_file(self):
        # self.data를 JSON 파일로 저장
        with open(self.filepath, "w", encoding="utf-8") as output_file:
            json.dump(self.data, output_file, indent=2)

    @handle_exception
    def set_value(self, key, value):
        self.data[key] = value
        self.log_debug(f"set_value() {key=} {value=}")
        self.save_file()

    @handle_exception
    def get_value(self, key, default):
        # 키가 없거나 값이 falsy이면 default 반환
        return self.data.get(key) or default

    @handle_exception
    def delete_value(self, key):
        # 키가 존재하면 삭제하고 저장, 없으면 로그만 출력
        if key in self.data:
            del self.data[key]
            self.log_debug(f"delete_value() {key=} deleted")
            self.save_file()
        else:
            self.log_debug(f"delete_value() {key=} not found")


# 간소화 버전: 클래스 변수를 JSON으로 관리
class Var:
    @classmethod
    def as_dict(cls):
        # 클래스의 모든 공개 속성(메서드 제외)을 딕셔너리로 반환
        return {attr: getattr(cls, attr) for attr in dir(cls) if not attr.startswith("_") and not callable(getattr(cls, attr))}

    @classmethod
    def save_to_json(cls, filepath):
        # 클래스 속성을 JSON 파일로 저장
        with open(filepath, "w", encoding="UTF-8") as f:
            json.dump(cls.as_dict(), f, ensure_ascii=False, indent=4)

    @classmethod
    def from_dict(cls, data):
        # 딕셔너리 데이터로부터 클래스 속성 업데이트 (기존 속성만)
        for key, value in data.items():
            if hasattr(cls, key):
                setattr(cls, key, value)
            else:
                print(f"Key {key} not found in {cls.__name__}.")

    @classmethod
    def load_from_json(cls, filepath):
        # JSON 파일을 읽어 클래스 속성으로 로드
        with open(filepath, "r", encoding="UTF-8") as f:
            data = json.load(f)
        cls.from_dict(data)


# ---------------------------------------------------------------------------- #
