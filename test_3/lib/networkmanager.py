import socket
import threading
import time
from types import SimpleNamespace
from typing import Any, Dict, Optional, Tuple

from lib.eventmanager import EventManager

# from mojo import context


VERSION = "2025.07.28"


def get_version():
    return VERSION


DEFAULT_BUFFER_SIZE = 2048


def log_info(msg):
    print(f"INFO: {msg}")


def log_warn(msg):
    print(f"WARNING: {msg}")


def log_error(msg):
    print(f"ERROR: {msg}")


def log_debug(msg):
    print(f"DEBUG: {msg}")


# ---------------------------------------------------------------------------- #
# section: TcpServer
class TcpServer(EventManager):
    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.add_event_handler("received", listener)

    def __init__(self, port, buffer_size=DEFAULT_BUFFER_SIZE):
        super().__init__("received", "online", "offline", "connected", "disconnected")
        self.port = port
        self.buffer_size = buffer_size
        self.socket: Optional[socket.socket] = None
        self.receive = self.ReceiveHandler(self)
        self.is_running = False
        self.server_thread: Optional[threading.Thread] = None
        self.cleanup_thread: Optional[threading.Thread] = None
        self.clients: Dict[Tuple[str, int], Dict[str, Any]] = {}
        self.client_lock = threading.Lock()
        self.client_timeout = 30.0
        self.time_cleanup_clients = 10.0
        self.echo = False

    def online(self, handler):
        self.add_event_handler("online", handler)

    def offline(self, handler):
        self.add_event_handler("offline", handler)

    def start(self):
        self.is_running = True
        self.server_thread = threading.Thread(target=self._start_server, daemon=True)
        self.server_thread.start()

    def _start_server(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(("", self.port))
            self.socket.listen()
            self.cleanup_thread = threading.Thread(target=self._cleanup_clients, daemon=True)
            self.cleanup_thread.start()
            log_debug(f"TcpServer.start() {self.port} 서버 시작")
            while self.is_running:
                try:
                    client, address = self.socket.accept()
                    with self.client_lock:
                        self.clients[address] = {"socket": client, "last_seen": time.time()}
                    self.trigger_event("online", address=address)
                    self.trigger_event("connected", address=address)
                    threading.Thread(target=self._receive_loop, args=(client, address), daemon=True).start()
                except OSError:  # 소켓이 닫혀 있을 경우 발생할 수 있음
                    break
        except Exception as e:
            log_error(f"TcpServer.start() {self.port} 서버 시작 실패: {e}")
            self.is_running = False

    def stop(self):
        self.is_running = False
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                log_error(f"TcpServer.stop() 소켓 닫기 실패: {e}")
        if self.server_thread and self.server_thread.is_alive() and threading.current_thread() != self.server_thread:
            try:
                self.server_thread.join(timeout=1.0)
            except RuntimeError as e:
                log_error(f"Error joining server_thread: {e}")
        log_debug(f"TcpServer.stop() {self.port} 서버 중지")

    def _receive_loop(self, client_socket: socket.socket, address: Tuple[str, int]):
        try:
            while self.is_running:
                data = client_socket.recv(self.buffer_size)
                if not data:
                    break  # 클라이언트에 의해 연결 중단
                last_seen = time.time()
                with self.client_lock:
                    # 업데이트 클라이언트 라스트 씬 타임
                    if address in self.clients:
                        self.clients[address]["last_seen"] = last_seen

                log_debug(f"TcpServer._receive_loop() {self.port} 수신 : data={data} address={address}")
                event = SimpleNamespace()
                event.source = self
                event.arguments = {"data": data, "address": address}
                self.emit("received", event)
                if self.echo:
                    client_socket.sendall(data)
        except (ConnectionResetError, BrokenPipeError):
            log_debug(f"TcpServer._receive_loop() {self.port} 클라이언트 연결이 끊어졌습니다: {address}")
        except Exception as e:
            if self.is_running:
                log_error(f"TcpServer._receive_loop() {self.port} 에러: {e}")
        finally:
            client_socket.close()
            with self.client_lock:
                if address in self.clients:
                    del self.clients[address]
            self.trigger_event("offline", address=address)
            self.trigger_event("disconnected", address=address)
            log_debug(f"TcpServer._receive_loop() {self.port} 클라이언트 연결 종료: {address}")

    def send_to(self, client_socket: socket.socket, data: bytes | bytearray) -> bool:
        try:
            client_socket.sendall(data)
            return True
        except Exception as e:
            log_error(f"TcpServer.send_to() {self.port} 전송 실패: {e}")
            return False

    def send(self, data: bytes | bytearray, exclude_client: Optional[Tuple[str, int]] = None) -> bool:
        with self.client_lock:
            # 이터레이션 동안 수정 방지를 위해 클라이언트 사본 생성
            clients_copy = dict(self.clients)
            for client_addr, client_info in clients_copy.items():
                if client_addr != exclude_client:
                    client_socket = client_info.get("socket")
                    if client_socket:
                        self.send_to(client_socket, data)
        return True

    def _cleanup_clients(self):
        log_debug(f"TcpServer._cleanup_clients() {self.port} 클라이언트 정리 스레드 시작")
        while self.is_running:
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
                            client_socket.close()
                        del self.clients[client_addr]
                        self.trigger_event("offline", address=client_addr)
                        self.trigger_event("disconnected", address=client_addr)
                        log_debug(f"TcpServer._cleanup_clients() {self.port} 비활성 클라이언트 제거: {client_addr}")
                time.sleep(self.time_cleanup_clients)
            except Exception as e:
                log_error(f"TcpServer._cleanup_clients() {self.port} 클라이언트 정리 중 에러: {e}")
                time.sleep(self.time_cleanup_clients)


# ---------------------------------------------------------------------------- #
# section: UdpServer
class UdpServer(EventManager):
    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.add_event_handler("received", listener)

    def __init__(self, name, port, buffer_size=DEFAULT_BUFFER_SIZE):
        super().__init__("received")
        self.name = name
        self.port = port
        self.buffer_size = buffer_size
        self.socket: Optional[socket.socket] = None
        self.receive = self.ReceiveHandler(self)
        self.is_running = False
        self.receive_thread: Optional[threading.Thread] = None
        self.cleanup_thread: Optional[threading.Thread] = None
        self.clients: Dict[Tuple[str, int], float] = {}
        self.client_lock = threading.Lock()
        self.client_timeout = 60.0
        self.time_cleanup_clients = 10.0  # 클라이언트 정리 주기 (초)

    def start(self) -> bool:
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(("", self.port))
            self.is_running = True
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            self.cleanup_thread = threading.Thread(target=self._cleanup_clients, daemon=True)
            self.cleanup_thread.start()
            log_debug(f"UdpServer.start() {self.port} 서버 시작")
            return True
        except Exception as e:
            log_error(f"UdpServer.start() {self.port} 서버 시작 실패: {e}")
            return False

    def stop(self):
        self.is_running = False
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                log_error(f"UdpServer.stop() {self.port} 소켓 닫기 실패: {e}")
            finally:
                self.socket = None
        if self.receive_thread and self.receive_thread.is_alive() and threading.current_thread() != self.receive_thread:
            try:
                self.receive_thread.join(timeout=1.0)
            except RuntimeError as e:
                log_error(f"Error joining receive_thread: {e}")
        if self.cleanup_thread and self.cleanup_thread.is_alive() and threading.current_thread() != self.cleanup_thread:
            try:
                self.cleanup_thread.join(timeout=1.0)
            except RuntimeError as e:
                log_error(f"Error joining cleanup_thread: {e}")
        log_info(f"UdpServer.stop() {self.port} 서버 중지")

    def _receive_loop(self):
        while self.is_running:
            try:
                if not self.socket:
                    log_error(f"UdpServer {self.port} 소켓 초기화 필요")
                    break
                data, addr = self.socket.recvfrom(self.buffer_size)
                last_seen = time.time()
                with self.client_lock:
                    self.clients[addr] = last_seen
                log_debug(f"UdpServer._receive_loop() {self.port} 수신 : {data=} {addr=}")
                event = SimpleNamespace()
                event.source = self
                event.arguments = {"data": data, "address": addr}
                self.emit("received", event)
            except OSError as e:
                if self.is_running:
                    log_error(f"UdpServer._receive_loop() {self.port} 소켓 에러: {e=}")
                time.sleep(1)  # 에러 발생 시 대기 후 재시도
            except Exception as e:
                if self.is_running:
                    log_error(f"UdpServer._receive_loop() {self.port} 메세지 수신 중 에러: {e=}")
                time.sleep(1)  # 에러 발생 시 대기 후 재시도

    def send_to(self, host: str, port: int, data: bytes | bytearray) -> bool:
        if not self.socket:
            return False
        try:
            self.socket.sendto(data, (host, port))
            return True
        except Exception as e:
            log_error(f"UdpServer.send() {self.port} 전송 실패: {e}")
            return False

    def send(self, data: bytes | bytearray, exclude_client: Optional[Tuple[str, int]] = None) -> bool:
        with self.client_lock:
            try:
                for client_addr in self.clients:
                    if client_addr != exclude_client:
                        self.send_to(client_addr[0], client_addr[1], data)
                return True
            except Exception as e:
                log_error(f"UdpServer.send() {self.port} {client_addr} 전송 실패: {e}")
                return False

    def _cleanup_clients(self):
        log_debug(f"UdpServer._cleanup_clients() {self.port} 클라이언트 정리 스레드 시작")
        while self.is_running:
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
                            log_debug(f"UdpServer._cleanup_clients() {self.port} 비활성 클라이언트 제거: {client_addr}")
                        except KeyError:
                            # 클라이언트가 이미 제거된 경우
                            pass
                time.sleep(self.time_cleanup_clients)  # 10초마다 정리
            except Exception as e:
                log_error(f"UdpServer._cleanup_clients() {self.port} 클라이언트 정리 중 에러: {e}")
                time.sleep(self.time_cleanup_clients)  # 에러 발생 시에도 대기


# ---------------------------------------------------------------------------- #
# section: TcpClient
class TcpClient(EventManager):
    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.add_event_handler("received", listener)

    def __init__(
        self,
        name,
        server_ip,
        server_port,
        reconnect=True,
        time_reconnect=5.0,
        buffer_size=DEFAULT_BUFFER_SIZE,
    ):
        super().__init__("connected", "received", "online", "offline")
        self.name = name
        self.server_ip = server_ip
        self.server_port = server_port
        self.receive = self.ReceiveHandler(self)
        self.time_reconnect = time_reconnect
        self.timeout = 3.0
        self.buffer_size = buffer_size
        self.connected = False
        self.socket: Optional[socket.socket] = None
        self.connect_thread: Optional[threading.Thread] = None
        self.receive_thread: Optional[threading.Thread] = None
        self.reconnect = reconnect
        self.last_received_time = 0

    def online(self, handler):
        self.add_event_handler("online", handler)

    def offline(self, handler):
        self.add_event_handler("offline", handler)

    def connect(self) -> bool:
        try:
            if self.connected:
                return True
            self._connect()
            if not self.connected:
                return False
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
        except Exception as e:
            log_error(f"TcpClient.connect() {self.name} {self.server_ip}:{self.server_port} 시작 실패 {e=}")
            return False
        return True

    def _connect(self):
        while not self.connected:
            try:
                self.socket = socket.create_connection((self.server_ip, self.server_port))
                if not self.reconnect and self.socket:
                    self.socket.settimeout(self.timeout)  # reconnect 하지 않으면 수신 타임아웃 설정하기
                self.connected = True
                self.emit("online")
                self.emit("connected")
            except ConnectionRefusedError:
                log_error(f"_connect() {self.server_ip}:{self.server_port} 연결 거부")
                if self.reconnect:
                    time.sleep(self.time_reconnect)
                else:
                    break
            except TimeoutError:
                log_error(f"_connect() {self.server_ip}:{self.server_port} 연결 타임아웃")
                if self.reconnect:
                    time.sleep(self.time_reconnect)
                else:
                    break
            except Exception:
                log_error(f"_connect() {self.server_ip}:{self.server_port} 에러")
                if self.reconnect:
                    time.sleep(self.time_reconnect)
                else:
                    break

    def disconnect(self):
        self.connected = False
        if self.receive_thread and self.receive_thread.is_alive() and threading.current_thread() != self.receive_thread:
            try:
                self.receive_thread.join(timeout=1.0)
            except RuntimeError as e:
                log_error(f"Error joining receive_thread: {e}")
        if self.socket:
            try:
                self.socket.close()
            finally:
                self.socket = None
        log_debug(f"TcpClient.disconnect() {self.server_ip}:{self.server_port} 연결 중지")

    def send(self, msg: bytes | bytearray) -> bool:
        if self.reconnect:
            if self.socket and self.connected:
                try:
                    self.socket.sendall(msg)
                    log_debug(f"TcpClient.send() {self.server_ip}:{self.server_port} 전송: {msg=}")
                    return True
                except Exception:
                    self.connected = False
                    if self.reconnect:
                        self.connect()
                    return False
        else:
            try:
                self.connect()
                if self.socket and self.connected:
                    self.socket.sendall(msg)
                    log_debug(f"TcpClient.send() {self.server_ip}:{self.server_port} 전송: {msg=}")
                    # schedule delayed disconnect when not reconnecting
                    scheduling = threading.Timer(self.time_reconnect, self.disconnect)
                    scheduling.daemon = True
                    scheduling.start()
                    return True
            except Exception as e:
                log_error(f"TcpClient.send() {self.server_ip}:{self.server_port} 전송 실패: {e=}")
                return False
        return False

    def _receive_loop(self):
        while self.connected:
            try:
                if not self.socket:
                    log_error(f"TcpClient {self.name} {self.server_ip}:{self.server_port} 소켓 초기화 필요")
                    break
                else:
                    msg = self.socket.recv(self.buffer_size)
                    self.last_received_time = time.time()
                if msg:
                    log_debug(f"TcpClient._receive_loop() {self.server_ip}:{self.server_port} 수신: {msg=}")
                    event = SimpleNamespace()
                    event.source = self
                    event.arguments = {"data": msg}
                    self.trigger_event("received", event)
                else:
                    self.connected = False
                    if self.reconnect:
                        self.connect()
                    break
            except socket.timeout:
                if not self.reconnect:  # 데이타가 없는 타임아웃 : reconnect 없으면 disconnect
                    self.disconnect()
                    break

                continue  # 재접속 시엔 timeout 무시
            except Exception:
                self.connected = False
                log_error(f"TcpClient._receive_loop() {self.server_ip}:{self.server_port} 에러")
                if self.reconnect:
                    self.connect()
                break

    def is_connected(self):
        return self.connected


# ---------------------------------------------------------------------------- #
# section: UdpClient
class UdpClient(EventManager):
    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.add_event_handler("received", listener)

    def __init__(
        self,
        name,
        server_ip,
        server_port,
        time_reconnect=10,
        buffer_size=DEFAULT_BUFFER_SIZE,
        bound_port=None,
    ):
        super().__init__("connected", "received")
        self.name = name
        self.server_ip = server_ip
        self.server_port = server_port
        self.receive = self.ReceiveHandler(self)
        self.time_reconnect = time_reconnect
        self.buffer_size = buffer_size
        self.connected = False
        self.socket: Optional[socket.socket] = None
        self.connect_thread: Optional[threading.Thread] = None
        self.receive_thread: Optional[threading.Thread] = None
        self.monitor_thread: Optional[threading.Thread] = None
        self.bound_port: Optional[int] = bound_port
        self.last_received_time = 0
        self.connection_timeout = 60.0
        self.time_monitor_connection = 10.0

    def connect(self) -> bool:
        try:
            if self.connected:
                return True
            self._connect()
            if not self.connected:
                return False
            self.last_received_time = time.time()  # 연결 시 수신 시간 초기화
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()
            self.monitor_thread = threading.Thread(target=self._monitor_connection, daemon=True)
            self.monitor_thread.start()
            self.emit("connected")
            return True
        except Exception as e:
            log_error(f"UDPClient.connect() {self.name} {self.server_ip}:{self.server_port} 시작 실패 {e=}")
            return False

    def _connect(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setblocking(False)
            self.socket.settimeout(1.0)  # recvfrom timeout 설정
            self.socket.bind(("", 0 if self.bound_port is None else self.bound_port))
            self.bound_port = self.socket.getsockname()[1]
            log_debug(
                f"UdpClient._connect() {self.name} {self.server_ip}:{self.server_port} 바인딩된 포트: {self.bound_port}"
            )
            self.connected = True
            self.emit("connected")
        except Exception as e:
            log_error(f"UdpClient._connect() {self.name} {self.server_ip}:{self.server_port} 연결 실패: {e=}")
            self.connected = False

    def disconnect(self):
        self.connected = False
        if self.receive_thread and self.receive_thread.is_alive() and threading.current_thread() != self.receive_thread:
            try:
                self.receive_thread.join(timeout=1.0)
            except RuntimeError as e:
                log_error(f"Error joining receive_thread: {e}")
        if self.socket:
            try:
                self.socket.close()
            finally:
                self.socket = None
        log_info(f"UDPClient.disconnect() {self.name} {self.server_ip}:{self.server_port} 연결 중지")

    def send(self, msg: bytes | bytearray) -> bool:
        if self.socket and self.connected:
            try:
                self.socket.sendto(msg, (self.server_ip, self.server_port))
                log_debug(f"UdpClient.send() {self.name} {self.server_ip}:{self.server_port} 전송: {msg=}")
                return True
            except Exception as e:
                log_error(f"UdpClient.send() {self.name} {self.server_ip}:{self.server_port} 전송 실패: {e=}")
                return False
        return False

    def _receive_loop(self):
        while self.connected:
            try:
                if not self.socket:
                    log_error(f"UdpClient {self.name} {self.server_ip}:{self.server_port} 소켓 초기화 필요")
                    break
                msg, addr = self.socket.recvfrom(self.buffer_size)
                self.last_received_time = time.time()  # 수신 시간 업데이트
                log_debug(f"UdpClient._receive_loop() {self.server_ip}:{self.server_port} 수신 : {msg=} {addr=}")
                event = SimpleNamespace()
                event.source = self
                event.arguments = {"data": msg, "address": addr}
                self.emit("received", event)
            except socket.timeout:
                continue
            except OSError as e:
                if self.connected:
                    log_error(
                        f"UdpClient._receive_loop() {self.name} {self.server_ip}:{self.server_port} 소켓 에러: {e=}"
                    )
                break
            except Exception:
                if self.connected:
                    log_debug(
                        f"UdpClient._receive_loop() {self.name} {self.server_ip}:{self.server_port} 메세지 수신 중 에러"
                    )
                break

    def _monitor_connection(self):
        while self.connected:
            try:
                current_time = time.time()
                # 초기 연결 후 충분한 시간을 기다린 후에만 타임아웃 체크
                if self.last_received_time > 0 and current_time - self.last_received_time > self.connection_timeout:
                    log_warn(
                        f"UdpClient._monitor_connection() {self.name} {self.server_ip}:{self.server_port} 연결 타임아웃, 연결 재시도"
                    )
                    self.handle_reconnect()
                time.sleep(self.time_monitor_connection)
            except Exception as e:
                if self.connected:
                    log_error(
                        f"UdpClient._monitor_connection() {self.name} {self.server_ip}:{self.server_port} 모니터링 중 에러: {e=}"
                    )
                time.sleep(self.time_monitor_connection)

    def handle_reconnect(self):
        try:
            old_connected = self.connected
            self.connected = False  # 먼저 연결 상태를 false로 설정

            if self.socket:
                try:
                    self.socket.close()
                except Exception:
                    pass  # 소켓 닫기 실패는 무시
                finally:
                    self.socket = None

            if old_connected:  # 이전에 연결되어 있었다면 재연결 시도
                time.sleep(1)  # 잠시 대기 후 재연결
                self.connect()
        except Exception as e:
            log_error(f"UdpClient.handle_reconnect() {self.name} {self.server_ip}:{self.server_port} 재연결 실패: {e=}")
