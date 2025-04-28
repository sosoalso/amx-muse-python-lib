# ---------------------------------------------------------------------------- #
import asyncio
import socket
import threading
from types import SimpleNamespace

from lib.eventmanager import EventManager

# ---------------------------------------------------------------------------- #
BUFFER_SIZE = 1024


# ---------------------------------------------------------------------------- #
async def async_send_tcp_message_once(ip: str, port: int, message, timeout: float = 5):
    data = None
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout)
        print(f"send_tcp_message_once send: {ip}:{port} {message=}")
        writer.write(message.encode())
        data = await asyncio.wait_for(reader.read(100), timeout)
    except asyncio.TimeoutError:
        print(f"async_send_tcp_message_once {ip}:{port} Error: The connection attempt timed out.")
    except ConnectionRefusedError:
        print(f"async_send_tcp_message_once {ip}:{port} Error: Connection was refused.")
    except Exception as e:
        print(f"async_send_tcp_message_once {ip}:{port} An unexpected error occurred: {e}")
    finally:
        if "writer" in locals() and not writer.is_closing():
            print(f"async_send_tcp_message_once {ip}:{port} Close the connection")
            writer.close()
            await writer.wait_closed()
    return data


def send_tcp_message_once(ip: str, port: int, message, timeout: float = 5):
    return asyncio.run(async_send_tcp_message_once(ip, port, message, timeout))


# ---------------------------------------------------------------------------- #
class TcpServer(EventManager):
    def __init__(self, port, buffer_size=BUFFER_SIZE):
        super().__init__("received")
        self.debug = False
        self.port = port
        self.clients = []
        self.buffer_size = buffer_size
        self.sock = None
        self.lock = threading.Lock()
        self.echo = False
        self.receive = self.ReceiveHandler(self)

    # ---------------------------------------------------------------------------- #
    def log(self, msg):
        if self.debug:
            print(msg)

    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.add_event_handler("received", listener)

    # ---------------------------------------------------------------------------- #
    def start(self):
        self.listen()

    # ---------------------------------------------------------------------------- #
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

    # ---------------------------------------------------------------------------- #
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
                    raise ValueError("CLIENT Disconnected")
            except (socket.error, ValueError) as e:
                client.close()
                with self.lock:
                    if client in self.clients:
                        self.clients.remove(client)
                self.log(f"handle_client() Error with client {address=}: {e=}")
                break
        self.trigger_event("disconnected")

    def send_all(self, data):
        for client in self.clients:
            client.send(data)


# ---------------------------------------------------------------------------- #
class TcpClient(EventManager):
    def __init__(self, name, ip, port, reconnect=True, time_reconnect=5, buffer_size=BUFFER_SIZE):
        super().__init__("connected", "received")
        self.debug = False
        self.name = name
        self.ip = ip
        self.port = port
        self.reconnect = reconnect
        self.time_reconnect = time_reconnect
        self.BUFFER_SIZE = buffer_size
        self.connected = False
        self.socket = None
        # ---------------------------------------------------------------------------- #
        self._thread_connect = None
        self._thread_receive = None
        self.lock = threading.Lock()
        # ---------------------------------------------------------------------------- #
        self.receive = self.ReceiveHandler(self)

    # ---------------------------------------------------------------------------- #
    def log(self, msg):
        if self.debug:
            print(msg)

    # ---------------------------------------------------------------------------- #
    def online(self, callback):
        self.add_event_handler("connected", callback)

    def offline(self, callback):
        self.add_event_handler("disconnected", callback)

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
            except (ConnectionRefusedError, TimeoutError, Exception) as e:
                self.log(f"_connect() {e=}")
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break

    def _handle_reconnect(self):
        with self.lock:
            self.connected = False
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
                    self.log(f"_receive() :: {msg=}")
                    event = SimpleNamespace()
                    event.source = self
                    event.arguments = {"data": msg}
                    self.trigger_event("received", event)
                else:
                    with self.lock:
                        self.connected = False
                        self.log("_receive() :: None")
                        if self.reconnect:
                            self.connect()
                    break
            except Exception as e:
                with self.lock:
                    self.connected = False
                self.log(f"_receive() ERROR {e=}")
                self._handle_reconnect()
                break

    def send_byte(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendall(message)
            except Exception:
                self._handle_reconnect()

    def send(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendall(bytes(message, "UTF-8"))
            except Exception:
                self._handle_reconnect()

    # ---------------------------------------------------------------------------- #
    def disconnect(self):
        if self.socket and self.connected:
            with self.lock:
                self.socket.close()
                self.connected = False
                self.socket = None
            self.trigger_event("disconnect")

    # ---------------------------------------------------------------------------- #
    def is_connected(self):
        return self.connected


# ---------------------------------------------------------------------------- #
class UdpClient(EventManager):
    def __init__(self, name, ip, port, reconnect=True, time_reconnect=5, buffer_size=BUFFER_SIZE, port_bind=None):
        super().__init__("connected", "received")
        self.debug = False
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

    # ---------------------------------------------------------------------------- #
    def log(self, msg):
        if self.debug:
            print(msg)

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
                    self.log(f"_connect() Bound to port:{self.bound_port}")
                    if self.socket:
                        self.connected = True
                        self._run_thread_receive()
            except (ConnectionRefusedError, TimeoutError, Exception) as e:
                self.log(f"_connect() ERROR {e=}")
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
                    self.log(f"_receive() :: {msg=}")
                    event = SimpleNamespace()
                    event.source = self
                    event.arguments = {"data": msg, "address": addr}
                    self.trigger_event("received", event)
            except Exception as e:
                self.log(f"_receive() ERROR {e=}")
                with self.lock:
                    self.connected = False
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
        self.debug = False
        self.port = port
        self.BUFFER_SIZE = buffer_size
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("", self.port))
        self._server_thread = None
        self.running = False
        self.receive = self.ReceiveHandler(self)
        # ---------------------------------------------------------------------------- #

    def log(self, msg):
        if self.debug:
            print(msg)

    # ---------------------------------------------------------------------------- #
    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.add_event_handler("received", listener)

    # ---------------------------------------------------------------------------- #
    def start(self):
        self._server_thread = threading.Thread(target=self._start, daemon=True)
        self._server_thread.start()
        self.log(f"UDP server bound to port: {self.socket.getsockname()[1]}")

    def _start(self):
        self.running = True
        while self.running:
            try:
                data, addr = self.socket.recvfrom(self.BUFFER_SIZE)
                if data:
                    print(data)
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
