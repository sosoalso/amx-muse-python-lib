from pythonosc import osc_message_builder, udp_client


class _OSCClientHandler:
    def __init__(self, address, port):
        self.address = address
        self.port = port
        self.sender = udp_client.UDPClient(address, port)

    def send_osc(self, address, arg, arg_type):
        msg = osc_message_builder.OscMessageBuilder(address)
        msg.add_arg(arg, arg_type)
        self.sender.send(msg.build())
