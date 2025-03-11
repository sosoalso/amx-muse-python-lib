# ---------------------------------------------------------------------------- #
import socket
import threading
import time
from types import SimpleNamespace

from lib.eventmanager import EventManager

# ---------------------------------------------------------------------------- #
BUFFER_SIZE = 1024
# ---------------------------------------------------------------------------- #

# # ---------------------------------------------------------------------------- #
# class TCPServer(EventManager):
#     def __init__(self, port, buffer_size=BUFFER_SIZE, connections=10):
#         super().__init__("received")
#         self.config = {"port": port, "buffer_size": buffer_size, "connections": connections}
#         self.port = port
#         self.connections = connections
#         self.clients = []
#         self.server = None
#         self._executor = ThreadPoolExecutor(max_workers=connections + 2)
#         self.lock = threading.Lock()
#         self.running = False
#         self.receive = self.ReceiveHandler(self)

#     class ReceiveHandler:
#         def __init__(self, client):
#             self.client = client

#         def listen(self, listener):
#             self.client.add_event_handler("received", listener)

#     def get_client(self, client, addr):
#         while self.running:
#             data = client.recv(1024)
#             if data:
#                 event = SimpleNamespace()
#                 event.arguments = {"data": data, "address": addr}
#                 self.trigger_event("received", event)
#             else:
#                 client.close()
#                 self.clients.remove(client)
#                 print(f"Connection closed from {addr}")

#     def send_clients(self, data):
#         if not self.clients:
#             print("No clients connected")
#             return
#         for client in self.clients:
#             client.sendall(data)

#     def send_client(self, client, data):
#         if client in self.clients:
#             client.sendall(data)

#     def start_server_thread(self):
#         self.running = True
#         self._executor.submit(self._start_server)

#     def _start_server(self):
#         self.server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#         self.server.bind((socket.gethostname(), self.port))
#         self.server.listen(self.connections)  # max connections
#         # print(f"TCP Server Listening on {self.host}:{self.port}")
#         while self.running:
#             try:
#                 (client_sock, client_addr) = self.server.accept()
#                 if client_sock:
#                     self.clients.append(client_sock)
#                     self._executor.submit(self.get_client, args=(client_sock, client_addr))
#             except (socket.error, socket.timeout):
#                 if not self.running:
#                     break

#     def stop_server(self):
#         self.running = False
#         self.server.close()
#         self._executor.shutdown(wait=True)
#         # print(f"TCP Server Disconnected from {self.host}:{self.port}")


# ---------------------------------------------------------------------------- #
class TcpClient(EventManager):

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
        self._thread_connect = None
        self._thread_receive = None
        self.lock = threading.Lock()
        self.receive = self.ReceiveHandler(self)

    class ReceiveHandler:
        def __init__(self, client):
            self.client = client

        def listen(self, listener):
            self.client.add_event_handler("received", listener)

    def connect(self):
        if not self.connected:
            self._thread_connect = threading.Thread(target=self._connect, daemon=True)
            self._thread_connect.start()

    def _connect(self):
        while not self.connected:
            try:
                with self.lock:
                    self.socket = socket.create_connection((self.ip, self.port))
                    if self.socket:
                        self.connected = True
                        self._run_thread_receive()
            except ConnectionRefusedError:
                print("_connect() Connection refused")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break
            except TimeoutError:
                print("_connect() Connection timed out")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break
            except Exception:
                print("_connect() error")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break

    def _handle_reconnect(self):
        if self.reconnect:
            self.connect()

    def _run_thread_receive(self):
        self._thread_receive = threading.Thread(target=self._receive, daemon=True)
        self._thread_receive.start()

    def _receive(self):
        self.trigger_event("connected")
        while self.connected:
            try:
                msg = self.socket.recv(self.BUFFER_SIZE)
                if msg:
                    print("msg: ", msg)
                    event = SimpleNamespace()
                    event.source = self
                    event.arguments = {"data": msg}
                    self.trigger_event("received", event)
            except Exception:
                with self.lock:
                    self.connected = False
                print("_receive() error")
                if self.reconnect:
                    self.connect()
                break

    def send_byte(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendall(message)
            except Exception:
                with self.lock:
                    self.connected = False
                self._handle_reconnect()

    def send(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendall(bytes(message, "UTF-8"))
            except Exception:
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
# class UdpClient:
#     def __init__(self, name, ip, port):
#         self.name = name
#         self.ip = ip
#         self.port = port
#         self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

#     def send(self, message):
#         self.socket.sendto(bytes(message, "UTF-8"), (self.ip, self.port))

#     def send_byte(self, message):
#         self.socket.sendto(message, (self.ip, self.port))

#     def close(self):
#         self.socket.close()


#     def open(self):
#         self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
class UdpClient(EventManager):

    def __init__(self, name, ip, port, reconnect=True, time_reconnect=5, buffer_size=BUFFER_SIZE, port_bind=None):
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
        self._thread_connect = None
        self._thread_receive = None
        self.lock = threading.Lock()
        self.receive = self.ReceiveHandler(self)
        self.port_bind = self.port if port_bind is None else port_bind

    class ReceiveHandler:
        def __init__(self, client):
            self.client = client

        def listen(self, listener):
            self.client.add_event_handler("received", listener)

    def connect(self):
        if not self.connected:
            self._thread_connect = threading.Thread(target=self._connect, daemon=True)
            self._thread_connect.start()

    def _connect(self):
        while not self.connected:
            try:
                with self.lock:
                    self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    # 수신을 위해 소켓에 로컬 포트를 바인딩합니다.
                    self.socket.bind(("", 0 if self.port_bind is None else self.port_bind))
                    if self.socket:
                        self.connected = True
                        self._run_thread_receive()
            except ConnectionRefusedError:
                print("_connect() Connection refused")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break
            except TimeoutError:
                print("_connect() Connection timed out")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break
            except Exception:
                print("_connect() error")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break

    def _handle_reconnect(self):
        if self.reconnect:
            self.connect()

    def _run_thread_receive(self):
        self._thread_receive = threading.Thread(target=self._receive, daemon=True)
        self._thread_receive.start()

    def _receive(self):
        self.trigger_event("connected")
        while self.connected:
            try:
                msg, addr = self.socket.recvfrom(self.BUFFER_SIZE)
                if msg:
                    print("msg: ", msg)
                    event = SimpleNamespace()
                    event.source = self
                    event.arguments = {"data": msg, "address": addr}
                    self.trigger_event("received", event)
            except Exception:
                with self.lock:
                    self.connected = False
                print("_receive() error")
                if self.reconnect:
                    self.connect()
                break

    def send_byte(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendto(message, (self.ip, self.port))
            except Exception:
                with self.lock:
                    self.connected = False
                self._handle_reconnect()

    def send(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendto(bytes(message, "UTF-8"), (self.ip, self.port))
            except Exception:
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
class UdpServer(EventManager):

    def __init__(self, port, buffer_size=BUFFER_SIZE):
        super().__init__("received")
        self.port = port
        self.BUFFER_SIZE = buffer_size
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("", self.port))
        print("UDP server bound to port:", self.socket.getsockname()[1])
        self._server_thread = None
        self.running = False
        self.receive = self.ReceiveHandler(self)

    class ReceiveHandler:
        def __init__(self, server):
            self.server = server

        def listen(self, listener):
            self.server.add_event_handler("received", listener)

    def start_server_thread(self):
        self._server_thread = threading.Thread(target=self._start_server, daemon=True)
        self._server_thread.start()

    def _start_server(self):
        self.running = True
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


# ---------------------------------------------------------------------------- #
if __name__ == "__main__":
    pass
