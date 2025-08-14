from mojo import context

from lib.database import Database

# ---------------------------------------------------------------------------- #
VERSION = "2025.08.14"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class Userdata(Database):

    def __init__(self, db_path="userdata.db", debug=False):
        super().__init__(db_path=db_path)
        self.data = {}  # 여기에 db에서 불러온 키에 대한 값들을 저장할 거임
        self.debug = debug
        if self.debug:
            context.log.debug(f"Userdata - __init__() {self.db_path=}")

    def set_value(self, key, value):
        k = str(key)
        self.data[k] = value
        if self.debug:
            context.log.debug(f"Userdata - set_value() {self.db_path=} {k}:{self.data[k]}")
        self.save(k, self.data[k])

    def get_value(self, key, default=None):
        k = str(key)
        self.data[k] = self.load(k, default if default is not None else {})
        if self.debug:
            context.log.debug(f"Userdata - get_value() {self.db_path=} {k}:{self.data[k]}")
        return self.data.get(k, default if default is not None else {})

    def delete_value(self, key):
        k = str(key)
        if k in self.data:
            del self.data[k]
            if self.debug:
                context.log.debug(f"Userdata - delete_value() {self.db_path=} {k=}")
            self.save(k, self.data)
