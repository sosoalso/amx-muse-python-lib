# 마지막 수정일 : 20260514
import atexit
import socket
import threading
import time
from typing import Dict, Tuple

from lib.event_manager import EventManager
from lib.network_manager.common import DEFAULT_BUFFER_SIZE, ReceiveListener, close_socket, make_received_event, to_bytes
from lib.utility import CommonLogger, start_thread


class UdpServer(CommonLogger, EventManager):
    def __init__(self, port, buffer_size=DEFAULT_BUFFER_SIZE, name=None):
        super().__init__("received", "online", "offline")
        self.name = name or f"udpserver_{port}"
        self.port = port
        self.buffer_size = buffer_size
        self.socket: socket.socket | None = None
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.running = False
        self.clients: Dict[Tuple[str, int], float] = {}
        self.echo = False
        self._thread_receive_loop: threading.Thread | None = None
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
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(("", self.port))
            self.socket.settimeout(0.2)
            self.running = True
            self.log_info("start() : server starting")
            self.emit("online")
            self._thread_receive_loop = start_thread(self._receive_loop)
        except Exception as e:
            self.running = False
            self._close_server_socket()
            self.log_error(f"start() : failed to start server {e=}")

    def stop(self):
        if not self.running and not self.socket:
            return
        was_running = self.running
        self.running = False
        with self._client_lock:
            self.clients.clear()
        self._close_server_socket()
        if was_running:
            self.emit("offline")
        self.log_info("stop() : stop signal sent")

    def send_to(self, host: str, port: int, data: bytes | bytearray | str):
        if not self.socket:
            return
        try:
            self.log_debug(f"send_to() : {host=} {port=} {data=}")
            self.socket.sendto(to_bytes(data), (host, port))
        except Exception as e:
            self.log_error(f"send_to() : failed to send {e=}")

    def send(self, data: bytes | bytearray | str, exclude_client: tuple[str, int] | None = None):
        try:
            with self._client_lock:
                client_addrs = list(self.clients.keys())
            for client_addr in client_addrs:
                if client_addr != exclude_client:
                    self.send_to(client_addr[0], client_addr[1], data)
        except Exception as e:
            self.log_error(f"send() : failed to send {e=}")

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        self.emit("received", make_received_event(self, data, address))

    def _receive_loop(self):
        self.log_debug("_receive_loop() : thread started")
        while self.running:
            try:
                if not self.socket:
                    break
                data, addr = self.socket.recvfrom(self.buffer_size)
                if not data:
                    continue
                with self._client_lock:
                    self.clients[addr] = time.time()
                self.log_debug(f"_receive_loop() : received {data=} {addr=}")
                self._emit_received(data, addr)
                if self.echo:
                    self.socket.sendto(data, addr)
            except socket.timeout:
                continue
            except OSError as e:
                if self.running:
                    self.log_error(f"_receive_loop() : socket {e=}")
                break
            except Exception as e:
                if self.running:
                    self.log_error(f"_receive_loop() : message receive {e=}")
                break
        self.log_debug("_receive_loop() : thread ended")

    def _close_server_socket(self):
        if self.socket:
            close_socket(self.socket)
            self.socket = None
