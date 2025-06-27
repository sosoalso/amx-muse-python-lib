import json
import re

from mojo import context

from lib.eventmanager import EventManager


# ---------------------------------------------------------------------------- #
# SECTION : 제어 장비
# ---------------------------------------------------------------------------- #
class Videohub(EventManager):
    def __init__(self, dv, name="videohub"):
        super().__init__("route")
        self.dv = dv
        self.routes = {key: 0 for key in range(1, 20 + 1)}
        self.name = name
        self.init()

    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.load_json()

    def send(self, msg):
        self.dv.send(msg.encode())

    def load_json(self):
        try:
            with open(f"{self.name}_routes.json", "r", encoding="UTF-8") as f:
                data = json.load(f)
                for key, value in data.items():
                    if hasattr(self.routes, key):
                        setattr(self.routes, key, value)
        except FileNotFoundError:
            context.log.debug(f"{self.name}_routes.json 로드 에러 : 파일이 없습니다. 새로 생성합니다.")
            self.save_json()

    def save_json(self):
        try:
            with open(f"{self.name}_routes.json", "w", encoding="UTF-8") as f:
                json.dump(self.routes, f, ensure_ascii=False, indent=4)
        except Exception as e:
            context.log.error(f"{self.name}_routes.json 저장 에러 : {e}")

    def parse_response(self, *args):
        try:
            data_text = args[0].arguments["data"].decode("utf-8")
            context.log.debug(data_text)
            parsed_data_text_chunks = data_text.split("\n\n")
            for parsed_data_text in parsed_data_text_chunks:
                splitted_message = parsed_data_text.split("\n")
                if "VIDEO OUTPUT ROUTING:" in splitted_message[0]:
                    for msg in splitted_message[1:]:
                        match = re.search(r"\d+ \d+", msg)
                        if match:
                            line = match.group(0)
                            idx_out, idx_in = map(int, line.split())
                            self.routes[idx_out + 1] = idx_in + 1
                            self.trigger_event("route", idx_in=idx_in, idx_out=idx_out, this=self)
            self.save_json()
        except (AttributeError, KeyError, UnicodeDecodeError, ValueError) as e:
            context.log.error(f"Error decoding data: {e}")
            return

    def set_route(self, idx_in, idx_out):
        self.send(f"VIDEO OUTPUT ROUTING:\n{idx_out} {idx_in}\n\n")
        self.routes[idx_out + 1] = idx_in + 1
        self.trigger_event("route", idx_in=idx_in, idx_out=idx_out, routes=self.routes, this=self)

    def set_routes(self, route_dict):
        route_str = "\n".join(f"{idx_in} {idx_out}" for idx_in, idx_out in route_dict.items())
        self.send(f"VIDEO OUTPUT ROUTING:\n{route_str}\n")
        for idx_in, idx_out in route_dict.items():
            self.trigger_event("route", idx_in=idx_in, idx_out=idx_out, routes=self.routes, this=self)


