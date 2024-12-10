import json
import os
import unittest

from camtrackpreset import CamtrackPreset


class TestCamtrackPreset(unittest.TestCase):
    def setUp(self):
        self.test_filename = "test_camtrack_preset.json"
        self.max_preset_index = 40
        self.preset = CamtrackPreset(filename=self.test_filename, max_preset_index=self.max_preset_index)

    def tearDown(self):
        if os.path.isfile(self.test_filename):
            os.remove(self.test_filename)

    def test_initialization_creates_file(self):
        self.assertTrue(os.path.isfile(self.test_filename))

    def test_initialization_creates_correct_presets(self):
        with open(self.test_filename, "r") as f:
            data = json.load(f)
        self.assertEqual(len(data["presets"]), self.max_preset_index)
        for idx, preset in enumerate(data["presets"]):
            self.assertEqual(preset["index"], idx + 1)
            self.assertEqual(preset["camera"], 0)
            self.assertEqual(preset["preset"], 0)

    def test_get_preset(self):
        self.assertEqual(self.preset.get_preset(1), {"index": 1, "camera": 0, "preset": 0})

    def test_set_preset(self):
        self.preset.set_preset(1, 1, 1)
        self.assertEqual(self.preset.get_preset(1), {"index": 1, "camera": 1, "preset": 1})


if __name__ == "__main__":
    unittest.main()
