import socket
import threading
import time
from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple

from mojo import context

from lib.eventmanager import EventManager

VERSION = "2025.08.26"


def get_version():
    return VERSION


DEFAULT_BUFFER_SIZE = 2048


# ---------------------------------------------------------------------------- #
# section: TcpServer
# ---------------------------------------------------------------------------- #
class TcpServer(EventManager):
    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.on("received", listener)

    def __init__(self, port, buffer_size=DEFAULT_BUFFER_SIZE, name=None):
        super().__init__("received", "online", "offline", "connected", "disconnected")
        self.port = port
        self.name = name or f"TcpServer:{port}"
        self.buffer_size = buffer_size
        self.socket: Optional[socket.socket] = None
        self.receive = self.ReceiveHandler(self)
        self.running = False
        self.server_thread: Optional[threading.Thread] = None
        self.cleanup_thread: Optional[threading.Thread] = None
        self.clients: Dict[Tuple[str, int], Dict[str, Any]] = {}
        self.client_lock = threading.Lock()
        self.client_timeout = 60.0
        self.time_cleanup_clients = 10.0
        self.echo = False
        self.restart = True

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def start(self):
        context.log.debug(f"{self.name} start()")
        self.running = True
        self.server_thread = threading.Thread(target=self._start_server)
        self.server_thread.start()

    def _start_server(self):
        context.log.debug(f"{self.name} _start_server()")
        time.sleep(1)
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self.socket.bind(("", self.port))
            except OSError as e:
                if e.errno == 98:  # Address already in use
                    context.log.warn(f"{self.name} _start_server() 주소가 이미 사용중이며 무시")
                else:
                    self.running = False
                return
            self.socket.listen()
            self.cleanup_thread = threading.Thread(target=self._cleanup_clients)
            self.cleanup_thread.start()
            context.log.debug(f"{self.name} _start_server() 서버 시작")
            while self.running:
                try:
                    client, address = self.socket.accept()
                    with self.client_lock:
                        self.clients[address] = {"socket": client, "last_seen": time.time()}
                    self.emit("online", address=address)
                    self.emit("connected", address=address)
                    threading.Thread(target=self._receive_loop, args=(client, address)).start()
                except OSError:  # 소켓이 닫혀 있을 경우 발생할 수 있음
                    self.running = False
                    break
        except Exception as e:
            context.log.error(f"{self.name} _start_server() 서버 시작 실패 에러: {e}")
            self.running = False
            if self.restart:
                self.start()

    def stop(self):
        context.log.debug(f"{self.name} stop()")
        self.running = False
        for _, client_info in self.clients.items():
            try:
                client_socket = client_info.get("socket")
                if client_socket:
                    client_socket.shutdown(socket.SHUT_RDWR)
                    client_socket.close()
            except Exception as e:
                context.log.error(f"{self.name} stop() 클라이언트 소켓 닫기 실패 에러: {e}")
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except Exception as e:
                context.log.error(f"{self.name} stop() 클라이언트 소켓 닫기 실패 에러: {e}")
        if self.server_thread and self.server_thread.is_alive() and threading.current_thread() != self.server_thread:
            try:
                self.server_thread.join(timeout=1.0)
            except RuntimeError as e:
                context.log.error(f"{self.name} stop() 서버 스레드 조인 실패 에러: {e}")
        context.log.debug(f"{self.name} stop() 서버 중지")

    def _receive_loop(self, client_socket: socket.socket, address: Tuple[str, int]):
        context.log.debug(f"{self.name} _receive_loop()")
        try:
            while self.running:
                data = client_socket.recv(self.buffer_size)
                if not data:
                    break  # 클라이언트에 의해 연결 중단
                last_seen = time.time()
                with self.client_lock:
                    # 업데이트 클라이언트 라스트 씬 타임
                    if address in self.clients:
                        self.clients[address]["last_seen"] = last_seen
                context.log.debug(f"{self.name} _receive_loop() 수신 -- {data=} {address=}")
                event = SimpleNamespace()
                event.source = self
                if not isinstance(data, (bytes, bytearray)):
                    data = str(data).encode()  # Ensure msg is in bytes
                event.arguments = {"data": data, "address": address}
                self.emit("received", event)
                if self.echo:
                    client_socket.sendall(data)
        except (ConnectionResetError, BrokenPipeError):
            context.log.debug(f"{self.name} _receive_loop() 클라이언트 연결 끊김 {address=}")
        except Exception as e:
            if self.running:
                context.log.error(f"{self.name} _receive_loop() 에러: {e}")
        finally:
            client_socket.close()
            with self.client_lock:
                if address in self.clients:
                    del self.clients[address]
            self.emit("offline", address=address)
            self.emit("disconnected", address=address)
            context.log.debug(f"{self.name} _receive_loop() 클라이언트 연결 종료 {address=}")

    def send_to(self, client_socket: socket.socket, data: bytes | bytearray):
        try:
            client_socket.sendall(data)
        except Exception as e:
            context.log.error(f"{self.name} send_to() 전송 실패 에러: {e}")

    def send(self, data: bytes | bytearray, exclude_client: Optional[Tuple[str, int]] = None):
        try:
            with self.client_lock:
                clients_copy = dict(self.clients)
                for client_addr, client_info in clients_copy.items():
                    if client_addr != exclude_client:
                        client_socket = client_info.get("socket")
                        if client_socket:
                            self.send_to(client_socket, data)
        except Exception as e:
            context.log.error(f"{self.name} send() 전송 실패 에러: {e}")

    def _cleanup_clients(self):
        context.log.debug(f"{self.name} _cleanup_clients() 클라이언트 정리 스레드 시작")
        while self.running:
            try:
                current_time = time.time()
                with self.client_lock:
                    expired_clients = []
                    for client_addr, client_info in self.clients.items():
                        if current_time - client_info["last_seen"] > self.client_timeout:
                            expired_clients.append(client_addr)
                    for client_addr in expired_clients:
                        client_socket = self.clients[client_addr].get("socket")
                        if client_socket:
                            client_socket.shutdown(socket.SHUT_RDWR)
                            client_socket.close()
                        del self.clients[client_addr]
                        self.emit("offline", address=client_addr)
                        self.emit("disconnected", address=client_addr)
                        context.log.debug(f"{self.name} _cleanup_clients() 비활성 클라이언트 제거: {client_addr=}")
                time.sleep(self.time_cleanup_clients)
            except Exception as e:
                context.log.error(f"{self.name} _cleanup_clients() 클라이언트 정리 에러: {e}")
                time.sleep(self.time_cleanup_clients)

    def is_running(self):
        return self.running


