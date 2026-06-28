# 마지막 수정일 : 20260625
import atexit
import socket
import threading
import time
from typing import Tuple

from lib.event_manager import EventManager
from lib.network_manager.common import (
    DEFAULT_BUFFER_SIZE,
    DEFAULT_UDP_CLIENT_RECONNECT_TIME,
    ReceiveListener,
    close_socket,
    make_received_event,
    to_bytes,
)
from lib.utility import CommonLogger, start_thread


class UdpClient(CommonLogger, EventManager):
    def __init__(
        self,
        ip,
        port,
        reconnect_time=DEFAULT_UDP_CLIENT_RECONNECT_TIME,
        buffer_size=DEFAULT_BUFFER_SIZE,
        bound_port=None,
        name=None,
    ):
        super().__init__("connected", "received", "online", "offline", "disconnected")
        self.name = name or f"udpclient_{ip}_{port}"
        self.ip = ip
        self.port = port
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.buffer_size = buffer_size
        self.connected = False
        self.reconnect = False
        self.socket: socket.socket | None = None
        self.bound_port: int | None = bound_port
        self.bind_port: int | None = None
        self.reconnect_time = reconnect_time
        self._thread_receive_loop: threading.Thread | None = None
        self._thread_monitor_loop: threading.Thread | None = None
        self._state_lock = threading.Lock()
        self._last_received_at = 0.0
        atexit.register(self.disconnect)

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def is_connected(self):
        return self.connected

    def connect(self):
        with self._state_lock:
            self.reconnect = True
            if self.socket:
                return

        if self._connect_socket():
            self._thread_monitor_loop = start_thread(self._monitor_loop)

    def disconnect(self):
        with self._state_lock:
            if not (self.connected or self.socket or self.reconnect):
                return
            self.reconnect = False
        if not self.connected and not self.socket:
            return
        self._set_state_disconnected()
        self._close_current_socket()
        self.log_debug("disconnect() : disconnect signal sent")

    def send(self, msg: bytes | bytearray | str):
        msg = to_bytes(msg)
        with self._state_lock:
            sock = self.socket
            is_connected = self.connected
        if not (sock and is_connected):
            return
        try:
            sock.sendto(msg, (self.ip, self.port))
            self.log_debug(f"send() : sending - {msg=}")
        except Exception as e:
            self.log_error(f"send() : failed to send: {e=}")
            self._set_state_disconnected()
            self._close_current_socket()

    def _connect_socket(self):
        sock = self._open_socket()
        if not sock:
            return False

        with self._state_lock:
            if not self.reconnect:
                close_socket(sock)
                return False
            was_connected = self.connected
            self.socket = sock
            self.bind_port = sock.getsockname()[1]
            self.connected = True
            self._last_received_at = time.time()

        if not was_connected:
            self.log_debug(f"_connect_socket() : connected to {self.ip}:{self.port}")
            try:
                self.emit("connected")
                self.emit("online")
            except Exception as e:
                self.log_error(f"_connect_socket() : emit error {e=}")
        self._thread_receive_loop = start_thread(self._receive_loop, sock)
        return True

    def _set_state_connected(self):
        with self._state_lock:
            was_connected = self.connected
            self.connected = True
        if not was_connected:
            self.emit("connected")
            self.emit("online")

    def _set_state_disconnected(self):
        with self._state_lock:
            was_connected = self.connected
            self.connected = False
        if was_connected:
            self.log_debug(f"_set_state_disconnected() : disconnected from {self.ip}:{self.port}")
            try:
                self.emit("offline")
                self.emit("disconnected")
            except Exception as e:
                self.log_error(f"_set_state_disconnected() : emit error {e=}")
        return was_connected

    def _open_socket(self) -> socket.socket | None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(0.2)
            sock.bind(("", 0 if self.bound_port is None else self.bound_port))
            self.log_debug(f"_open_socket() : bind_port={sock.getsockname()[1]}")
            return sock
        except Exception as e:
            self.log_error(f"_open_socket() : failed to open {e=}")
            return None

    def _monitor_loop(self):
        self.log_debug("_monitor_loop() : thread started")
        while True:
            with self._state_lock:
                if not self.reconnect:
                    break
                sock = self.socket
                connected = self.connected
                last_received_at = self._last_received_at

            if sock and connected and self.reconnect_time > 0:
                if time.time() - last_received_at >= self.reconnect_time:
                    self.log_debug(f"_monitor_loop() : no response for {self.reconnect_time} seconds, reconnecting")
                    self._set_state_disconnected()
                    self._close_current_socket()
                    self._connect_socket()
            elif not sock:
                self._connect_socket()

            time.sleep(min(0.5, max(0.1, self.reconnect_time / 2)))
        self.log_debug("_monitor_loop() : thread ended")

    def _receive_loop(self, recv_sock: socket.socket):
        self.log_debug("_receive_loop() : thread started")
        while True:
            try:
                with self._state_lock:
                    if not self.reconnect or self.socket is not recv_sock:
                        break
                    is_connected = self.connected
                if not is_connected:
                    break
                data, addr = recv_sock.recvfrom(self.buffer_size)
                with self._state_lock:
                    self._last_received_at = time.time()
                self.log_debug(f"_receive_loop() : received - {data=} {addr=}")
                try:
                    self._emit_received(data, addr)
                except Exception as e:
                    self.log_error(f"_receive_loop() : emit error {e=}")
            except socket.timeout:
                continue
            except OSError as e:
                with self._state_lock:
                    is_current_socket = self.socket is recv_sock
                if self.reconnect and is_current_socket:
                    self.log_error(f"_receive_loop() : socket {e=}")
                break
            except Exception as e:
                if self.reconnect:
                    self.log_error(f"_receive_loop() : receiving message {e=}")
                break
        with self._state_lock:
            is_current_socket = self.socket is recv_sock
            if is_current_socket:
                self.socket = None
                self.bind_port = None
        if is_current_socket:
            self._set_state_disconnected()
            close_socket(recv_sock)
        self.log_debug("_receive_loop() : thread ended")

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        self.emit("received", make_received_event(self, data, address))

    def _close_current_socket(self):
        with self._state_lock:
            sock = self.socket
            self.socket = None
            self.bind_port = None
        if sock:
            self._close_socket(sock)

    def _close_socket(self, sock: socket.socket):
        close_socket(sock)
