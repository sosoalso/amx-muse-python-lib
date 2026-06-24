# 마지막 수정일 : 20260514
import atexit
import socket
import threading
import time
from typing import Tuple

from lib.event_manager import EventManager
from lib.network_manager.common import (
    DEFAULT_BUFFER_SIZE,
    DEFAULT_TCP_CLIENT_CONNECT_TIMEOUT,
    DEFAULT_TCP_CLIENT_RECONNECT_TIME,
    DEFAULT_TCP_CLIENT_SOCKET_TIMEOUT,
    ReceiveListener,
    close_socket,
    make_received_event,
    to_bytes,
)
from lib.utility import CommonLogger, run_thread, start_thread


class TcpClient(CommonLogger, EventManager):
    def __init__(self, ip, port, reconnect_time=DEFAULT_TCP_CLIENT_RECONNECT_TIME, buffer_size=DEFAULT_BUFFER_SIZE, name=None):
        super().__init__("disconnected", "connected", "received", "online", "offline")
        self.name = name or f"tcpclient_{ip}_{port}"
        self.ip = ip
        self.port = port
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.reconnect_time = reconnect_time
        self.socket_timeout = DEFAULT_TCP_CLIENT_SOCKET_TIMEOUT
        self.connect_timeout = DEFAULT_TCP_CLIENT_CONNECT_TIMEOUT
        self.timeout_send_once = 1.0
        self.buffer_size = buffer_size
        self.connected = False
        self.socket: socket.socket | None = None
        self._thread_connect: threading.Thread | None = None
        self.reconnect = False
        self._state_lock = threading.Lock()
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
        self._thread_connect = run_thread(self._thread_connect, self._connect_loop)

    def disconnect(self):
        with self._state_lock:
            if not (self.connected or self.socket or self.reconnect):
                return
            self.reconnect = False
        self.log_info("disconnect() : disconnecting from server")
        self._set_state_disconnected()
        self._close_current_socket()

    def send(self, message: bytes | bytearray | str):
        message = to_bytes(message)

        with self._state_lock:
            reconnect_enabled = self.reconnect
            sock = self.socket
            is_connected = self.connected

        if reconnect_enabled:
            if not (sock and is_connected):
                return
            try:
                self.log_debug(f"send() : sending {message=}")
                sock.sendall(message)
            except Exception as e:
                self.log_error(f"send() : failed to send {e=}")
                with self._state_lock:
                    if self.socket is sock:
                        self.socket = None
                self._set_state_disconnected()
                self._close_socket(sock)
            return

        start_thread(self._send_once, message)

    def _connect_loop(self):
        while self.reconnect:
            sock = self._open_socket()
            if not sock:
                self._sleep_reconnect()
                continue

            with self._state_lock:
                if not self.reconnect:
                    self._close_socket(sock)
                    break
                self.socket = sock

            self._set_state_connected()
            self._receive_loop(sock)

            if self.reconnect:
                self._sleep_reconnect()

    def _open_socket(self) -> socket.socket | None:
        try:
            self.log_debug(f"_open_socket() : connecting to {self.ip}:{self.port}")
            sock = socket.create_connection((self.ip, self.port), timeout=self.connect_timeout)
            sock.settimeout(self.socket_timeout)
            return sock
        except (ConnectionRefusedError, TimeoutError, OSError) as e:
            self.log_debug(f"_open_socket() : connect failed {e=}")
            return None

    def _sleep_reconnect(self):
        end_time = time.time() + self.reconnect_time
        while self.reconnect and time.time() < end_time:
            time.sleep(0.1)

    def _set_state_connected(self):
        with self._state_lock:
            was_connected = self.connected
            self.connected = True
        if not was_connected:
            self.log_info("connected to server")
            self.log_debug("_set_state_connected() : connected to server")
            try:
                self.emit("connected")
                self.emit("online")
            except Exception as e:
                self.log_error(f"_set_state_connected() : emit error {e=}")

    def _set_state_disconnected(self):
        with self._state_lock:
            was_connected = self.connected
            self.connected = False
        if was_connected:
            self.log_info("disconnected from server")
            self.log_debug("_set_state_disconnected() : disconnected from server")
            try:
                self.emit("offline")
                self.emit("disconnected")
            except Exception as e:
                self.log_error(f"_set_state_disconnected() : emit error {e=}")
        return was_connected

    def _receive_loop(self, recv_sock: socket.socket):
        self.log_debug("_receive_loop() thread started")
        while self.reconnect:
            try:
                with self._state_lock:
                    if self.socket is not recv_sock:
                        break

                data = recv_sock.recv(self.buffer_size)
                if not data:
                    self.log_debug("_receive_loop() no data received, connection closed")
                    break

                self.log_debug(f"_receive_loop() received {data=}")
                try:
                    self._emit_received(data, address=(self.ip, self.port))
                except Exception as e:
                    self.log_error(f"_receive_loop() : emit error {e=}")
            except socket.timeout:
                continue
            except Exception as e:
                if isinstance(e, OSError) and self._is_socket_closed_error(e):
                    self.log_debug(f"_receive_loop() : socket already closed {e=}")
                else:
                    self.log_error(f"_receive_loop() : {e=}")
                break

        with self._state_lock:
            if self.socket is recv_sock:
                self.socket = None
        self._set_state_disconnected()
        self._close_socket(recv_sock)
        self.log_debug("_receive_loop() thread ended")

    def _close_current_socket(self):
        with self._state_lock:
            sock = self.socket
            self.socket = None
        if sock:
            self._close_socket(sock)

    def _close_socket(self, sock: socket.socket):
        close_socket(sock, shutdown=True)

    def _is_socket_closed_error(self, error: OSError) -> bool:
        return error.errno in (9, 10038) or getattr(error, "winerror", None) == 10038

    def _send_once(self, message: bytes | bytearray):
        try:
            sock = socket.create_connection((self.ip, self.port), timeout=self.timeout_send_once)
            sock.sendall(message)
            self.log_debug(f"_send_once() : sending {message=}")
            try:
                sock.settimeout(self.timeout_send_once)
                data = sock.recv(self.buffer_size)
                if data:
                    self.log_debug(f"_send_once() : received {data=}")
                    self._emit_received(data, address=(self.ip, self.port))
                else:
                    self.log_debug("_send_once() : connection closed by server, no response received")
            except socket.timeout:
                self.log_debug(f"_send_once() : no response received within {self.timeout_send_once} seconds")
            finally:
                self._close_socket(sock)
                self.log_debug("_send_once() : connection closed")
        except Exception as e:
            self.log_error(f"_send_once() : failed to send {e=}")

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        self.emit("received", make_received_event(self, data, address))
