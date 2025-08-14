import json

from mojo import context

OMNI = context.devices.get("ONNI")
# ---------------------------------------------------------------------------- #
LOGIC_SOURCE_NAME_LIST = [
    "LogicSource1",
    "LogicSource2",
    "LogicSource3",
]
LOGIC_SOURCE_LIST = [OMNI.Logic[obj_name] for obj_name in LOGIC_SOURCE_NAME_LIST]


# ---------------------------------------------------------------------------- #
class LastRecallPreset:
    value = 0


# ---------------------------------------------------------------------------- #
def handle_logic_source(evt, idx):
    if evt.value:
        if idx == 1:
            print("handle preset 1")
        elif idx == 2:
            print("handle preset 2")
        elif idx == 3:
            print("handle off preset")
        else:
            return
        LastRecallPreset.value = idx


# get { "path" : "/Audio/P4/Master Gain", "format" : "string" }
# set { "path" : "/Audio/P4/Master Gain", "format" : "string", "value" : "-26.78 dB" }
# subscribe { "path" : "/Audio/P4/Master Gain", "format" : "string" }
# publish { "path" : "/Audio/P4/Master Gain", "format" : "string" }
# unsubscribe { "path" : "/Audio/P4/Master Gain", "format" : "string" }


def req_hc_get(dv, path, f):
    send_json = {"path": path, "format": f}
    send = json.dumps(send_json)
    send = "get " + send + "\n"
    dv.send(send)


def req_hc_set(dv, path, f, v):
    send_json = {"path": path, "format": f, "value": v}
    send = json.dumps(send_json)
    send = "set " + send + "\n"
    dv.send(send)


def req_hc_subscribe(dv, path, f):
    send_json = {"path": path, "format": f}
    send = json.dumps(send_json)
    send = "subscribe " + send + "\n"
    dv.send(send)


def parse_hc_response(evt):
    try:
        datas = evt.arguments["data"].value.decode
        for data in datas.split("\n"):
            cmd, d = data.split(" ", 1)
            if cmd in ("@get", "@set", "@subscribe", "@publish", "@unsubscribe"):
                json_data = json.loads(d)
                print(json_data)
    except Exception as e:
        print(f"invalid response: {e}")


# ---------------------------------------------------------------------------- #
if __name__ == "__main__":
    for i, obj in enumerate(LOGIC_SOURCE_LIST):
        obj.watch(lambda evt, idx=i: handle_logic_source(evt, idx))
    context.run(globals())
