from lib.eventmanager import EventManager
from lib.lib_yeoul import handle_exception, log_info
from lib.userdata import Userdata


# ---------------------------------------------------------------------------- #
# SECTION - 제어 장비
# ---------------------------------------------------------------------------- #
class Vidmtx(EventManager):
    def __init__(self, dv, name):
        super().__init__("route", "routes")
        self.dv = dv
        self.name = name
        self.vidmtx_routes = Userdata(f"{self.name}_routes.json", default_value={key: 0 for key in range(1, 8)})
        self.dv.receive.listen(self.parse_response)

    @handle_exception
    def vidmtx_send(self, cmd: int, body: bytearray):
        msg = bytearray([0x7B, 0x7B, cmd, len(body)])
        msg += body
        # msg.append((sum(msg) + 0xFA) % 256)
        msg += bytearray([(sum(msg) + 0xFA) % 256])
        msg += bytearray([0x7D, 0x7D])
        self.dv.send(msg)

    @handle_exception
    def set_route(self, idx_in, idx_out):
        log_info(f"vidmtx_set_route {idx_in=} {idx_out=}")
        if idx_in < 1 or idx_in > 8 or idx_out < 1 or idx_out > 8:
            return
        if self.vidmtx_routes.get_value(idx_out, 0) == idx_in:
            return
        flag_in = idx_in - 1
        flag_out = 1 << (idx_out - 1)
        self.vidmtx_send(0x01, bytearray([flag_in, flag_out]))
        self.vidmtx_routes.set_value(idx_out, idx_in)
        self.trigger_event("route", idx_in=idx_in, idx_out=idx_out)

    @handle_exception
    def set_routes(self, idx_in, idx_outs):
        log_info(f"vidmtx_set_routes {idx_in=} {idx_outs=}")
        if idx_in < 1 or idx_in > 8 or not all(1 <= idx_out <= 8 for idx_out in idx_outs):
            return
        flag_in = idx_in - 1
        flags_out = 0
        for idx_out in idx_outs:
            if self.vidmtx_routes.get_value(idx_out, 0) != idx_in:
                flags_out |= 1 << (idx_out - 1)
            self.vidmtx_routes.set_value(idx_out, idx_in if idx_out in idx_outs else 0)
        self.vidmtx_send(0x01, bytearray([flag_in, flags_out]))
        self.trigger_event("routes", idx_in=idx_in, idx_outs=idx_outs)

    def parse_response(self, *args):
        pass


# class var:
#     sel_in = [0] * len(TP_LIST)


# def refresh_input_button(idx_tp):
#     for idx_in in range(1, NUM_VIDMTX_IN + 1):
#         tp_set_button(TP_LIST[idx_tp], TP_PORT_VIDMTX, idx_in + 100, var.sel_in[idx_tp] == idx_in)
#         tp_set_button(
#             TP_LIST[idx_tp],
#             TP_PORT_VIDMTX,
#             idx_in + 200,
#             var.sel_in[idx_tp] and vidmtx_instance.routes[idx_in] == var.sel_in[idx_tp],
#         )


# def refresh_output_button(idx_tp):
#     for idx_out in range(1, NUM_VIDMTX_OUT + 1):
#         tp_set_button(
#             TP_LIST[idx_tp],
#             TP_PORT_VIDMTX,
#             idx_out + 200,
#             var.sel_in[idx_tp] and vidmtx_instance.routes[idx_out] == var.sel_in[idx_tp],
#         )


# def refresh_input_button_name(idx_tp):
#     for idx_in in range(1, NUM_VIDMTX_IN + 1):
#         tp_set_button_text_unicode(TP_LIST[idx_tp], TP_PORT_VIDMTX, idx_in + 100, NAME_VIDMTX_IN[idx_in - 1])


# def refresh_output_button_name(idx_tp):
#     for idx_out in range(1, NUM_VIDMTX_OUT + 1):
#         tp_set_button_text_unicode(TP_LIST[idx_tp], TP_PORT_VIDMTX, idx_out + 200, NAME_VIDMTX_OUT[idx_out - 1])


# def refresh_output_route_name_all():
#     for idx_out in range(1, NUM_VIDMTX_OUT + 1):
#         refresh_output_route_name(idx_out)


