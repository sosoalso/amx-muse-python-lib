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
            print(f"init() :: File {self.filepath} not found, creating new file")
            self.data = {}
            self.save_file()
        else:
            print(f"init() :: File {self.filepath} Loading")
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
        print(f"set_value() :: {key=} {value=}")
        self.save_file()

    @handle_exception
    def get_value(self, key):
        return self.data.get(key)


# ---------------------------------------------------------------------------- #
