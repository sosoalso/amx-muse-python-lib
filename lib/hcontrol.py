import json

from mojo import context

# ---------------------------------------------------------------------------- #
VERSION = "2026.02.10"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #


def hc_get(dv, path, f):
    send_json = {"path": path, "format": f}
    send = json.dumps(send_json)
    send = "get " + send + "\n"
    dv.send(send)


def hc_set(dv, path, f, v):
    send_json = {"path": path, "format": f, "value": v}
    send = json.dumps(send_json)
    send = "set " + send + "\n"
    dv.send(send)


def hc_subscribe(dv, path, f):
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
                context.log.debug(f"parse_hc_response() {json_data=}")
    except Exception as e:
        context.log.error(f"parse_hc_response() 에러: {e}")
