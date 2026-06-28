# 마지막 수정일 : 20260629
import atexit
import socket
import threading
from typing import Dict, Tuple

from lib.event_manager import EventManager
from lib.network_manager.common import (
    DEFAULT_BUFFER_SIZE,
    ReceiveListener,
    close_socket,
    make_received_event,
    to_bytes,
)
from lib.utility import CommonLogger, start_thread


class TcpServer(CommonLogger, EventManager):
    def __init__(self, port, buffer_size=DEFAULT_BUFFER_SIZE, name=None):
        super().__init__("received", "online", "offline", "connected", "disconnected")
        self.port = port
        self.name = name or f"tcpserver_{port}"
        self.buffer_size = buffer_size
        self.socket: socket.socket | None = None
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.running = False
        self.clients: Dict[Tuple[str, int], socket.socket] = {}
        self.echo = False
        self._thread_start_server: threading.Thread | None = None
        self._client_lock = threading.Lock()
        atexit.register(self.stop)

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def is_running(self):
        return self.running

    def start(self):
        if self.running:
            return
        self.running = True
        self.log_info("start() : server starting")
        self._thread_start_server = start_thread(self._start_server)

    def stop(self):
        if not self.running and not self.socket:
            return
        self.running = False
        self._close_all_clients()
        self._close_server_socket()
        self.log_info("stop() : stop signal sent")

    def send_to(self, client_socket: socket.socket, data: bytes | bytearray | str):
        try:
            client_socket.sendall(to_bytes(data))
            return True
        except Exception as e:
            self.log_error(f"send_to() : failed to send {e=}")
            return False

    def send(self, data: bytes | bytearray | str, exclude_client: tuple[str, int] | None = None):
        with self._client_lock:
            clients = list(self.clients.items())
        for address, client_socket in clients:
            if address == exclude_client:
                continue
            if not self.send_to(client_socket, data):
                self._close_client(address, client_socket)

    def _is_address_in_use_error(self, error: OSError) -> bool:
        return error.errno in (48, 98) or getattr(error, "winerror", None) == 10048

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        # emit: received(event: ReceivedEvent)  — event.arguments["data"]: bytes
        self.emit("received", make_received_event(self, data, address))

    def _close_all_clients(self):
        with self._client_lock:
            clients = list(self.clients.items())
            self.clients.clear()
        for _address, client_socket in clients:
            self._close_socket(client_socket)

    def _close_client(self, address: Tuple[str, int], client_socket: socket.socket | None = None, *, emit_events: bool = True) -> bool:
        with self._client_lock:
            removed_socket = self.clients.pop(address, None)
        socket_to_close = client_socket or removed_socket
        if socket_to_close:
            self._close_socket(socket_to_close)
        if removed_socket and emit_events:
            # emit: offline(address: tuple[str, int])
            self.emit("offline", address=address)
            # emit: disconnected(address: tuple[str, int])
            self.emit("disconnected", address=address)
        return removed_socket is not None

    def _close_socket(self, sock: socket.socket):
        close_socket(sock, shutdown=True)

    def _close_server_socket(self):
        if self.socket:
            self._close_socket(self.socket)
            self.socket = None

    def _start_server(self):
        self.log_debug("_start_server() thread start")
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.settimeout(0.2)
            try:
                self.socket.bind(("", self.port))
            except OSError as e:
                if self._is_address_in_use_error(e):
                    self.log_warn("_start_server() : Address already in use, ignoring")
                else:
                    self.log_error(f"_start_server() : failed to bind {e=}")
                self.running = False
                return

            self.socket.listen()
            while self.running:
                try:
                    client, address = self.socket.accept()
                    client.settimeout(0.2)
                    self.log_debug(f"_start_server() : client connected {address=}")
                    with self._client_lock:
                        self.clients[address] = client
                    # emit: connected(address: tuple[str, int])
                    self.emit("connected", address=address)
                    # emit: online(address: tuple[str, int])
                    self.emit("online", address=address)
                    start_thread(self._receive_loop, client, address)
                except socket.timeout:
                    continue
                except OSError:
                    break
        except Exception as e:
            self.log_error(f"_start_server() : server start failed {e=}")
        finally:
            self.running = False
            self._close_server_socket()

    def _receive_loop(self, client_socket: socket.socket, address: Tuple[str, int]):
        self.log_debug(f"_receive_loop() : {address=}")
        try:
            while self.running:
                try:
                    data = client_socket.recv(self.buffer_size)
                except socket.timeout:
                    continue
                if not data:
                    break
                self.log_debug(f"_receive_loop() : {data=} {address=}")
                self._emit_received(data, address)
                if self.echo:
                    client_socket.sendall(data)
        except (ConnectionResetError, BrokenPipeError):
            self.log_info(f"_receive_loop() : Client disconnected {address=}")
        except Exception as e:
            if self.running:
                self.log_error(f"_receive_loop() : {e=}")
        finally:
            removed = self._close_client(address, client_socket)
            if removed:
                self.log_info(f"_receive_loop() : Client connection closed {address=}")
