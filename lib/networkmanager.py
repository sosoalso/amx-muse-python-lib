import socket
import threading
import time
from types import SimpleNamespace

from mojo import context

from lib.eventmanager import EventManager
from lib.lib_yeoul import handle_exception

# ---------------------------------------------------------------------------- #
VERSION = "2025.06.27"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
DEFAULT_BUFFER_SIZE = 2048


# ---------------------------------------------------------------------------- #
class TcpServer(EventManager):
    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.add_event_handler("received", listener)

    def __init__(self, port, buffer_size=DEFAULT_BUFFER_SIZE):
        super().__init__("received")
        self.port = port
        self.clients = []
        self.buffer_size = buffer_size
        self.sock = None
        self.echo = False
        self.receive = self.ReceiveHandler(self)

    @handle_exception
    def connect(self, handler):
        self.add_event_handler("connected", handler)

    @handle_exception
    def disconnect(self, handler):
        self.add_event_handler("disconnected", handler)

    @handle_exception
    def start(self):
        self.listen()

    @handle_exception
    def listen(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", self.port))
        self.sock.listen()
        while True:
            client, address = self.sock.accept()
            self.clients.append(client)
            self.trigger_event("connected", client, address)
            threading.Thread(target=self.handle_client, args=(client, address), daemon=True).start()

    @handle_exception
    def handle_client(self, client, address):
        while True:
            try:
                data = client.recv(self.buffer_size)
                if data:
                    event = SimpleNamespace()
                    event.source = self
                    event.arguments = {"data": data}
                    self.trigger_event("received", event)
                    if self.echo:
                        self.send_all(data)
                else:
                    context.log.error(f"클라이언트 연결 끊김 {address=}")
                    raise ValueError
            except (socket.error, ValueError) as e:
                client.close()
                if client in self.clients:
                    self.clients.remove(client)
                context.log.error(f"클라이언트 에러 {address=}: {e}")
                break
        self.trigger_event("disconnected")

    @handle_exception
    def send_all(self, data):
        for client in self.clients:
            client.send(data)


# ---------------------------------------------------------------------------- #
class TcpClient(EventManager):
    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.add_event_handler("received", listener)

    def __init__(
        self,
        name,
        ip,
        port,
        reconnect=True,
        time_reconnect=5,
        buffer_size=DEFAULT_BUFFER_SIZE,
    ):
        super().__init__("connected", "received")
        self.name = name
        self.ip = ip
        self.port = port
        self.reconnect = reconnect
        self.time_reconnect = time_reconnect
        self.DEFAULT_BUFFER_SIZE = buffer_size
        self.connected = False
        self.socket = None
        self._thread_connect = None
        self._thread_receive = None
        self.receive = self.ReceiveHandler(self)

    @handle_exception
    def connect(self):
        context.log.debug(f"TcpClient.connect() {self.name=}")
        if not self.connected:
            self._thread_connect = threading.Thread(target=self._connect, daemon=True)
            self._thread_connect.start()

    def _connect(self):
        while not self.connected:
            try:
                self.socket = socket.create_connection((self.ip, self.port))
                if self.socket:
                    self._run_thread_receive()
                    self.connected = True
            except ConnectionRefusedError:
                context.log.error(f"_connect() {self.ip}:{self.port} 연결 거부")
                time.sleep(self.time_reconnect)
                if not self.reconnect:
                    break
            except TimeoutError:
                context.log.error(f"_connect() {self.ip}:{self.port} 연결 타임아웃")
                time.sleep(self.time_reconnect)
                if not self.reconnect:
                    break
            except Exception:
                context.log.error(f"_connect() {self.ip}:{self.port} 에러")
                time.sleep(self.time_reconnect)
                if not self.reconnect:
                    break

    @handle_exception
    def _handle_reconnect(self):
        if self.reconnect:
            self.connect()

    @handle_exception
    def _run_thread_receive(self):
        self._thread_receive = threading.Thread(target=self._receive, daemon=True)
        self._thread_receive.start()

    def _receive(self):
        self.trigger_event("connected")
        context.log.debug(f"TcpClient._receive() {self.ip}:{self.port} 연결됨")
        while self.connected:
            try:
                msg = self.socket.recv(self.DEFAULT_BUFFER_SIZE)
                if msg:
                    context.log.debug(f"TcpClient._receive() {self.ip}:{self.port} 수신: {msg=}")
                    event = SimpleNamespace()
                    event.source = self
                    event.arguments = {"data": msg}
                    self.trigger_event("received", event)
                else:
                    self.connected = False
                    context.log.debug(f"TcpClient.connect() {self.ip}:{self.port}  수신: 없음 연결 끊김")
                    if self.reconnect:
                        self.connect()
                    break
            except Exception:
                self.connected = False
                context.log.error(f"TcpClient._receive() {self.ip}:{self.port} 에러")
                if self.reconnect:
                    self.connect()
                break

    # def send_byte(self, message):
    #     if self.socket and self.connected:
    #         try:
    #             self.socket.sendall(message)
    #             context.log.debug(f"TcpClient.send_byte() {self.ip}:{self.port} 전송: {message=}")
    #         except Exception:
    #             self.connected = False
    #             self._handle_reconnect()
    def send(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendall(message)
                # self.socket.sendall(bytes(message, "UTF-8"))
                context.log.debug(f"TcpClient.send() {self.ip}:{self.port} 전송: {message=}")
            except Exception:
                self.connected = False
                self._handle_reconnect()

    @handle_exception
    def disconnect(self):
        if self.socket:
            self.socket.close()
        self.connected = False
        self.socket = None
        context.log.debug(f"TcpClient.disconnect() {self.ip}:{self.port} 연결 끊김")

    @handle_exception
    def is_connected(self):
        return self.connected


class UdpClient(EventManager):
    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.add_event_handler("received", listener)

    def __init__(
        self,
        name,
        ip,
        port,
        reconnect=True,
        time_reconnect=5,
        buffer_size=DEFAULT_BUFFER_SIZE,
        port_bind=None,
    ):
        super().__init__("connected", "received")
        self.name = name
        self.ip = ip
        self.port = port
        self.reconnect = reconnect
        self.time_reconnect = time_reconnect
        self.DEFAULT_BUFFER_SIZE = buffer_size
        self.connected = False
        self.socket = None
        # self.receive_callback = None
        self._thread_connect = None
        self._thread_receive = None
        self.receive = self.ReceiveHandler(self)
        self.port_bind = port_bind if port_bind is not None else 0
        self.bound_port = None

    @handle_exception
    def connect(self):
        if not self.connected:
            self._thread_connect = threading.Thread(target=self._connect, daemon=True)
            self._thread_connect.start()

    def _connect(self):
        while not self.connected:
            try:
                self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # 수신을 위해 소켓에 로컬 포트를 바인딩
                self.socket.bind(("", 0 if self.port_bind is None else self.port_bind))
                self.bound_port = self.socket.getsockname()[1]
                context.log.debug(f"_connect() 포트에 바운드:{self.bound_port}")
                if self.socket:
                    self.connected = True
                    self._run_thread_receive()
            except ConnectionRefusedError:
                context.log.error(f"UdpClient._connect() {self.ip}:{self.port} 연결 거부 ")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break
            except TimeoutError:
                context.log.error(f"UdpClient._connect() {self.ip}:{self.port} 연결 타임아웃 ")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break
            except Exception:
                context.log.error(f"UdpClient._connect() {self.ip}:{self.port} 에러 ")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break

    @handle_exception
    def _handle_reconnect(self):
        if self.reconnect:
            self.connect()

    @handle_exception
    def _run_thread_receive(self):
        self._thread_receive = threading.Thread(target=self._receive, daemon=True)
        self._thread_receive.start()

    def _receive(self):
        self.trigger_event("connected")
        while self.connected:
            try:
                msg, addr = self.socket.recvfrom(self.DEFAULT_BUFFER_SIZE)
                if msg:
                    context.log.debug(f"UdpClient._receive() {self.ip}:{self.port} 수신 : {msg=} {addr=}")
                    event = SimpleNamespace()
                    event.source = self
                    event.arguments = {"data": msg, "address": addr}
                    self.trigger_event("received", event)
            except Exception:
                self.connected = False
                context.log.debug(f"UdpClient._receive() {self.ip}:{self.port} 수신 없음 에러")
                if self.reconnect:
                    self.connect()
                break

    # def send_byte(self, message):
    #     if self.socket and self.connected:
    #         try:
    #             self.socket.sendto(message, (self.ip, self.port))
    #         except Exception:
    #             self.connected = False
    #             self._handle_reconnect()
    def send(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendto(message, (self.ip, self.port))
                # self.socket.sendto(bytes(message, "UTF-8"), (self.ip, self.port))
                context.log.debug(f"UdpClient.send() {self.ip}:{self.port} 전송: {message=} ")
            except Exception:
                self.connected = False
                self._handle_reconnect()

    def disconnect(self):
        if self.socket and self.connected:
            try:
                self.socket.close()
            finally:
                self.socket = None
                self.connected = False

    @handle_exception
    def is_connected(self):
        return self.connected


# ---------------------------------------------------------------------------- #
class UdpServer(EventManager):
    def __init__(self, port, buffer_size=DEFAULT_BUFFER_SIZE):
        super().__init__("received")
        self.port = port
        self.DEFAULT_BUFFER_SIZE = buffer_size
        self._server_thread = None
        self.running = False
        self.receive = self.ReceiveHandler(self)
        self.socket = None
        self.clients = []

    @handle_exception
    def add_client(self, addr):
        if addr not in self.clients:
            self.clients.append(addr)

    @handle_exception
    def remove_client(self):
        self.clients = []

    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        @handle_exception
        def listen(self, listener):
            self.this.add_event_handler("received", listener)

    @handle_exception
    def start(self):
        if not self.socket:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(("", self.port))
            self._server_thread = threading.Thread(target=self._start, daemon=True)
            self._server_thread.start()

    def _start(self):
        self.running = True
        while self.running:
            try:
                data, addr = self.socket.recvfrom(self.DEFAULT_BUFFER_SIZE)
                if data:
                    context.log.debug(f"_start received: {addr=} {data=}")
                    self.add_client(addr)
                    event = SimpleNamespace()
                    event.arguments = {"data": data, "address": addr}
                    self.trigger_event("received", event)
            except (socket.error, socket.timeout):
                if not self.running:
                    break

    # def send_byte(self, message):
    #     if self.socket and self.running:
    #         for addr in self.clients:
    #             self.socket.sendto(message, addr)
    @handle_exception
    def send(self, message):
        if self.socket and self.running:
            for addr in self.clients:
                self.socket.sendto(message, addr)
                # self.socket.sendto(bytes(message, "UTF-8"), addr)
