# ---------------------------------------------------------------------------- #
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from eventmanager import EventManager


# ---------------------------------------------------------------------------- #
class TcpClient(EventManager):
    BUFFER_SIZE = 1024

    def __init__(self, name, ip, port, reconnect=True, time_reconnect=5):
        super().__init__("connected")
        self.name = name
        self.ip = ip
        self.port = port
        self.reconnect = reconnect
        self.time_reconnect = time_reconnect
        self.connected = False
        self.socket = None
        self.receive_callback = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.lock = threading.Lock()

    def set_receive_callback(self, callback):
        self.receive_callback = callback

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
            except ConnectionRefusedError as e:
                time.sleep(self.time_reconnect)
                if not self.reconnect:
                    break
            except TimeoutError as e:
                time.sleep(self.time_reconnect)
                if not self.reconnect:
                    break
            except Exception as e:
                time.sleep(self.time_reconnect)
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
                if msg and self.receive_callback is not None:
                    self.receive_callback(msg)
            except Exception as e:
                with self.lock:
                    self.connected = False
                if self.reconnect:
                    self.connect()
                break

    def send_byte(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendall(message)
            except Exception as e:
                with self.lock:
                    self.connected = False
                self._handle_reconnect()

    def send(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendall(bytes(message, "UTF-8"))
            except Exception as e:
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
        try:
            self.socket.sendto(bytes(message, "UTF-8"), (self.ip, self.port))
        except Exception as e:
            pass

    def send_byte(self, message):
        try:
            self.socket.sendto(message, (self.ip, self.port))
        except Exception as e:
            pass

    def close(self):
        try:
            self.socket.close()
        except Exception as e:
            pass

    def open(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except Exception as e:
            pass


# ---------------------------------------------------------------------------- #
class UdpServer:
    BUFFER_SIZE = 1024

    def __init__(self, port):
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("", self.port))
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.running = False
        self.receive_callback = None

    def start_server_thread(self):
        self.running = True
        self.executor.submit(self._start_server)

    def _start_server(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(self.BUFFER_SIZE)
                if self.receive_callback is not None:
                    self.receive_callback(data=data, addr=addr)
            except Exception as e:
                if not self.running:
                    break

    def set_receive_callback(self, callback):
        self.receive_callback = callback

    def stop_server(self):
        self.running = False
        self.socket.close()
        self.executor.shutdown(wait=True)


# ---------------------------------------------------------------------------- #
