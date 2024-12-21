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
class CamtrackPreset:
    def __init__(self, filename="camtrack_preset.json", max_preset_index=40):
        self.filename = filename
        self.max_preset_index = max_preset_index
        self.presets = {}
        self.init()

    @simple_exception_handler()
    def init(self):
        try:
            if not os.path.exists(self.filename):
                self.presets = self.make_dummy_presets()
                self.save_file()
            else:
                self.load_file()
        except Exception as e:
            # print(f"Error loading presets from file: {e}")
            pass

    @simple_exception_handler()
    def make_dummy_presets(self):
        return {
            "presets": [
                {"index": preset_index + 1, "camera": 0, "preset": 0} for preset_index in range(self.max_preset_index)
            ]
        }

    @simple_exception_handler()
    def load_file(self):
        with open(self.filename, "r") as file:
            self.presets = json.load(file)

    @simple_exception_handler()
    def save_file(self):
        with open(self.filename, "w", encoding="utf-8") as output_file:
            json.dump(self.presets, output_file, indent=2)
        return True

    @simple_exception_handler()
    def sort_presets(self):
        self.presets["presets"].sort(key=lambda x: x["index"])

    @simple_exception_handler()
    def get_preset(self, index):
        return next((preset for preset in self.presets["presets"] if preset["index"] == index), None)

    @simple_exception_handler()
    def set_preset(self, preset_index, cam_no, preset_no):
        target_preset = self.get_preset(preset_index)
        if target_preset:
            target_preset["camera"] = cam_no
            target_preset["preset"] = preset_no
            self.sort_presets()
            self.save_file()


# ---------------------------------------------------------------------------- #
