from typing import Any

from lib.database import Database

# ---------------------------------------------------------------------------- #
VERSION = "2025.07.05"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class Userdata(Database):

    def __init__(self, db_path="userdata.db"):
        super().__init__(db_path=db_path)
        self.data = {}  # 여기에 db에서 불러온 키에 대한 값들을 저장할 거임

    def set_value(self, key, value):
        k = str(key)
        self.data[k] = value
        self.save(k, self.data[k])

    def get_value(self, key, default=None) -> dict:
        k = str(key)
        self.data[k] = self.load(k, default if default is not None else {})
        return self.data.get(k, default if default is not None else {})

    def delete_value(self, key):
        k = str(key)
        if k in self.data:
            del self.data[k]
            self.save(k, self.data)
