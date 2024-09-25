# ---------------------------------------------------------------------------- #
from lib_yeoul import err_with_name, print_with_name
from simpleconfigmanager import SimpleConfigManager  # type: ignore


# ---------------------------------------------------------------------------- #
class CamtrackPreset:
    def __init__(self, filename, max_preset_idx=10):
        self.config = SimpleConfigManager(filename)
        self.max_preset_idx = max_preset_idx
        self.presets = self.make_dummy_presets()
        self.load_preset_list()
        self.save_preset_list()

    def make_dummy_presets(self):
        return [{"camera": 0, "preset": 0} for _ in range(self.max_preset_idx)]

    def load_preset_list(self):
        self.config.load_config()
        try:
            for section in self.config.get_sections():
                if not section:
                    return
                index = int(section.split("_")[-1])
                idx = index - 1
                if 0 <= idx < self.max_preset_idx:
                    self.presets[idx] = {key: int(value) for key, value in self.config.get_items(section)}
                    print_with_name(f"Loaded preset {idx}: {self.presets[idx]}")
        except Exception as e:
            err_with_name(IndexError, f"Error loading presets from file: {e}")

    def save_preset_list(self):
        for idx, preset in enumerate(self.presets):
            index = idx + 1
            section = f"preset_{index}"
            self.config.remove_section(section)
            self.config.add_section(section)
            for key, value in preset.items():
                self.config.set_option(section, key, str(value))

    def get_preset(self, idx):
        self.config.load_config()
        if 0 <= idx < self.max_preset_idx:
            return self.presets[idx]
        else:
            err_with_name(IndexError, "Preset index out of range.")

    def set_preset(self, idx, cam_no, preset_no):
        if 0 <= idx < self.max_preset_idx:
            self.presets[idx] = {"camera": cam_no, "preset": preset_no}
            self.save_preset_list()
        else:
            err_with_name(IndexError, "Preset index out of range.")


# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# from CamtrackPreset import CamtrackPreset

# my_camtrack_preset = CamtrackPreset("camtrack.ini", 5)
# my_camtrack_preset.set_preset(0, 1, 1)
# print(my_camtrack_preset.get_preset(0))
# my_camtrack_preset.set_preset(1, 2, 2)
# print(my_camtrack_preset.get_preset(1))
# my_camtrack_preset.set_preset(2, 3, 3)
# print(my_camtrack_preset.get_preset(2))
