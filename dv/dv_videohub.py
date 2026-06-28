# 마지막 수정일 : 20260512
import re
from lib.event_manager import EventManager
from lib.network_manager import DEFAULT_TCP_CLIENT_RECONNECT_TIME, TcpClient
from lib.utility import CommonLogger
from lib.userdata import Userdata
from lib.utility import handle_exception


class Videohub(CommonLogger, EventManager):
    DEFAULT_PORT = 9990

    def __init__(self, ip, port=DEFAULT_PORT, max_inputs=40, max_outputs=40, reconnect_time=DEFAULT_TCP_CLIENT_RECONNECT_TIME, name=None):
        super().__init__("route")
        self.dv = TcpClient(ip, port, reconnect_time=reconnect_time)
        self.max_inputs = max_inputs
        self.max_outputs = max_outputs
        self.name = name if name else f"{__class__.__name__.lower()}_{self.dv.name if self.dv.name else ''}"
        self.userdata = Userdata(self.name)
        self.routes = self.userdata.get_value(f"{self.dv.name}_routes", {key: 0 for key in range(1, 20 + 1)})
        self.input_labels = [""] * self.max_inputs
        self.output_labels = [""] * self.max_outputs

    @handle_exception
    def init(self):
        self.dv.receive.listen(self.parse_response)
        self.dv.connect()

    @handle_exception
    def send(self, msg):
        self.dv.send(msg)

    @handle_exception
    def set_route_value(self, index_in, index_out):
        if isinstance(index_out, int) and 1 <= index_out <= self.max_outputs:
            self.routes[str(index_out)] = index_in
            self.userdata.set_value(f"{self.name}_routes", self.routes)

    @handle_exception
    def get_route_value(self, index_out):
        return self.routes.get(str(index_out), 0)

    def parse_response(self, *args):
        try:
            data_text = args[0].arguments["data"].decode()
            parsed_data_text_chunks = data_text.split("\n\n")
            for parsed_data_text in parsed_data_text_chunks:
                splitted_message = parsed_data_text.split("\n")
                header = splitted_message[0]
                if "VIDEO OUTPUT ROUTING:" in header:
                    for msg in splitted_message[1:]:
                        match = re.search(r"\d+ \d+", msg)
                        if match:
                            line = match.group(0)
                            idx_out, idx_in = map(int, line.split())
                            self.set_route_value(idx_in + 1, idx_out + 1)
                            # emit: route(index_in: int, index_out: int)
                            self.emit("route", index_in=idx_in + 1, index_out=idx_out + 1)
                elif "INPUT LABELS:" in header:
                    for msg in splitted_message[1:]:
                        idx, name = msg.split(maxsplit=1)
                        self.input_labels[int(idx)] = name
                    self.log_debug(f"Input labels: {self.input_labels}")
                    # emit: refresh_input_labels()
                    self.emit("refresh_input_labels")
                elif "OUTPUT LABELS:" in header:
                    for msg in splitted_message[1:]:
                        idx, name = msg.split(maxsplit=1)
                        self.output_labels[int(idx)] = name
                    self.log_debug(f"Output labels: {self.output_labels}")
                    # emit: refresh_output_labels()
                    self.emit("refresh_output_labels")
        except (AttributeError, KeyError, UnicodeDecodeError, ValueError) as e:
            self.log_error(f"Error decoding data: {e}")

    def set_route(self, index_in, index_out):
        if 0 <= index_in <= self.max_inputs and 1 <= index_out <= self.max_outputs:
            self.dv.send(f"VIDEO OUTPUT ROUTING:\n{index_out-1} {index_in-1}\n\n".encode())
            self.set_route_value(index_in, index_out)
            # emit: route(index_in: int, index_out: int)
            self.emit("route", index_in=index_in, index_out=index_out)
