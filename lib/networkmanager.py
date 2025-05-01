import socket
import threading
from types import SimpleNamespace

from lib.eventmanager import EventManager
from lib.lib_yeoul import uni_log_debug, uni_log_error

# ---------------------------------------------------------------------------- #
BUFFER_SIZE = 1024
# ---------------------------------------------------------------------------- #
# import socket

# host = '127.0.0.1'  # localhost
# port = 12345


# try:
#     with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
#         s.bind((host, port))
#         s.listen()
#         print(f"Server listening on {host}:{port}")
#         conn, addr = s.accept()
#         with conn:
#             print(f"Connected by {addr}")
#             while True:
#                 data = conn.recv(1024)
#                 if not data:
#                     break
#                 conn.sendall(data)
# except socket.error as e:
#     print(f"Socket error: {e}")
# except Exception as e:
#     print(f"An error occurred: {e}")
# ---------------------------------------------------------------------------- #
# async def async_send_tcp_message_once(ip: str, port: int, message, timeout: float = 5):
#     data = None
#     try:
#         reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout)
#         uni_log_debug(f"send_tcp_message_once send: {ip}:{port} {message=}")
#         writer.write(message.encode())
#         data = await asyncio.wait_for(reader.read(100), timeout)
#     except asyncio.TimeoutError:
#         uni_log_error(f"async_send_tcp_message_once {ip}:{port} Error: The connection attempt timed out.")
#     except ConnectionRefusedError:
#         uni_log_error(f"async_send_tcp_message_once {ip}:{port} Error: Connection was refused.")
#     except Exception as e:
#         uni_log_error(f"async_send_tcp_message_once {ip}:{port} An unexpected error occurred: {e}")
#     finally:
#         if "writer" in locals() and not writer.is_closing():
#             uni_log_debug(f"async_send_tcp_message_once {ip}:{port} Close the connection")
#             writer.close()
#             await writer.wait_closed()
#     return data


# def send_tcp_message_once(ip: str, port: int, message, timeout: float = 5):
#     return asyncio.run(async_send_tcp_message_once(ip, port, message, timeout))


# ---------------------------------------------------------------------------- #
class TcpServer(EventManager):
    def __init__(self, port, buffer_size=BUFFER_SIZE):
        super().__init__("received")
        self.port = port
        self.clients = []
        self.buffer_size = buffer_size
        self.sock = None
        self.lock = threading.Lock()
        self.echo = False
        # ---------------------------------------------------------------------------- #
        self.receive = self.ReceiveHandler(self)

    def connect(self, handler):
        self.add_event_handler("connected", handler)

    def disconnect(self, handler):
        self.add_event_handler("disconnected", handler)

    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.add_event_handler("received", listener)

        # ---------------------------------------------------------------------------- #

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
                    uni_log_error(f"클라이언트 연결 끊김 {address=}")
                    raise ValueError
            except (socket.error, ValueError) as e:
                client.close()
                with self.lock:
                    if client in self.clients:
                        self.clients.remove(client)
                uni_log_error(f"클라이언트 에러 {address=}: {e}")
                break
        self.trigger_event("disconnected")

    def send_all(self, data):
        for client in self.clients:
            client.send(data)


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
        # self.receive_callback = None
        self._thread_connect = None
        self._thread_receive = None
        self.lock = threading.Lock()
        # ---------------------------------------------------------------------------- #
        self.receive = self.ReceiveHandler(self)
        # ---------------------------------------------------------------------------- #

    # ---------------------------------------------------------------------------- #
    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.add_event_handler("received", listener)

    # ---------------------------------------------------------------------------- #
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
                uni_log_error("_connect() 연결 거부")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break
            except TimeoutError:
                uni_log_error("_connect() 연결 타임아웃")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break
            except Exception:
                uni_log_error("_connect() 에러")
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
                    uni_log_debug(f"_receive 수신 {msg=}")
                    event = SimpleNamespace()
                    event.source = self
                    event.arguments = {"data": msg}
                    self.trigger_event("received", event)
                else:
                    with self.lock:
                        self.connected = False
                        uni_log_debug("_receive() 없음")
                        if self.reconnect:
                            self.connect()
                    break
            except Exception:
                with self.lock:
                    self.connected = False
                uni_log_error("_receive() 에러")
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
        # self.receive_callback = None
        self._thread_connect = None
        self._thread_receive = None
        self.lock = threading.Lock()
        self.receive = self.ReceiveHandler(self)
        self.port_bind = port_bind if port_bind is not None else 0
        self.bound_port = None

    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.add_event_handler("received", listener)

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
                    uni_log_debug(f"_connect() 포트에 바운드:{self.bound_port}")
                    if self.socket:
                        self.connected = True
                        self._run_thread_receive()
            except ConnectionRefusedError:
                uni_log_error("_connect() 연결 거부부")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break
            except TimeoutError:
                uni_log_error("_connect() 연결 타임아웃")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break
            except Exception:
                uni_log_error("_connect() 에러")
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
                    uni_log_debug(f"_receive 수신 : {addr=} {msg=}")
                    event = SimpleNamespace()
                    event.source = self
                    event.arguments = {"data": msg, "address": addr}
                    self.trigger_event("received", event)
            except Exception:
                with self.lock:
                    self.connected = False
                uni_log_error("_receive() 에러")
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
        uni_log_debug(f"UDP 서버 바운드:{self.socket.getsockname()[1]}")
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
                data, addr = self.socket.recvfrom(self.BUFFER_SIZE)
                if data:
                    uni_log_debug(f"_start 수신 {addr=} {data=}")
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