# ---------------------------------------------------------------------------- #
# section: UdpServer
class UdpServer(EventManager):
    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.on("received", listener)

    def __init__(self, port, buffer_size=DEFAULT_BUFFER_SIZE, name=None):
        super().__init__("received")
        self.name = name or f"UdpServer:{port}"
        self.port = port
        self.buffer_size = buffer_size
        self.socket: Optional[socket.socket] = None
        self.receive = self.ReceiveHandler(self)
        self.running = False
        self.receive_thread: Optional[threading.Thread] = None
        self.cleanup_thread: Optional[threading.Thread] = None
        self.clients: Dict[Tuple[str, int], float] = {}
        self.client_lock = threading.Lock()
        self.client_timeout = 60.0
        self.time_cleanup_clients = 10.0  # 클라이언트 정리 주기 (초)
        self.echo = False

    def start(self):
        context.log.debug(f"{self.name} start()")
        if self.running and self.socket:
            context.log.info(f"{self.name} start() 이미 실행 중")
            return
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(("", self.port))
            self.running = True
            self.receive_thread = threading.Thread(target=self._receive_loop)
            self.receive_thread.start()
            self.cleanup_thread = threading.Thread(target=self._cleanup_clients)
            self.cleanup_thread.start()
            context.log.debug(f"{self.name} start() 서버 시작")
        except Exception as e:
            self.running = False
            context.log.error(f"{self.name} start() 서버 시작 실패 에러: {e}")

    def stop(self):
        context.log.debug(f"{self.name} stop()")
        self.running = False
        with self.client_lock:
            self.clients.clear()
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                context.log.error(f"{self.name} stop() 클라이언트 소켓 닫기 실패 에러: {e}")
            finally:
                self.socket = None
        if self.receive_thread and self.receive_thread.is_alive() and threading.current_thread() != self.receive_thread:
            try:
                self.receive_thread.join(timeout=1.0)
            except RuntimeError as e:
                context.log.error(f"{self.name} stop() 서버 스레드 조인 실패 에러: {e}")
        if self.cleanup_thread and self.cleanup_thread.is_alive() and threading.current_thread() != self.cleanup_thread:
            try:
                self.cleanup_thread.join(timeout=1.0)
            except RuntimeError as e:
                context.log.error(f"{self.name} stop() 서버 스레드 조인 실패 에러: {e}")

    def _receive_loop(self):
        context.log.debug(f"{self.name} _receive_loop()")
        while self.running:
            try:
                if not self.socket:
                    context.log.error(f"{self.name} 소켓 초기화 필요")
                    break
                data, addr = self.socket.recvfrom(self.buffer_size)
                if not data:
                    continue
                last_seen = time.time()
                with self.client_lock:
                    self.clients[addr] = last_seen
                context.log.debug(f"{self.name} _receive_loop() 수신 -- {data=} {addr=}")
                event = SimpleNamespace()
                event.source = self
                if not isinstance(data, (bytes, bytearray)):
                    data = str(data).encode()  # Ensure msg is in bytes
                event.arguments = {"data": data, "address": addr}
                self.emit("received", event)
                if self.echo:
                    self.socket.sendto(data, addr)
            except OSError as e:
                if self.running:
                    context.log.error(f"{self.name} _receive_loop() 소켓 에러: {e}")
                    time.sleep(1)  # 에러 발생 시 대기 후 재시도
            except Exception as e:
                if self.running:
                    context.log.error(f"{self.name} _receive_loop() 메세지 수신 에러: {e}")
                    time.sleep(1)  # 에러 발생 시 대기 후 재시도

    def send_to(self, host: str, port: int, data: bytes | bytearray):
        if not self.socket:
            return
        try:
            context.log.debug(f"{self.name} send_to() {host=} {port=} {data=}")
            self.socket.sendto(data, (host, port))
        except Exception as e:
            context.log.error(f"{self.name} send_to() 전송 실패 에러: {e}")

    def send(self, data: bytes | bytearray, exclude_client: Optional[Tuple[str, int]] = None):
        with self.client_lock:
            try:
                for client_addr in self.clients:
                    if client_addr != exclude_client:
                        self.send_to(client_addr[0], client_addr[1], data)
            except Exception as e:
                context.log.error(f"{self.name} send() {client_addr} 전송 실패 에러: {e}")

    def _cleanup_clients(self):
        context.log.debug(f"{self.name} _cleanup_clients() 클라이언트 정리 스레드 시작")
        while self.running:
            try:
                current_time = time.time()
                with self.client_lock:
                    expired_clients = []
                    for client_addr, last_seen in self.clients.items():
                        if current_time - last_seen > self.client_timeout:
                            expired_clients.append(client_addr)
                    for client_addr in expired_clients:
                        try:
                            del self.clients[client_addr]
                            context.log.debug(f"{self.name} _cleanup_clients() 비활성 클라이언트 제거: {client_addr=}")
                        except KeyError:
                            pass  #  클라이언트가 이미 제거된 경우
                time.sleep(self.time_cleanup_clients)  # 10초마다 정리
            except Exception as e:
                context.log.error(f"{self.name} _cleanup_clients() 클라이언트 정리 에러: {e}")
                time.sleep(self.time_cleanup_clients)  # 에러 발생 시에도 대기

    def is_running(self):
        return self.running


