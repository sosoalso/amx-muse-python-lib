# ---------------------------------------------------------------------------- #
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from lib.eventmanager import EventManager


# ---------------------------------------------------------------------------- #
class TcpClient(EventManager):
    BUFFER_SIZE = 1024

    def __init__(self, name, ip, port, reconnect=True, time_reconnect=5, buffer_size=BUFFER_SIZE):
        super().__init__("connected", "received")
        self.name = name
        self.ip = ip
        self.port = port
        self.reconnect = reconnect
        self.time_reconnect = time_reconnect
        self.BUFFER_SIZE = buffer_size
        self.connected = False
        self.socket = None
        self.receive_callback = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.lock = threading.Lock()
        self.receive = self.ReceiveHandler(self)

    class ReceiveHandler:
        def __init__(self, client):
            self.client = client

        def listen(self, listener):
            self.client.add_event_handler("received", listener)

    def connect(self):
        if not self.connected:
            self.executor.submit(self._connect)

    def _connect(self):
        while not self.connected:
            try:
                with self.lock:
                    self.socket = socket.create_connection((self.ip, self.port))
                    if self.socket:
                        self.connected = True
                        self._run_thread_receive()
            except (socket.error, socket.timeout):
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break

    def _handle_reconnect(self):
        if self.reconnect:
            self.connect()

    def _run_thread_receive(self):
        self.executor.submit(self._receive)
        self.trigger_event("connected")

    def _receive(self):
        while self.socket and self.connected:
            try:
                msg = self.socket.recv(self.BUFFER_SIZE)
                if msg:
                    print("msg: ", msg)
                    event = SimpleNamespace()
                    event.source = self
                    event.arguments = {"data": msg}
                    self.trigger_event("received", event)

            except (socket.error, socket.timeout):
                with self.lock:
                    self.connected = False
                if self.reconnect:
                    self.connect()

    def send_byte(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendall(message)
            except (socket.error, socket.timeout):
                with self.lock:
                    self.connected = False
                self._handle_reconnect()

    def send(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendall(bytes(message, "UTF-8"))
            except (socket.error, socket.timeout):
                with self.lock:
                    self.connected = False
                self._handle_reconnect()

    def disconnect(self):
        if self.socket and self.connected:
            try:
                self.socket.close()
            finally:
                with self.lock:
                    self.socket = None
                    self.connected = False

    def is_connected(self):
        return self.connected


# ---------------------------------------------------------------------------- #
class UdpClient:
    def __init__(self, name, ip, port):
        self.name = name
        self.ip = ip
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, message):
        self.socket.sendto(bytes(message, "UTF-8"), (self.ip, self.port))

    def send_byte(self, message):
        self.socket.sendto(message, (self.ip, self.port))

    def close(self):
        self.socket.close()

    def open(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)


# ---------------------------------------------------------------------------- #
class UdpServer(EventManager):
    BUFFER_SIZE = 1024

    def __init__(self, port):
        super().__init__("received")
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("", self.port))
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.running = False
        self.receive = self.ReceiveHandler(self)

    class ReceiveHandler:
        def __init__(self, client):
            self.client = client

        def listen(self, listener):
            self.client.add_event_handler("received", listener)

    def start_server_thread(self):
        self.running = True
        self.executor.submit(self._start_server)

    def _start_server(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(self.BUFFER_SIZE)
                if data:
                    event = SimpleNamespace()
                    event.arguments = {"data": data, "address": addr}
                    self.trigger_event("received", event)

            except (socket.error, socket.timeout):
                if not self.running:
                    break

    def stop_server(self):
        self.running = False
        self.socket.close()
        self.executor.shutdown(wait=True)


# ---------------------------------------------------------------------------- #