# def refresh_output_route_name(idx_out):
#     if 0 < idx_out <= NUM_VIDMTX_OUT:
#         if 0 < vidmtx_instance.routes[idx_out] <= NUM_VIDMTX_IN:
#             tp_set_button_text_unicode_ss(
#                 TP_LIST, TP_PORT_VIDMTX, idx_out + 300, NAME_VIDMTX_IN[vidmtx_instance.routes[idx_out] - 1]
#             )
#         else:
#             tp_set_button_text_unicode_ss(TP_LIST, TP_PORT_VIDMTX, idx_out + 300, "")


# def add_tp_vidmtx():
#     for idx_tp, dv_tp in enumerate(TP_LIST):
#         # NOTE : 입력 선택 버튼 | ch 101-120
#         for idx_in in range(1, 20 + 1):

#             def set_selected_input(idx_tp=idx_tp, idx_in=idx_in):
#                 var.sel_in[idx_tp] = idx_in
#                 refresh_input_button(idx_tp)
#                 refresh_output_button(idx_tp)

#             input_select_button = ButtonHandler()
#             input_select_button.add_event_handler("push", set_selected_input)
#             tp_add_watcher(dv_tp, TP_PORT_VIDMTX, idx_in + 100, input_select_button.handle_event)
#         # NOTE : 출력 버튼 - 라우팅 | ch 201-220
#         for idx_out in range(1, 20 + 1):

#             def set_route(idx_tp=idx_tp, idx_out=idx_out):
#                 if var.sel_in[idx_tp] and idx_out:
#                     vidmtx_instance.set_route(var.sel_in[idx_tp] - 1, idx_out - 1)
#                     refresh_output_button(idx_tp)

#             output_route_button = ButtonHandler()
#             output_route_button.add_event_handler("push", set_route)
#             tp_add_watcher(dv_tp, TP_PORT_VIDMTX, idx_out + 200, output_route_button.handle_event)
#     context.log.info("add_tp_vidmtx 등록 완료")


# def add_evt_vidmtx():
#     # NOTE : 매트릭스 이벤트 피드백
#     def refresh_button_on_route_event(**kwargs):
#         for idx_evt, _ in enumerate(TP_LIST):
#             refresh_output_button(idx_evt)
#             refresh_output_route_name(kwargs["idx_out"] + 1)

#     vidmtx_instance.add_event_handler("route", refresh_button_on_route_event)
#     # NOTE : TP 온라인 피드백
#     for idx_tp, dv_tp in enumerate(TP_LIST):
#         dv_tp.online(lambda evt, idx_tp=idx_tp: refresh_input_button(idx_tp))
#         dv_tp.online(lambda evt, idx_tp=idx_tp: refresh_output_button(idx_tp))
#         dv_tp.online(lambda evt, idx_tp=idx_tp: refresh_input_button_name(idx_tp))
#         dv_tp.online(lambda evt, idx_tp=idx_tp: refresh_output_button_name(idx_tp))
#         dv_tp.online(lambda evt: refresh_output_route_name_all())
#     context.log.info("add_evt_vidmtx 등록 완료")


# ---------------------------------------------------------------------------- #
# import unittest
# class TestVidmtx(unittest.TestCase):
#     def setUp(self):
#         self.vidmtx = Vidmtx()
#     def test_parse_response_valid_data(self):
#         data_text = "VIDEO OUTPUT ROUTING:\n1 2\n3 4\n\n"
#         self.vidmtx.parse_response(data_text)
#         self.assertEqual(self.vidmtx.routes, {1: 2, TP_PORT_VIDMTX: 4})
#     def test_parse_response_no_video_output_routing(self):
#         data_text = "SOME OTHER HEADER:\n1 2\n3 4\n\n"
#         self.vidmtx.parse_response(data_text)
#         self.assertEqual(self.vidmtx.routes, {})
#     def test_parse_response_empty_data(self):
#         data_text = ""
#         self.vidmtx.parse_response(data_text)
#         self.assertEqual(self.vidmtx.routes, {})
#     def test_parse_response_no_double_newline(self):
#         data_text = "VIDEO OUTPUT ROUTING:\n1 2\n3 4"
#         self.vidmtx.parse_response(data_text)
#         self.assertEqual(self.vidmtx.routes, {})
#     def test_parse_response_invalid_format(self):
#         data_text = "VIDEO OUTPUT ROUTING:\n1 A\n3 4\n\n"
#         self.assertEqual(self.vidmtx.routes, {})
# if __name__ == "__main__":
#     unittest.main()