# ---------------------------------------------------------------------------- #
# section: TcpClient
# ---------------------------------------------------------------------------- #
class TcpClient(EventManager):
    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.on("received", listener)

    def __init__(
        self,
        server_ip,
        server_port,
        reconnect=True,
        time_reconnect=5.0,
        buffer_size=DEFAULT_BUFFER_SIZE,
        name=None,
    ):
        super().__init__("connected", "received", "online", "offline")
        self.name = name or f"TcpClient:{server_ip}:{server_port}"
        self.server_ip = server_ip
        self.server_port = server_port
        self.receive = self.ReceiveHandler(self)
        self.time_reconnect = time_reconnect
        self.timeout = 1.0
        self.buffer_size = buffer_size
        self.connected = False
        self.socket: Optional[socket.socket] = None
        self.connect_thread: Optional[threading.Thread] = None
        self.receive_thread: Optional[threading.Thread] = None
        self.reconnect = reconnect
        self.last_received_time = 0

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def connect(self):
        if not self.reconnect:
            context.log.debug(f"{self.name} connect() reconnect 비활성화")
            return
        if self.connected:
            context.log.debug(f"{self.name} connect() 이미 연결됨")
            return
        context.log.debug(f"{self.name} connect()")
        self.connect_thread = threading.Thread(target=self._connect)
        self.connect_thread.start()

    def _connect(self):
        while not self.connected:
            try:
                self.socket = socket.create_connection((self.server_ip, self.server_port))
                if self.socket:
                    if not self.reconnect:
                        self.socket.settimeout(self.timeout)  # reconnect 하지 않으면 수신 타임아웃 설정하기
                    self._run_thread_receive()
                    self.connected = True
            except ConnectionRefusedError:
                context.log.error(f"{self.name} _connect() 연결 거부")
                time.sleep(self.time_reconnect)
                if not self.reconnect:
                    break
            except TimeoutError:
                context.log.error(f"{self.name} _connect() 연결 타임아웃")
                time.sleep(self.time_reconnect)
                if not self.reconnect:
                    break
            except Exception:
                context.log.error(f"{self.name} _connect() 에러")
                time.sleep(self.time_reconnect)
                if not self.reconnect:
                    break

    def disconnect(self):
        if self.socket:
            self.socket.close()
        self.connected = False
        self.socket = None
        context.log.debug(f"{self.name} disconnect() 연결 끊김")

    def handle_reconnect(self):
        if self.reconnect:
            self.connect()

    def _run_thread_receive(self):
        self.receive_thread = threading.Thread(target=self._receive_loop)
        self.receive_thread.start()

    def _receive_loop(self):
        self.emit("connected")
        context.log.debug(f"{self.name} _receive_loop() 연결됨")
        while self.connected:
            try:
                if not self.socket:
                    context.log.error(f"{self.name} _receive_loop() 소켓 초기화 필요")
                else:
                    data = self.socket.recv(self.buffer_size)
                    if data:
                        context.log.debug(f"{self.name} _receive_loop() 수신 -- {data=}")
                        event = SimpleNamespace()
                        event.source = self
                        if not isinstance(data, (bytes, bytearray)):
                            data = str(data).encode()  # Ensure data is in bytes
                        event.arguments = {"data": data}
                        self.emit("received", event)
                    else:
                        self.connected = False
                        context.log.debug(f"{self.name} connect() 수신 없음 연결 끊김")
                        self.handle_reconnect()
                        break
            except socket.timeout:  # 데이터가 없는 타임 아웃 : reconnect 없으면 disconnect
                self.connected = False
                if not self.reconnect:
                    self.disconnect()
                    break
                continue  # 재접속 시 timeout 무시
            except Exception as e:
                self.connected = False
                context.log.error(f"{self.name} _receive_loop() 에러: {e}")
                self.handle_reconnect()
                break

    def send(self, message):
        if self.reconnect:
            if self.socket and self.connected:
                try:
                    context.log.debug(f"{self.name} send() 송신 -- {message=}")
                    self.socket.sendall(message)
                except Exception as e:
                    context.log.error(f"{self.name} send() 송신 실패 에러: {e}")
                    self.connected = False
                    self.handle_reconnect()
        else:

            def one_shot_send():
                try:
                    sock = socket.create_connection((self.server_ip, self.server_port), timeout=self.timeout)
                    sock.sendall(message)
                    context.log.info(f"송신 - {message}")
                    try:
                        sock.settimeout(self.timeout)
                        msg = sock.recv(self.buffer_size)
                        if msg:
                            context.log.info(f"수신 - {msg=}")
                            event = SimpleNamespace()
                            event.source = self
                            event.arguments = {"data": msg}
                            self.emit("received", event)
                        else:
                            context.log.info(
                                f"{self.name} one_shot_send() 서버에 의해 연결이 종료되어 응답을 받지 못함"
                            )
                    except socket.timeout:
                        context.log.info(f"{self.name} one_shot_send() {self.timeout} 초 이내에 응답을 받지 못함")
                    finally:
                        sock.close()
                        context.log.info(f"{self.name} one_shot_send() 연결 닫힘")
                except Exception as e:
                    context.log.error(f"{self.name} one_shot_send() 전송 실패 에러: {e=}")

            threading.Thread(target=one_shot_send).start()

    def is_connected(self):
        return self.connected


