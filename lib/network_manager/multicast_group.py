# 마지막 수정일 : 20260514
import atexit
import socket
import threading
from typing import Tuple

from lib.event_manager import EventManager
from lib.network_manager.common import DEFAULT_BUFFER_SIZE, ReceiveListener, close_socket, make_received_event, to_bytes
from lib.utility import CommonLogger, run_thread


class MulticastGroup(CommonLogger, EventManager):
    def __init__(
        self,
        group_ip,
        port,
        bind_port=None,
        buffer_size=DEFAULT_BUFFER_SIZE,
        ttl=64,
        loopback=False,
        interface_ip="0.0.0.0",
        name=None,
    ):
        super().__init__("connected", "received", "online", "offline")
        self.connected = False
        self.name = name or f"multicastgroup_{group_ip}_{port}"
        self.group_ip = group_ip
        self.port = port
        self.interface_ip = interface_ip
        self.buffer_size = buffer_size
        self.ttl = ttl
        self.loopback = loopback
        self.bind_port = port if bind_port is None else bind_port
        self.socket: socket.socket | None = None
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.membership = None
        self._thread_receive_loop = None
        self._state_lock = threading.Lock()
        atexit.register(self.disconnect)

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def join(self):
        self.connect()

    def connect(self):
        self.log_info("connect() starting")
        with self._state_lock:
            if self.connected:
                return

        sock = None
        membership = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind(("", self.bind_port))

            group_bin = socket.inet_aton(self.group_ip)
            interface_bin = socket.inet_aton(self.interface_ip)
            membership = group_bin + interface_bin
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.ttl)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1 if self.loopback else 0)
            if self.interface_ip != "0.0.0.0":
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, interface_bin)
            sock.settimeout(1.0)

            with self._state_lock:
                self.socket = sock
                self.membership = membership
                self.connected = True

            try:
                self.emit("connected")
                self.emit("online")
            except Exception as e:
                self.log_error(f"connect() : emit error {e=}")
            self._thread_receive_loop = run_thread(self._thread_receive_loop, self._receive_loop)
        except Exception as e:
            if sock:
                self._close_socket(sock)
            with self._state_lock:
                self.connected = False
                self.socket = None
                self.membership = None
            self.log_error(f"connect() : failed {e=}")

    def leave(self):
        self.disconnect()

    def disconnect(self):
        with self._state_lock:
            was_connected = self.connected
            self.connected = False
            sock = self.socket
            self.socket = None
            membership = self.membership
            self.membership = None

        if sock:
            try:
                if membership:
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, membership)
            except Exception as e:
                self.log_error(f"disconnect() : failed to leave group {e=}")
            self._close_socket(sock)

        if was_connected:
            try:
                self.emit("offline")
            except Exception as e:
                self.log_error(f"disconnect() : emit error {e=}")
        self.log_info("disconnect() : disconnect signal sent")

    def send(self, msg: bytes | bytearray | str):
        if not self.socket or not self.connected:
            return
        try:
            msg = to_bytes(msg)
            self.socket.sendto(msg, (self.group_ip, self.port))
            self.log_debug(f"send() : sending {msg=}")
        except Exception as e:
            self.log_error(f"send() : failed to send {e=}")

    def _receive_loop(self):
        self.log_debug("_receive_loop() : thread started")
        while self.connected:
            try:
                if not self.socket:
                    break
                data, addr = self.socket.recvfrom(self.buffer_size)
                try:
                    self._emit_received(data, addr)
                except Exception as e:
                    self.log_error(f"_receive_loop() : emit error {e=}")
                self.log_debug(f"_receive_loop() : received {data=} {addr=}")
            except socket.timeout:
                continue
            except OSError as e:
                if self.connected:
                    self.log_error(f"_receive_loop() : socket {e=}")
                break
            except Exception as e:
                if self.connected:
                    self.log_error(f"_receive_loop() : receiving {e=}")
                break
        self.log_debug("_receive_loop() : thread ended")

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        self.emit("received", make_received_event(self, data, address))

    def _close_socket(self, sock: socket.socket):
        close_socket(sock)
