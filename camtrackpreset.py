# ---------------------------------------------------------------------------- #
import json
import os


# ---------------------------------------------------------------------------- #
class CamtrackPreset:
    def __init__(self, filename="camtrack_preset.json", max_preset_index=40):
        self.filename = filename
        self.max_preset_index = max_preset_index
        self.presets = {}
        self.init()

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

    def make_dummy_presets(self):
        return {"presets": [{"index": idx + 1, "camera": 0, "preset": 0} for idx in range(self.max_preset_index)]}

    def load_file(self):
        with open(self.filename, "r") as file:
            self.presets = json.load(file)

    def save_file(self):
        try:
            with open(self.filename, "w", encoding="utf-8") as output_file:
                json.dump(self.presets, output_file, indent=2)
            return True
        except Exception as error:
            # print(f"Error saving data: {error}")
            return False

    def sort_presets(self):
        try:
            self.presets["presets"].sort(key=lambda x: x["index"])
        except Exception as e:
            # print(f"Error sorting presets: {e}")
            pass

    def get_preset(self, index):
        # print(f"get_preset: {index}")
        try:
            return next((preset for preset in self.presets["presets"] if preset["index"] == index), None)
        except Exception as e:
            # print(f"Error get_preset: {e}")
            pass

    def set_preset(self, idx, cam_no, preset_no):
        # print(f"set_preset: {idx}, {cam_no}, {preset_no}")
        try:
            target_preset = self.get_preset(idx)
            if target_preset:
                target_preset["camera"] = cam_no
                target_preset["preset"] = preset_no
                self.sort_presets()
                self.save_file()
            else:
                # print(f"Preset with index {idx} not found")
                pass
        except Exception as e:
            # print(f"Error in set_preset: {e}")
            pass


# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