# ---------------------------------------------------------------------------- #
# section: UdpClient
# ---------------------------------------------------------------------------- #
class UdpClient(EventManager):
    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.on("received", listener)

    def __init__(
        self,
        server_ip,
        server_port,
        time_reconnect=10,
        connection_timeout=60.0,
        buffer_size=DEFAULT_BUFFER_SIZE,
        bound_port=None,
        name=None,
    ):
        super().__init__("connected", "received")
        self.name = name or f"UdpClient:{server_ip}:{server_port}"
        self.server_ip = server_ip
        self.server_port = server_port
        self.receive = self.ReceiveHandler(self)
        self.time_reconnect = time_reconnect
        self.buffer_size = buffer_size
        self.connected = False
        self.socket: Optional[socket.socket] = None
        self.receive_thread: Optional[threading.Thread] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.bound_port: Optional[int] = bound_port
        self.bind_port: Optional[int] = None
        self.last_received_time = 0
        self.connection_timeout = connection_timeout
        self.time_monitor_connection = 10.0

    def connect(self):
        try:
            if self.connected:
                return
            self._connect()
            if not self.connected:
                return
            self.last_received_time = time.time()  # 연결 시 수신 시간 초기화
            self.receive_thread = threading.Thread(target=self._receive_loop)
            self.receive_thread.start()
            self.monitor_thread = threading.Thread(target=self._monitor_connection)
            self.monitor_thread.start()
        except Exception as e:
            context.log.error(f"{self.name} connect() 시작 실패 에러: {e}")

    def _connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setblocking(False)
            self.socket.settimeout(1.0)  # recvfrom timeout 설정
            self.socket.bind(("", 0 if self.bound_port is None else self.bound_port))
            self.bind_port = self.socket.getsockname()[1]
            context.log.debug(f"{self.name} _connect() 바인딩된 포트: {self.bind_port}")
            self.connected = True
            self.emit("connected")
        except Exception as e:
            context.log.error(f"{self.name} _connect() 연결 실패 에러: {e}")
            self.connected = False

    def disconnect(self):
        self.connected = False
        if self.receive_thread and self.receive_thread.is_alive() and threading.current_thread() != self.receive_thread:
            try:
                self.receive_thread.join(timeout=1.0)
            except RuntimeError as e:
                context.log.error(f"{self.name} disconnect() receive_thread 조인 에러: {e}")
        if self.socket:
            try:
                self.socket.close()
            finally:
                self.socket = None
        context.log.info(f"{self.name} disconnect() 연결 중지")

    def send(self, msg: bytes | bytearray):
        if self.socket and self.connected:
            try:
                self.socket.sendto(msg, (self.server_ip, self.server_port))
                context.log.debug(f"{self.name} send() 송신 - {msg=}")
            except Exception as e:
                context.log.error(f"{self.name} send() 송신 실패: {e}")

    def _receive_loop(self):
        while self.connected:
            try:
                if not self.socket:
                    context.log.error(f"{self.name} 소켓 초기화 필요")
                    break
                data, addr = self.socket.recvfrom(self.buffer_size)
                self.last_received_time = time.time()  # 수신 시간 업데이트
                context.log.debug(f"{self.name} _receive_loop() 수신 - {data=} {addr=}")
                event = SimpleNamespace()
                event.source = self
                if not isinstance(data, (bytes, bytearray)):
                    data = str(data).encode()  # Ensure data is in bytes
                event.arguments = {"data": data, "address": addr}
                self.emit("received", event)
            except socket.timeout:
                continue
            except OSError as e:
                if self.connected:
                    context.log.error(f"{self.name} _receive_loop() 소켓 에러: {e}")
                break
            except Exception as e:
                if self.connected:
                    context.log.debug(f"{self.name} _receive_loop() 메세지 수신 중 에러: {e}")
                break

    def _monitor_connection(self):
        while self.connected:
            try:
                current_time = time.time()
                # 초기 연결 후 충분한 시간을 기다린 후에만 타임아웃 체크
                if self.last_received_time > 0 and current_time - self.last_received_time > self.connection_timeout:
                    context.log.warn(f"{self.name} _monitor_connection() 연결 타임아웃, 연결 재시도")
                    self.handle_reconnect()
                time.sleep(self.time_monitor_connection)
            except Exception as e:
                if self.connected:
                    context.log.error(f"{self.name} _monitor_connection() 모니터링 중 에러: {e}")
                time.sleep(self.time_monitor_connection)

    def handle_reconnect(self):
        try:
            old_connected = self.connected
            self.connected = False
            if self.socket:
                try:
                    self.socket.close()
                except Exception:
                    context.log.error(f"{self.name} handle_reconnect() 소켓 닫기 실패 에러: {e}")
                finally:
                    self.socket = None
            if old_connected:  # 이전에 연결되어 있었다면 재연결 시도
                time.sleep(1.0)  # 잠시 대기 후 재연결
                self.connect()
        except Exception as e:
            context.log.error(f"{self.name} handle_reconnect() 재연결 실패: {e}")
