import socket
from types import SimpleNamespace
from typing import Callable


class ReceiveListener:
    def __init__(self, register_listener: Callable):
        self._register_listener = register_listener

    def listen(self, listener):
        self._register_listener(listener)


def to_bytes(data: bytes | bytearray | str) -> bytes | bytearray:
    return data.encode() if isinstance(data, str) else data


def make_received_event(source, data: bytes, address: tuple[str, int]):
    event = SimpleNamespace()
    event.source = source
    event.arguments = {"data": data, "address": address}
    return event


def close_socket(sock: socket.socket, shutdown=False):
    if shutdown:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
    try:
        sock.close()
    except OSError:
        pass


DEFAULT_BUFFER_SIZE = 2048
DEFAULT_TCP_SERVER_CLIENT_TIMEOUT = 30.0
DEFAULT_UDP_SERVER_CLIENT_TIMEOUT = 30.0
DEFAULT_TCP_CLIENT_RECONNECT_TIME = 30.0
DEFAULT_TCP_CLIENT_SOCKET_TIMEOUT = 0.3
DEFAULT_UDP_CLIENT_RECONNECT_TIME = 30.0
DEFAULT_TCP_CLIENT_CONNECT_TIMEOUT = 3.0
