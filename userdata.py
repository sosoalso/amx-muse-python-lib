# ---------------------------------------------------------------------------- #
import json
import os


# ---------------------------------------------------------------------------- #
def simple_exception_handler(*exceptions):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                print(f"Exception occurred in {func.__name__}: {e}")
                return None
            except Exception as e:
                print(f"Exception occurred in {func.__name__}: {e}")
                return None

        return wrapper

    return decorator


# ---------------------------------------------------------------------------- #
class UserData:
    def __init__(self, filename="user_data.json", foldername=None):
        self.filename = filename
        self.foldername = foldername
        self.filepath = self.get_file_path()
        self.data = None
        self.init()

    @simple_exception_handler
    def get_file_path(self):
        return f"{self.foldername}/" + self.filename if self.foldername is not None else self.filename

    @simple_exception_handler
    def init(self):
        try:
            if self.foldername:
                try:
                    if not os.path.exists(self.foldername):
                        os.makedirs(self.foldername)
                except Exception as e:
                    print(f"init() Error creating folder: {e}")
            if not os.path.exists(self.filepath):
                print(f"init() :: File {self.filepath} not found, creating new file")
                self.data = {}
                self.save_file()
            else:
                print(f"init() :: File {self.filepath} Loading")
                self.load_file()
        except Exception as e:
            print(f"init() Error :: {e}")

    @simple_exception_handler
    def load_file(self):
        with open(self.filepath, "r") as file:
            self.data = json.load(file)

    @simple_exception_handler
    def save_file(self):
        with open(self.filepath, "w", encoding="utf-8") as output_file:
            json.dump(self.data, output_file, indent=2)

    @simple_exception_handler
    def set_value(self, key, value):
        self.data[key] = value
        print(f"set_value() :: {key=} {value=}")
        self.save_file()

    @simple_exception_handler
    def get_value(self, key):
        return self.data.get(key)


# ---------------------------------------------------------------------------- #
