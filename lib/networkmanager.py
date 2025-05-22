import socket
import threading
from types import SimpleNamespace

from lib.eventmanager import EventManager
from mojo import context

# ---------------------------------------------------------------------------- #
DEFAULT_BUFFER_SIZE = 1024


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
        self.lock = threading.Lock()
        self.echo = False
        self.receive = self.ReceiveHandler(self)

    def connect(self, handler):
        self.add_event_handler("connected", handler)

    def disconnect(self, handler):
        self.add_event_handler("disconnected", handler)

    def start(self):
        self.listen()

    def listen(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(("", self.port))
        self.sock.listen()
        while True:
            client, address = self.sock.accept()
            self.clients.append(client)
            self.trigger_event("connected", client, address)
            threading.Thread(target=self.handle_client, args=(client, address)).start()

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
                with self.lock:
                    if client in self.clients:
                        self.clients.remove(client)
                context.log.error(f"클라이언트 에러 {address=}: {e}")
                break
        self.trigger_event("disconnected")

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

    def __init__(self, name, ip, port, reconnect=True, time_reconnect=5, buffer_size=DEFAULT_BUFFER_SIZE):
        super().__init__("connected", "received")
        self.name = name
        self.ip = ip
        self.port = port
        self.reconnect = reconnect
        self.time_reconnect = time_reconnect
        self.DEFAULT_BUFFER_SIZE = buffer_size
        self.connected = False
        self.socket = None
        self.lock = threading.Lock()
        self._thread_connect = None
        self._thread_receive = None
        self.receive = self.ReceiveHandler(self)

    def connect(self):
        context.log.debug(f"TcpClient.connect() {self.name=}")
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
                context.log.error("_connect() 연결 거부")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break
            except TimeoutError:
                context.log.error("_connect() 연결 타임아웃")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break
            except Exception:
                context.log.error("_connect() 에러")
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
        context.log.debug(f"TcpClient._receive() {self.name=} 연결됨")
        while self.connected:
            try:
                msg = self.socket.recv(self.DEFAULT_BUFFER_SIZE)
                if msg:
                    context.log.debug(f"TcpClient._receive() {self.name=} 수신 :: {msg=}")
                    event = SimpleNamespace()
                    event.source = self
                    event.arguments = {"data": msg}
                    self.trigger_event("received", event)
                    context.log.info(f"trigger_event received {event=}")
                else:
                    with self.lock:
                        self.connected = False
                        context.log.debug(f"TcpClient.connect() {self.name=} 수신 없음 연결 끊김")
                        if self.reconnect:
                            self.connect()
                    break
            except Exception:
                with self.lock:
                    self.connected = False
                context.log.error(f"TcpClient._receive()  {self.name=} :: 에러")
                if self.reconnect:
                    self.connect()
                break

    def send_byte(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendall(message)
                context.log.debug(f"TcpClient.send_byte() {self.name=} 전송 :: {message=}")
            except Exception:
                with self.lock:
                    self.connected = False
                self._handle_reconnect()

    def send(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendall(bytes(message, "UTF-8"))
                context.log.debug(f"TcpClient.send() {self.name=} 전송 :: {message=}")
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
        context.log.debug(f"TcpClient.disconnect() {self.name=} 연결 끊김")

    def is_connected(self):
        return self.connected


class UdpClient(EventManager):
    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.add_event_handler("received", listener)

    def __init__(
        self, name, ip, port, reconnect=True, time_reconnect=5, buffer_size=DEFAULT_BUFFER_SIZE, port_bind=None
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
        self.lock = threading.Lock()
        self.receive = self.ReceiveHandler(self)
        self.port_bind = port_bind if port_bind is not None else 0
        self.bound_port = None

    def connect(self):
        if not self.connected:
            self._thread_connect = threading.Thread(target=self._connect, daemon=True)
            self._thread_connect.start()

    def _connect(self):
        while not self.connected:
            try:
                with self.lock:
                    self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                    # 수신을 위해 소켓에 로컬 포트를 바인딩
                    self.socket.bind(("", 0 if self.port_bind is None else self.port_bind))
                    self.bound_port = self.socket.getsockname()[1]
                    context.log.debug(f"_connect() 포트에 바운드:{self.bound_port}")
                    if self.socket:
                        self.connected = True
                        self._run_thread_receive()
            except ConnectionRefusedError:
                context.log.error(f"UdpClient._connect() 연결 거부 {self.name=}")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break
            except TimeoutError:
                context.log.error(f"UdpClient._connect() 연결 타임아웃 {self.name=}")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break
            except Exception:
                context.log.error(f"UdpClient._connect() 에러 {self.name=}")
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
                msg, addr = self.socket.recvfrom(self.DEFAULT_BUFFER_SIZE)
                if msg:
                    context.log.debug(f"UdpClient._receive() {self.name=} 수신 :: {msg=} {addr=}")
                    event = SimpleNamespace()
                    event.source = self
                    event.arguments = {"data": msg, "address": addr}
                    self.trigger_event("received", event)
            except Exception:
                with self.lock:
                    self.connected = False
                    context.log.debug(f"UdpClient._receive() {self.name=} 수신 없음 에러")
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
                context.log.debug(f"UdpClient.send() {self.name=} 전송 :: {message=} {self.ip=} {self.port=}")
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
    def __init__(self, port, buffer_size=DEFAULT_BUFFER_SIZE):
        super().__init__("received")
        self.port = port
        self.DEFAULT_BUFFER_SIZE = buffer_size
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("", self.port))
        context.log.debug(f"UDP 서버 바운드:{self.socket.getsockname()[1]}")
        self._server_thread = None
        self.running = False
        self.receive = self.ReceiveHandler(self)

    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.add_event_handler("received", listener)

    def start(self):
        self._server_thread = threading.Thread(target=self._start, daemon=True)
        self._server_thread.start()

    def _start(self):
        self.running = True
        while self.running:
            try:
                data, addr = self.socket.recvfrom(self.DEFAULT_BUFFER_SIZE)
                if data:
                    context.log.debug(f"_start 수신 {addr=} {data=}")
                    event = SimpleNamespace()
                    event.arguments = {"data": data, "address": addr}
                    self.trigger_event("received", event)
            except (socket.error, socket.timeout):
                if not self.running:
                    break

    def stop_server(self):
        self.running = False
        self.socket.close()