# videohub_instance = Videohub(VIDEOHUB)  # INFO : 제어 장비 인스턴스
# # ---------------------------------------------------------------------------- #
# # SECTION : TP
# # ---------------------------------------------------------------------------- #
# TP_PORT_VIDEOHUB = 3
# NUM_VIDEOHUB_IN = 20
# NUM_VIDEOHUB_OUT = 20
# NAME_VIDEOHUB_IN = (
#     "카메라 1",
#     "카메라 2",
#     "카메라 3",
#     "카메라 4",
#     "05",
#     "06",
#     "07",
#     "08",
#     "09",
#     "10",
#     "11",
#     "12",
#     "13",
#     "14",
#     "15",
#     "16",
#     "17",
#     "18",
#     "19",  # "비디오 스위쳐\nPGM",
#     "레코더\n출력",
# )
# NAME_VIDEOHUB_OUT = (
#     "프로젝터\n1",
#     "프로젝터\n2",
#     "프로젝터\n3",
#     "04",
#     "조종실\n모니터 좌",
#     "조종실\n모니터 우",
#     "07",
#     "08",
#     "09",
#     "10",
#     "11",
#     "12",
#     "13",
#     "14",
#     "15",
#     "16",
#     "17",
#     "18",
#     "19",  # "비디오 스위쳐\n입력",
#     "레코더\n입력",
# )
# class var:
#     sel_in = [0] * len(TP_LIST)
# def refresh_input_button(idx_tp):
#     for idx_in in range(1, NUM_VIDEOHUB_IN + 1):
#         tp_set_button(TP_LIST[idx_tp], TP_PORT_VIDEOHUB, idx_in + 100, var.sel_in[idx_tp] == idx_in)
#         tp_set_button(
#             TP_LIST[idx_tp],
#             TP_PORT_VIDEOHUB,
#             idx_in + 200,
#             var.sel_in[idx_tp] and videohub_instance.routes[idx_in] == var.sel_in[idx_tp],
#         )
# def refresh_output_button(idx_tp):
#     for idx_out in range(1, NUM_VIDEOHUB_OUT + 1):
#         tp_set_button(
#             TP_LIST[idx_tp],
#             TP_PORT_VIDEOHUB,
#             idx_out + 200,
#             var.sel_in[idx_tp] and videohub_instance.routes[idx_out] == var.sel_in[idx_tp],
#         )
# def refresh_input_button_name(idx_tp):
#     for idx_in in range(1, NUM_VIDEOHUB_IN + 1):
#         tp_set_button_text_unicode(TP_LIST[idx_tp], TP_PORT_VIDEOHUB, idx_in + 100, NAME_VIDEOHUB_IN[idx_in - 1])
# def refresh_output_button_name(idx_tp):
#     for idx_out in range(1, NUM_VIDEOHUB_OUT + 1):
#         tp_set_button_text_unicode(TP_LIST[idx_tp], TP_PORT_VIDEOHUB, idx_out + 200, NAME_VIDEOHUB_OUT[idx_out - 1])
# def refresh_output_route_name_all():
#     for idx_out in range(1, NUM_VIDEOHUB_OUT + 1):
#         refresh_output_route_name(idx_out)
# def refresh_output_route_name(idx_out):
#     if 0 < idx_out <= NUM_VIDEOHUB_OUT:
#         if 0 < videohub_instance.routes[idx_out] <= NUM_VIDEOHUB_IN:
#             tp_set_button_text_unicode_ss(
#                 TP_LIST, TP_PORT_VIDEOHUB, idx_out + 300, NAME_VIDEOHUB_IN[videohub_instance.routes[idx_out] - 1]
#             )
#         else:
#             tp_set_button_text_unicode_ss(TP_LIST, TP_PORT_VIDEOHUB, idx_out + 300, "")
# def add_tp_videohub():
#     for idx_tp, dv_tp in enumerate(TP_LIST):
#         # NOTE : 입력 선택 버튼 | ch 101-120
#         for idx_in in range(1, 20 + 1):
#             def set_selected_input(idx_tp=idx_tp, idx_in=idx_in):
#                 var.sel_in[idx_tp] = idx_in
#                 refresh_input_button(idx_tp)
#                 refresh_output_button(idx_tp)
#             input_select_button = ButtonHandler()
#             input_select_button.add_event_handler("push", set_selected_input)
#             tp_add_watcher(dv_tp, TP_PORT_VIDEOHUB, idx_in + 100, input_select_button.handle_event)
#         # NOTE : 출력 버튼 - 라우팅 | ch 201-220
#         for idx_out in range(1, 20 + 1):
#             def set_route(idx_tp=idx_tp, idx_out=idx_out):
#                 if var.sel_in[idx_tp] and idx_out:
#                     videohub_instance.set_route(var.sel_in[idx_tp] - 1, idx_out - 1)
#                     refresh_output_button(idx_tp)
#             output_route_button = ButtonHandler()
#             output_route_button.add_event_handler("push", set_route)
#             tp_add_watcher(dv_tp, TP_PORT_VIDEOHUB, idx_out + 200, output_route_button.handle_event)
#     context.log.info("add_tp_videohub 등록 완료")
# def add_evt_videohub():
#     # NOTE : 매트릭스 이벤트 피드백
#     def refresh_button_on_route_event(**kwargs):
#         for idx_evt, _ in enumerate(TP_LIST):
#             refresh_output_button(idx_evt)
#             refresh_output_route_name(kwargs["idx_out"] + 1)
#     videohub_instance.add_event_handler("route", refresh_button_on_route_event)
#     # NOTE : TP 온라인 피드백
#     for idx_tp, dv_tp in enumerate(TP_LIST):
#         dv_tp.online(lambda evt, idx_tp=idx_tp: refresh_input_button(idx_tp))
#         dv_tp.online(lambda evt, idx_tp=idx_tp: refresh_output_button(idx_tp))
#         dv_tp.online(lambda evt, idx_tp=idx_tp: refresh_input_button_name(idx_tp))
#         dv_tp.online(lambda evt, idx_tp=idx_tp: refresh_output_button_name(idx_tp))
#         dv_tp.online(lambda evt: refresh_output_route_name_all())
#     context.log.info("add_evt_videohub 등록 완료")
# ---------------------------------------------------------------------------- #
# import unittest
# class TestVideohub(unittest.TestCase):
#     def setUp(self):
#         self.videohub = Videohub()
#     def test_parse_response_valid_data(self):
#         data_text = "VIDEO OUTPUT ROUTING:\n1 2\n3 4\n\n"
#         self.videohub.parse_response(data_text)
#         self.assertEqual(self.videohub.routes, {1: 2, TP_PORT_VIDEOHUB: 4})
#     def test_parse_response_no_video_output_routing(self):
#         data_text = "SOME OTHER HEADER:\n1 2\n3 4\n\n"
#         self.videohub.parse_response(data_text)
#         self.assertEqual(self.videohub.routes, {})
#     def test_parse_response_empty_data(self):
#         data_text = ""
#         self.videohub.parse_response(data_text)
#         self.assertEqual(self.videohub.routes, {})
#     def test_parse_response_no_double_newline(self):
#         data_text = "VIDEO OUTPUT ROUTING:\n1 2\n3 4"
#         self.videohub.parse_response(data_text)
#         self.assertEqual(self.videohub.routes, {})
#     def test_parse_response_invalid_format(self):
#         data_text = "VIDEO OUTPUT ROUTING:\n1 A\n3 4\n\n"
#         self.assertEqual(self.videohub.routes, {})
# if __name__ == "__main__":
#     unittest.main()
