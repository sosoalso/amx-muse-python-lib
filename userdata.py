# ---------------------------------------------------------------------------- #
import json
import os


# ---------------------------------------------------------------------------- #
class UserData:
    def __init__(self, filename="user_data.json"):
        self.filename = filename
        self.init()

    def init(self):
        try:
            if not os.path.exists(self.filename):
                print(f"{__name__} File not found, creating new file.")
                self.data = {}
                self.save_file()
            else:
                print(f"{__name__} Loading data from file.")
                self.load_file()
        except Exception as e:
            print(f"Error loading data from file: {e}")

    def load_file(self):
        with open(self.filename, "r") as file:
            self.data = json.load(file)

    def save_file(self):
        try:
            with open(self.filename, "w", encoding="utf-8") as output_file:
                json.dump(self.data, output_file, indent=2)
            return True
        except Exception as error:
            print(f"Error saving data: {error}")
            return False

    def set_value(self, key, value):
        try:
            self.data[key] = value
            print(f"Setting value: {self.data}")
            saved = self.save_file()
            return saved
        except Exception as e:
            print(f"Error in set_value: {e}")
            return False

    def get_value(self, key):
        try:
            return self.data.get(key)
        except Exception as e:
            print(f"Error in get_value: {e}")
            return None

    def get_list_item_by_idx(self, list_name, idx):
        try:
            if list_name in self.data and isinstance(self.data[list_name], list):
                return self.data[list_name][idx]
            return None
        except Exception as e:
            print(f"Error in get_list_item_by_idx: {e}")
            return None

    def find_in_list_by_key(self, list_name, search_key, search_value):
        try:
            return next((item for item in self.data[list_name] if item[search_key] == search_value), None)
        except Exception as e:
            print(f"Error in find_in_list_by_key: {e}")
            return None

    def update_list_item(self, list_name, search_key, search_value, update_key, update_value):
        try:
            item = self.find_in_list_by_key(list_name, search_key, search_value)
            if item:
                item[update_key] = update_value
                return self.save_file()
            return False
        except Exception as e:
            print(f"Error in update_list_item: {e}")
            return False

    def add_item_to_list(self, list_name, item):
        try:
            if list_name not in self.data:
                self.data[list_name] = []
            if not isinstance(self.data[list_name], list):
                self.data[list_name] = [self.data[list_name]]
            self.data[list_name].append(item)
            return self.save_file()
        except Exception as e:
            print(f"Error in add_item_to_list: {e}")
            return False

    def remove_item_from_list(self, list_name, item_to_remove):
        try:
            if list_name in self.data and isinstance(self.data[list_name], list):
                self.data[list_name].remove(item_to_remove)
                return self.save_file()
            return False
        except Exception as e:
            print(f"Error in remove_item_from_list: {e}")
            return False


# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
