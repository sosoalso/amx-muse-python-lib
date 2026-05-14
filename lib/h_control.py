# 마지막 수정일 : 20260507
import json


class HControlDebugFlags:
    debug = False


def hc_get(dv, path, f):
    # 경로와 포맷을 JSON 형식으로 구성하여 서버에 전송
    send_json = {"path": path, "format": f}
    send = json.dumps(send_json)
    send = "get " + send + "\n"
    dv.send(send)


def hc_set(dv, path, f, v):
    # 경로, 포맷, 값을 JSON 형식으로 구성하여 서버에 전송
    send_json = {"path": path, "format": f, "value": v}
    send = json.dumps(send_json)
    send = "set " + send + "\n"
    dv.send(send)


def hc_subscribe(dv, path, f):
    # 구독 요청을 JSON 형식으로 구성하여 서버에 전송
    send_json = {"path": path, "format": f}
    send = json.dumps(send_json)
    send = "subscribe " + send + "\n"
    dv.send(send)


def parse_hc_response(evt):
    try:
        # 이벤트 데이터를 byte에서 문자열로 디코딩
        datas = evt.arguments["data"].value.decode()
        # 여러 응답이 개행으로 구분되어 있을 수 있으므로 줄 단위로 파싱
        for data in datas.split("\n"):
            # 첫 공백을 기준으로 명령어와 JSON 데이터 분리
            cmd, d = data.split(" ", 1)
            # 지원하는 응답 타입 확인
            if cmd in ("@get", "@set", "@subscribe", "publish", "@unsubscribe"):
                json_data = json.loads(d)
                if HControlDebugFlags.debug:
                    print(f"(DEBUG) - hcontrol : parse_hc_response() : {json_data=}")
                return json_data
    except Exception as e:
        print(f"(ERROR) - hcontrol : parse_hc_response() {e=}")
