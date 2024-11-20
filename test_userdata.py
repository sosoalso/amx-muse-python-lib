# from camtrackpreset import CamtrackPreset

# camtrack_preset = CamtrackPreset()
# print(camtrack_preset.get_preset(1))
# camtrack_preset.set_preset(0, 2, 4)
# print(camtrack_preset.get_preset(40))

from userdata import UserData

user_data = UserData()

user_data.set("name", "Alice")
user_data.set("age", 25)

print(user_data.get_item("name"))
print(user_data.get_item("age"))
