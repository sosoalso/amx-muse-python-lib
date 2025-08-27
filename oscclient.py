from mojo import context

from lib.eventmanager import EventManager
from lib.networkmanager import UdpClient
from pythonosc.osc_message import OscMessage
from pythonosc.osc_message_builder import OscMessageBuilder

# ---------------------------------------------------------------------------- #


class OSCClient(EventManager):
    def __init__(self, address, port, bound_port=None):
        super().__init__()
        self.debug = False
        self.address = address
        self.port = port
        self.bound_port = bound_port
        self.dv = UdpClient(self.address, self.port, bound_port=self.bound_port)
        self.add_event()

    def connect(self):
        self.dv.connect()

    def add_event(self):
        def handle_receive(evt):
            datagram = evt.arguments["data"]
            parsed_osc_message = OscMessage(datagram)
            if self.debug:
                context.log.debug(f"{parsed_osc_message.address=}, {parsed_osc_message.params=}")
            self.emit(parsed_osc_message.address, params=parsed_osc_message.params)

        self.dv.receive.listen(handle_receive)

    def send(self, address, value, value_type=None):
        builder = OscMessageBuilder(address=address)
        builder.add_arg(arg_value=value, arg_type=value_type if value_type else None)
        message = builder.build()
        self.dv.send(message.dgram)
        if self.debug:
            context.log.debug(f"{__class__.__name__} {message.dgram=}")
