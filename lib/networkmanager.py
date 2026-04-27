import socket
import threading
import time
from types import SimpleNamespace
from typing import Any, Dict, Tuple

from lib.eventmanager import EventManager

# ---------------------------------------------------------------------------- #
VERSION = "2026.04.24"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
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
        self.debug = False
        self.port = port
        self.name = name or f"tcp_server:{port}"
        self.buffer_size = buffer_size
        self.socket: socket.socket | None = None
        self.receive = self.ReceiveHandler(self)
        self.running = False
        self.server_thread: threading.Thread | None = None
        self.cleanup_thread: threading.Thread | None = None
        # 클라이언트 주소를 키로 하고 소켓 정보를 값으로 저장하는 딕셔너리
        self.clients: Dict[Tuple[str, int], Dict[str, Any]] = {}
        # 클라이언트 딕셔너리 접근 시 스레드 안전성을 위한 락
        self.client_lock = threading.Lock()
        # 클라이언트의 타임아웃 시간 (초)
        self.client_timeout = 60.0
        # 클라이언트 정리 작업 수행 간격 (타임아웃의 절반)
        self.time_cleanup_clients = float(self.client_timeout // 2)
        self.echo = False
        self.restart = True

    def log_debug(self, message):
        if self.debug:
            print(f"{__class__.__name__} (DEBUG) -- {message}")

    def log_error(self, message):
        print(f"{__class__.__name__} (ERROR) -- {message}")

    def log_warn(self, message):
        print(f"{__class__.__name__} (WARN) -- {message}")

    def log_info(self, message):
        print(f"{__class__.__name__} (INFO) -- {message}")

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def start(self):
        self.log_info(f"{self.name} start()")
        self.running = True
        if not self.server_thread or not self.server_thread.is_alive():
            self.server_thread = threading.Thread(target=self._start_server, daemon=True)
            self.server_thread.start()

    def _start_server(self):
        self.log_debug(f"{self.name} _start_server() -- thread start")
        time.sleep(1.0)
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # SO_REUSEADDR: 이전 연결이 TIME_WAIT 상태일 때 포트 재사용 가능하게 설정
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self.socket.bind(("", self.port))
            except OSError as e:
                if e.errno == 98:  # Address already in use
                    self.log_warn(f"{self.name} _start_server() -- Address already in use, ignoring")
                else:
                    self.running = False
                return
            # 서버 소켓을 리스닝 상태로 변경
            self.socket.listen()
            if not self.cleanup_thread or not self.cleanup_thread.is_alive():
                self.cleanup_thread = threading.Thread(target=self._cleanup_clients, daemon=True)
                self.cleanup_thread.start()
            # 클라이언트 연결을 무한으로 수락하는 루프
            while self.running:
                try:
                    client, address = self.socket.accept()
                    self.log_debug(f"{self.name} _start_server() client connected {address=}")
                    with self.client_lock:
                        # 새로운 클라이언트 정보 저장 (소켓, 마지막 수신 시간)
                        self.clients[address] = {"socket": client, "last_seen": time.time()}
                    self.emit("connected", address=address)
                    self.emit("online", address=address)
                    # 각 클라이언트별로 수신 처리를 위한 독립적인 스레드 생성
                    threading.Thread(target=self._receive_loop, args=(client, address), daemon=True).start()
                except OSError:  # 소켓이 닫혀 있을 경우 발생할 수 있음
                    self.running = False
                    break
        except Exception as e:
            self.log_error(f"{self.name} _start_server() server start failed {e=}")
            self.running = False
            if self.restart:
                # 자동 재시작 활성화 시 서버 재시작
                self.start()

    def stop(self):
        if self.debug:
            self.log_debug(f"{self.name} stop() executing")
        self.running = False
        # 모든 클라이언트 연결 종료
        for _, client_info in self.clients.items():
            try:
                client_socket = client_info.get("socket")
                if client_socket:
                    # SHUT_RDWR: 읽기와 쓰기 모두 종료
                    client_socket.shutdown(socket.SHUT_RDWR)
                    client_socket.close()
            except Exception as e:
                self.log_error(f"{self.name} stop() -- failed to close client socket {e=}")
        # 서버 소켓 종료
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except Exception as e:
                self.log_error(f"{self.name} stop() -- failed to close server socket {e=}")
        # 서버 스레드 종료 대기 (현재 스레드 제외)
        if self.server_thread and self.server_thread.is_alive() and threading.current_thread() != self.server_thread:
            try:
                # 최대 1초 대기 후 강제 종료
                self.server_thread.join(timeout=1.0)
            except RuntimeError as e:
                self.log_error(f"{self.name} stop() -- failed to join server thread {e=}")
        self.log_info(f"{self.name} stop() -- server stopped")

    def _receive_loop(self, client_socket: socket.socket, address: Tuple[str, int]):
        self.log_debug(f"{self.name} _receive_loop() {address=}")
        try:
            while self.running:
                # 클라이언트로부터 데이터 수신
                data = client_socket.recv(self.buffer_size)
                if not data:
                    # 클라이언트에 의해 연결이 정상 종료됨
                    break
                last_seen = time.time()
                with self.client_lock:
                    # 클라이언트의 마지막 수신 시간 업데이트 (타임아웃 감지용)
                    if address in self.clients:
                        self.clients[address]["last_seen"] = last_seen
                if self.debug:
                    self.log_debug(f"{self.name} _receive_loop() {data=} {address=}")
                # SimpleNamespace를 사용한 이벤트 객체 생성
                event = SimpleNamespace()
                event.source = self
                event.arguments = {"data": data, "address": address}
                # 수신 데이터 이벤트 발생
                self.emit("received", event)
                # 에코 모드 활성화 시 수신한 데이터를 그대로 송신
                if self.echo:
                    client_socket.sendall(data)
        except (ConnectionResetError, BrokenPipeError):
            self.log_info(f"{self.name} _receive_loop() -- Client disconnected {address=}")
        except Exception as e:
            if self.running:
                self.log_error(f"{self.name} _receive_loop() {e=}")
        finally:
            # 클라이언트 소켓 종료
            client_socket.close()
            with self.client_lock:
                # 클라이언트 정보 제거
                if address in self.clients:
                    del self.clients[address]
            # 오프라인/연결 종료 이벤트 발생
            self.emit("offline", address=address)
            self.emit("disconnected", address=address)
            self.log_info(f"{self.name} _receive_loop() -- Client connection closed {address=}")

    def send_to(self, client_socket: socket.socket, data: bytes | bytearray | str):
        """특정 클라이언트 소켓으로 데이터 전송"""
        try:
            if isinstance(data, str):
                data = data.encode()
            client_socket.sendall(data)
        except Exception as e:
            self.log_error(f"{self.name} send_to() -- failed to send {e=}")

    def send(self, data: bytes | bytearray | str, exclude_client: tuple[str, int] | None = None):
        """지정된 클라이언트를 제외한 모든 클라이언트로 브로드캐스트"""
        try:
            with self.client_lock:
                # 현재 클라이언트 딕셔너리의 복사본을 생성하여 반복 중 수정 방지
                clients_copy = dict(self.clients)
                for client_addr, client_info in clients_copy.items():
                    # 제외 클라이언트가 아닌 경우만 전송
                    if client_addr != exclude_client:
                        client_socket = client_info.get("socket")
                        if client_socket:
                            self.send_to(client_socket, data)
        except Exception as e:
            self.log_error(f"{self.name} send() -- failed to send {e=}")

    def _cleanup_clients(self):
        """타임아웃된 클라이언트를 주기적으로 정리하는 스레드"""
        if self.debug:
            self.log_debug(f"{self.name} _cleanup_clients() client cleanup thread started")
        while self.running:
            try:
                current_time = time.time()
                with self.client_lock:
                    # 타임아웃 조건을 만족하는 클라이언트 찾기
                    expired_clients = []
                    for client_addr, client_info in self.clients.items():
                        # 마지막 수신 이후 타임아웃 시간 초과 확인
                        if current_time - client_info["last_seen"] > self.client_timeout:
                            expired_clients.append(client_addr)
                    # 타임아웃된 클라이언트 정리 및 연결 종료
                    for client_addr in expired_clients:
                        client_socket = self.clients[client_addr].get("socket")
                        if client_socket:
                            client_socket.shutdown(socket.SHUT_RDWR)
                            client_socket.close()
                        del self.clients[client_addr]
                        self.emit("offline", address=client_addr)
                        self.emit("disconnected", address=client_addr)
                        self.log_debug(f"{self.name} _cleanup_clients() -- removed inactive client: {client_addr=}")
                # Wait for configured interval
                time.sleep(self.time_cleanup_clients)
            except Exception as e:
                self.log_error(f"{self.name} _cleanup_clients() -- client cleanup {e=}")
                time.sleep(self.time_cleanup_clients)
        if self.debug:
            self.log_debug(f"{self.name} _cleanup_clients() -- thread ended")

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
        self.debug = False
        self.name = name or f"udp_server:{port}"
        self.port = port
        self.buffer_size = buffer_size
        self.socket: socket.socket | None = None
        self.receive = self.ReceiveHandler(self)
        self.running = False
        self.receive_thread: threading.Thread | None = None
        self.cleanup_thread: threading.Thread | None = None
        # UDP 클라이언트 주소와 마지막 수신 시간을 저장
        self.clients: Dict[Tuple[str, int], float] = {}
        self.client_lock = threading.Lock()
        self.client_timeout = 60.0
        self.time_cleanup_clients = float(self.client_timeout // 2)
        self.echo = False

    def log_debug(self, message):
        if self.debug:
            print(f"{__class__.__name__} (DEBUG) -- {message}")

    def log_error(self, message):
        print(f"{__class__.__name__} (ERROR) -- {message}")

    def log_warn(self, message):
        print(f"{__class__.__name__} (WARN) -- {message}")

    def log_info(self, message):
        print(f"{__class__.__name__} (INFO) -- {message}")

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def start(self):
        self.log_info(f"{self.name} start() -- server starting")
        if self.running and self.socket:
            self.log_info(f"{self.name} start() -- already running")
            return
        try:
            # UDP 소켓 생성
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # SO_REUSEADDR: 빠른 재시작을 위해 포트 재사용 허용
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # 모든 인터페이스의 지정 포트에 바인드
            self.socket.bind(("", self.port))
            self.running = True
            # 수신 스레드 시작
            if not self.receive_thread or not self.receive_thread.is_alive():
                self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
                self.receive_thread.start()
            # 클라이언트 정리 스레드 시작
            if not self.cleanup_thread or not self.cleanup_thread.is_alive():
                self.cleanup_thread = threading.Thread(target=self._cleanup_clients, daemon=True)
                self.cleanup_thread.start()
            if self.debug:
                self.log_debug(f"{self.name} start() -- server started")
        except Exception as e:
            self.running = False
            self.log_error(f"{self.name} start() -- failed to start server {e=}")

    def stop(self):
        self.running = False
        with self.client_lock:
            # 모든 클라이언트 정보 초기화
            self.clients.clear()
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                self.log_error(f"{self.name} stop() -- failed to close socket {e=}")
            finally:
                self.socket = None
        # 수신 스레드 종료 대기
        if self.receive_thread and self.receive_thread.is_alive() and threading.current_thread() != self.receive_thread:
            try:
                self.receive_thread.join(timeout=1.0)
            except RuntimeError as e:
                self.log_error(f"{self.name} stop() -- failed to join receive thread {e=}")
        # Wait for cleanup thread to end
        if self.cleanup_thread and self.cleanup_thread.is_alive() and threading.current_thread() != self.cleanup_thread:
            try:
                self.cleanup_thread.join(timeout=1.0)
            except RuntimeError as e:
                self.log_error(f"{self.name} stop() -- failed to join cleanup thread {e=}")
        self.log_info(f"{self.name} stop() -- server stopped")

    def _receive_loop(self):
        """UDP 패킷 수신 루프"""
        if self.debug:
            self.log_debug(f"{self.name} _receive_loop() -- thread started")
        while self.running:
            try:
                if not self.socket:
                    self.log_error(f"{self.name} _receive_loop() -- socket initialization needed")
                    break
                # UDP는 비연결형이므로 recvfrom으로 발신자 주소와 함께 수신
                data, addr = self.socket.recvfrom(self.buffer_size)
                if not data:
                    continue
                last_seen = time.time()
                with self.client_lock:
                    # UDP 클라이언트의 마지막 수신 시간 기록
                    self.clients[addr] = last_seen
                if self.debug:
                    self.log_debug(f"{self.name} _receive_loop() -- received {data=} {addr=}")
                # Create event object and emit received data event
                event = SimpleNamespace()
                event.source = self
                event.arguments = {"data": data, "address": addr}
                self.emit("received", event)
                # 에코 모드: 발신 클라이언트로 데이터 반송
                if self.echo:
                    self.socket.sendto(data, addr)
            except OSError as e:
                if self.running:
                    self.log_error(f"{self.name} _receive_loop() -- socket {e=}")
                    # Wait and retry on error for recovery
                    time.sleep(1)
            except Exception as e:
                if self.running:
                    self.log_error(f"{self.name} _receive_loop() -- message receive {e=}")
                    time.sleep(1)
        if self.debug:
            self.log_debug(f"{self.name} _receive_loop() -- thread ended")

    def send_to(self, host: str, port: int, data: bytes | bytearray | str):
        """특정 주소의 클라이언트로 UDP 패킷 전송"""
        if not self.socket:
            return
        try:
            self.log_debug(f"{self.name} send_to() -- {host=} {port=} {data=}")
            if isinstance(data, str):
                data = data.encode()
            self.socket.sendto(data, (host, port))
        except Exception as e:
            self.log_error(f"{self.name} send_to() -- failed to send {e=}")

    def send(self, data: bytes | bytearray | str, exclude_client: tuple[str, int] | None = None):
        """지정된 클라이언트를 제외한 모든 클라이언트로 브로드캐스트"""
        with self.client_lock:
            try:
                for client_addr in self.clients:
                    # 제외 클라이언트가 아닌 경우만 전송
                    if client_addr != exclude_client:
                        self.send_to(client_addr[0], client_addr[1], data)
            except Exception as e:
                self.log_error(f"{self.name} send() -- failed to send {e=}")

    def _cleanup_clients(self):
        """타임아웃된 UDP 클라이언트 주기적 정리"""
        if self.debug:
            self.log_debug(f"{self.name} _cleanup_clients() -- client cleanup thread started")
        while self.running:
            try:
                current_time = time.time()
                with self.client_lock:
                    # 타임아웃된 클라이언트 찾기
                    expired_clients = []
                    for client_addr, last_seen in self.clients.items():
                        if current_time - last_seen > self.client_timeout:
                            expired_clients.append(client_addr)
                    # 타임아웃된 클라이언트 제거
                    for client_addr in expired_clients:
                        try:
                            del self.clients[client_addr]
                            self.log_debug(f"{self.name} _cleanup_clients() -- removed inactive client: {client_addr=}")
                        except KeyError:
                            # 클라이언트가 이미 제거된 경우
                            pass
                time.sleep(self.time_cleanup_clients)
            except Exception as e:
                self.log_error(f"{self.name} _cleanup_clients() -- client cleanup {e=}")
                time.sleep(self.time_cleanup_clients)
        if self.debug:
            self.log_debug(f"{self.name} _cleanup_clients() -- thread ended")

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
        ip,
        port,
        reconnect_time=30.0,
        buffer_size=DEFAULT_BUFFER_SIZE,
        name=None,
    ):
        super().__init__("connected", "received", "online", "offline")
        self.debug = False
        self.name = name or f"tcp:{ip}:{port}"
        self.ip = ip
        self.port = port
        self.receive = self.ReceiveHandler(self)
        # 연결 재시도 간격 (초)
        self.reconnect_time = reconnect_time
        # 일회성 전송 모드에서 응답 대기 타임아웃
        self.timeout_send_once = 1.0
        self.buffer_size = buffer_size
        self.connected = False
        self.socket: socket.socket | None = None
        self.connect_thread: threading.Thread | None = None
        self.receive_thread: threading.Thread | None = None
        # 자동 재연결 활성화 플래그
        self.reconnect = False
        self.last_received_time = 0

    def log_debug(self, message):
        if self.debug:
            print(f"{__class__.__name__} (DEBUG) -- {message}")

    def log_error(self, message):
        print(f"{__class__.__name__} (ERROR) -- {message}")

    def log_warn(self, message):
        print(f"{__class__.__name__} (WARN) -- {message}")

    def log_info(self, message):
        print(f"{__class__.__name__} (INFO) -- {message}")

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def connect(self):
        """Start server connection in reconnect mode"""
        # Enable reconnect flag
        self.reconnect = True
        self.log_info(f"{self.name} connect()")
        # 재연결이 비활성화되면 반환
        if not self.reconnect:
            self.log_debug(f"{self.name} connect() -- reconnect disabled")
            return
        # Return if already connected
        if self.connected:
            self.log_debug(f"{self.name} connect() -- already connected")
            return
        # 연결 스레드가 없거나 실행 중이 아니면 새 스레드 생성
        if not self.connect_thread or not self.connect_thread.is_alive():
            self.connect_thread = threading.Thread(target=self._connect, daemon=True)
            self.connect_thread.start()

    def _connect(self):
        """서버에 연결을 시도하고 실패 시 주기적으로 재시도"""
        # 연결될 때까지 반복 시도
        while not self.connected:
            try:
                # 서버에 연결 시도
                self.socket = socket.create_connection((self.ip, self.port))
                if self.socket:
                    # 재연결 모드가 아니면 수신 타임아웃 설정
                    if not self.reconnect:
                        self.socket.settimeout(self.timeout_send_once)
                    # 연결 상태 업데이트
                    self.connected = True
                    # 수신 스레드 시작
                    self._run_thread_receive()
            except ConnectionRefusedError:
                # Connection refused by server
                self.log_error(f"{self.name} _connect() -- connection refused")
                time.sleep(self.reconnect_time)
                # 재연결이 비활성화되면 루프 종료
                if not self.reconnect:
                    break
            except TimeoutError:
                # Connection timeout occurred
                self.log_error(f"{self.name} _connect() -- connection timeout")
                time.sleep(self.reconnect_time)
                if not self.reconnect:
                    break
            except Exception as e:
                # 기타 예외 발생한 경우
                self.log_error(f"{self.name} _connect() {e=}")
                time.sleep(self.reconnect_time)
                if not self.reconnect:
                    break

    def disconnect(self):
        """서버와의 연결 종료"""
        # 재연결 플래그 비활성화
        self.reconnect = False
        if self.socket:
            try:
                # 소켓의 읽기/쓰기 모두 종료
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError as e:
                self.log_error(f"{self.name} disconnect() -- socket shutdown failed {e=}")
            finally:
                self.socket.close()  # 소켓 닫기
        self.connected = False
        self.socket = None
        # 연결 스레드 종료 대기 (현재 스레드 제외)
        if self.connect_thread and self.connect_thread.is_alive() and threading.current_thread() != self.connect_thread:
            try:
                self.connect_thread.join(timeout=1.0)
            except RuntimeError as e:
                self.log_error(f"{self.name} disconnect() -- connect_thread join failed: {e=}")
        # Wait for receive thread to end (except current thread)
        if self.receive_thread and self.receive_thread.is_alive() and threading.current_thread() != self.receive_thread:
            try:
                self.receive_thread.join(timeout=1.0)
            except RuntimeError as e:
                self.log_error(f"{self.name} disconnect() -- receive_thread join failed {e=}")
        self.log_info(f"{self.name} disconnect() connection stopped -- reconnect disabled")

    def handle_reconnect(self):
        """재연결 플래그가 활성화되어 있으면 재연결 시도"""
        if self.reconnect:
            self.connect()

    def _run_thread_receive(self):
        """수신 스레드 시작 (중복 실행 방지)"""
        if not self.receive_thread or not self.receive_thread.is_alive():
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()

    def _receive_loop(self):
        """서버로부터 데이터 수신 루프"""
        if self.debug:
            self.log_debug(f"{self.name} _receive_loop() -- thread started")
        self.emit("connected")
        self.emit("online")
        while self.connected:
            try:
                if not self.socket:
                    self.log_error(f"{self.name} _receive_loop() -- socket initialization needed")
                else:
                    # 서버로부터 데이터 수신
                    data = self.socket.recv(self.buffer_size)
                    if data:
                        if self.debug:
                            self.log_debug(f"{self.name} _receive_loop() -- received {data=}")
                        # Create event object and emit received data event
                        event = SimpleNamespace()
                        event.source = self
                        event.arguments = {"data": data}
                        self.emit("received", event)
                    else:
                        # 데이터가 없음 = 서버가 연결을 종료함
                        self.connected = False
                        self.log_info(f"{self.name} _receive_loop() -- no data received, connection closed")
                        self.handle_reconnect()
                        break
            except socket.timeout:
                # 데이터 없음 타임아웃: 재연결 모드면 무시
                self.connected = False
                if not self.reconnect:
                    self.disconnect()
                    break
                # 재연결 모드 시 timeout 무시하고 계속
                continue
            except Exception as e:
                self.connected = False
                self.log_error(f"{self.name} _receive_loop() -- {e=}")
                self.handle_reconnect()
                break
        self.log_debug(f"{self.name} _receive_loop() -- thread ended")

    def send(self, message: bytes | bytearray | str):
        """메시지 전송 (재연결 모드 또는 일회성 전송)"""
        if isinstance(message, str):
            message = message.encode()
        # 재연결 모드: 지속적인 연결 유지
        if self.reconnect:
            if self.socket and self.connected:
                try:
                    if self.debug:
                        self.log_debug(f"{self.name} send() sending -- {message=}")
                    self.socket.sendall(message)
                except Exception as e:
                    self.log_error(f"{self.name} send() failed to send {e=}")
                    self.connected = False
                    self.log_warn(f"{self.name} send() -- connection closed. Attempting reconnect after {self.reconnect_time} seconds.")

                    # 지정된 시간 대기 후 재연결 시도
                    def wait_and_reconnect():
                        time.sleep(self.reconnect_time)
                        if self.reconnect:  # reconnect 플래그 확인 후 재연결 시도
                            self.handle_reconnect()

                    threading.Thread(target=wait_and_reconnect, daemon=True).start()
        else:
            # 일회성 전송 모드: 매번 새로운 연결 생성
            def send_once():
                try:
                    # 연결 생성 및 데이터 전송
                    sock = socket.create_connection((self.ip, self.port), timeout=self.timeout_send_once)
                    sock.sendall(message)
                    if self.debug:
                        self.log_debug(f"{self.name} send_once() -- sending {message=}")
                    try:
                        sock.settimeout(self.timeout_send_once)
                        # 서버의 응답 대기
                        data = sock.recv(self.buffer_size)
                        if data:
                            if self.debug:
                                self.log_debug(f"{self.name} send_once() -- received {data=}")
                            # Create event object and emit received data event
                            event = SimpleNamespace()
                            event.source = self
                            event.arguments = {"data": data}
                            self.emit("received", event)
                        else:
                            self.log_info(f"{self.name} send_once() -- connection closed by server, no response received")
                    except socket.timeout:
                        # No response received within timeout
                        self.log_info(f"{self.name} send_once() -- no response received within {self.timeout_send_once} seconds")
                    finally:
                        sock.close()
                        self.log_info(f"{self.name} send_once() -- connection closed")
                except Exception as e:
                    self.log_error(f"{self.name} send_once() -- failed to send {e=}")

            # 일회성 전송을 독립적인 스레드에서 실행
            threading.Thread(target=send_once).start()

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
        ip,
        port,
        connection_timeout=60.0,
        buffer_size=DEFAULT_BUFFER_SIZE,
        bound_port=None,
        name=None,
    ):
        super().__init__("connected", "received")
        self.debug = False
        self.name = name or f"udp:{ip}:{port}"
        self.ip = ip
        self.port = port
        self.receive = self.ReceiveHandler(self)
        self.buffer_size = buffer_size
        self.connected = False
        self.socket: socket.socket | None = None
        self.receive_thread: threading.Thread | None = None
        self.monitor_thread: threading.Thread | None = None
        # 클라이언트가 바인드할 로컬 포트 (None이면 OS가 자동 할당)
        self.bound_port: int | None = bound_port
        # 실제 바인드된 포트 번호
        self.bind_port: int | None = None
        # 마지막 패킷 수신 시간 (연결 타임아웃 감지용)
        self.last_received_time = 0
        # 연결 타임아웃 시간 (초)
        self.connection_timeout = connection_timeout
        # 연결 모니터링 주기 (타임아웃의 절반)
        self.time_monitor_connection = float(self.connection_timeout // 2)

    def log_debug(self, message):
        if self.debug:
            print(f"{__class__.__name__} (DEBUG) -- {message}")

    def log_error(self, message):
        print(f"{__class__.__name__} (ERROR) -- {message}")

    def log_warn(self, message):
        print(f"{__class__.__name__} (WARN) -- {message}")

    def log_info(self, message):
        print(f"{__class__.__name__} (INFO) -- {message}")

    def connect(self):
        """Start UDP connection"""
        self.log_info(f"{self.name} connect() -- starting")
        try:
            # 이미 연결되어 있으면 반환
            if self.connected:
                return
            # 실제 연결 수행
            self._connect()
            # 연결 실패 시 반환
            if not self.connected:
                return
            # 연결 성공 시 수신 시간 초기화
            self.last_received_time = time.time()
            # 수신 스레드 시작 (중복 실행 방지)
            if not self.receive_thread or not self.receive_thread.is_alive():
                self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
                self.receive_thread.start()
            # 연결 모니터링 스레드 시작 (타임아웃 감지용)
            if not self.monitor_thread or not self.monitor_thread.is_alive():
                self.monitor_thread = threading.Thread(target=self._monitor_connection, daemon=True)
                self.monitor_thread.start()
        except Exception as e:
            self.log_error(f"{self.name} connect() -- failed to start {e=}")

    def _connect(self):
        """UDP 소켓 생성 및 바인드"""
        try:
            # UDP 소켓 생성
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # 소켓을 논블로킹 모드로 설정하고 타임아웃 1초로 설정
            self.socket.setblocking(False)
            self.socket.settimeout(1.0)
            # 로컬 포트에 바인드 (포트 미지정 시 OS가 자동 할당)
            self.socket.bind(("", 0 if self.bound_port is None else self.bound_port))
            # 바인딩된 실제 포트 번호 저장
            self.bind_port = self.socket.getsockname()[1]
            if self.debug:
                self.log_debug(f"{self.name} _connect() -- bound port: {self.bind_port}")
            # Update connection state
            self.connected = True
            # 연결 완료 이벤트 발생
            self.emit("connected")
            self.emit("online")
        except Exception as e:
            self.log_error(f"{self.name} _connect() -- failed to connect {e=}")
            self.connected = False

    def disconnect(self):
        """UDP 연결 종료"""
        self.connected = False
        # 수신 스레드 종료 대기
        if self.receive_thread and self.receive_thread.is_alive() and threading.current_thread() != self.receive_thread:
            try:
                self.receive_thread.join(timeout=1.0)
            except RuntimeError as e:
                self.log_error(f"{self.name} disconnect() -- receive_thread join {e=}")
        # Clean up socket
        if self.socket:
            try:
                self.socket.close()
            finally:
                self.socket = None
        self.log_info(f"{self.name} disconnect() -- connection stopped")

    def handle_reconnect(self):
        """연결 상태를 초기화하고 재연결 시도"""
        try:
            old_connected = self.connected
            self.connected = False
            if self.socket:
                try:
                    self.socket.close()
                except Exception as e:
                    self.log_error(f"{self.name} handle_reconnect() -- failed to close socket {e=}")
                finally:
                    self.socket = None
            # 이전에 연결되어 있었다면 재연결 시도
            if old_connected:
                # 잠시 대기 후 재연결 시도
                time.sleep(1.0)
                self.connect()
        except Exception as e:
            self.log_error(f"{self.name} handle_reconnect() -- failed to reconnect: {e=}")

    def send(self, msg: bytes | bytearray | str):
        """지정된 주소로 UDP 패킷 전송"""
        if self.socket and self.connected:
            try:
                if isinstance(msg, str):
                    msg = msg.encode()
                self.socket.sendto(msg, (self.ip, self.port))
                if self.debug:
                    self.log_debug(f"{self.name} send() -- sending - {msg=}")
            except Exception as e:
                self.log_error(f"{self.name} send() -- failed to send: {e=}")

    def _receive_loop(self):
        """UDP 패킷 수신 루프"""
        if self.debug:
            self.log_debug(f"{self.name} _receive_loop() -- thread started")
        while self.connected:
            try:
                if not self.socket:
                    self.log_error(f"{self.name} _receive_loop() -- socket initialization needed")
                    break
                # UDP 패킷 수신 및 발신자 주소 획득
                data, addr = self.socket.recvfrom(self.buffer_size)
                # 수신 시간 업데이트 (연결 타임아웃 감지용)
                self.last_received_time = time.time()
                if self.debug:
                    self.log_debug(f"{self.name} _receive_loop() -- received - {data=} {addr=}")
                # Create event object and emit received data event
                event = SimpleNamespace()
                event.source = self
                event.arguments = {"data": data, "address": addr}
                self.emit("received", event)
            except socket.timeout:
                # 타임아웃 발생 시 계속 수신 대기
                continue
            except OSError as e:
                if self.connected:
                    self.log_error(f"{self.name} _receive_loop() -- socket {e=}")
                break
            except Exception as e:
                if self.connected:
                    self.log_error(f"{self.name} _receive_loop() -- receiving message {e=}")
                break
        if self.debug:
            self.log_debug(f"{self.name} _receive_loop() -- thread ended")

    def _monitor_connection(self):
        """연결 타임아웃을 감지하고 필요시 재연결 수행"""
        if self.debug:
            self.log_debug(f"{self.name} _monitor_connection() -- thread started")
        while self.connected:
            try:
                current_time = time.time()
                # 모니터링 주기만큼 대기
                time.sleep(self.time_monitor_connection)
                if self.debug:
                    self.log_debug(f"{self.name} _monitor_connection() {self.connected=} {self.last_received_time=} {current_time=}")
                # 마지막 수신 이후 타임아웃 시간 초과 시 재연결 시도
                if self.last_received_time > 0 and current_time - self.last_received_time > self.connection_timeout:
                    if self.debug:
                        self.log_debug(f"{self.name} _monitor_connection() -- connection timeout, attempting reconnect")
                    self.handle_reconnect()
            except Exception as e:
                if self.connected:
                    self.log_error(f"{self.name} _monitor_connection() -- monitoring {e=}")
                time.sleep(self.time_monitor_connection)
        if self.debug:
            self.log_debug(f"{self.name} _monitor_connection()-- thread ended")


# ---------------------------------------------------------------------------- #
class MulticastGroup(EventManager):
    class ReceiveHandler:
        def __init__(self, this):
            self.this = this

        def listen(self, listener):
            self.this.on("received", listener)

    def __init__(
        self,
        group_ip,
        port,
        buffer_size=DEFAULT_BUFFER_SIZE,
        bind_port=None,
        name=None,
        ttl=64,
        loopback=False,
        interface_ip="0.0.0.0",
    ):
        super().__init__("connected", "received", "online", "offline")
        self.debug = False
        self.name = name or f"mc:{group_ip}:{port}"
        self.group_ip = group_ip
        self.port = port
        # 멀티캐스트를 수신할 인터페이스 (0.0.0.0 = 기본 인터페이스)
        self.interface_ip = interface_ip
        self.buffer_size = buffer_size
        # Time To Live: 패킷이 라우팅될 수 있는 최대 홉(hop) 수
        self.ttl = ttl
        # 루프백: 자신이 보낸 패킷을 받을지 여부
        self.loopback = loopback
        self.bind_port = port if bind_port is None else bind_port
        self.socket: socket.socket | None = None
        self.receive = self.ReceiveHandler(self)
        self.receive_thread: threading.Thread | None = None
        self.connected = False
        # 멀티캐스트 그룹 멤버십 정보 (그룹 IP + 인터페이스 IP)
        self.membership = None

    def log_debug(self, message):
        if self.debug:
            print(f"{__class__.__name__} (DEBUG) -- {message}")

    def log_error(self, message):
        print(f"{__class__.__name__} (ERROR) -- {message}")

    def log_warn(self, message):
        print(f"{__class__.__name__} (WARN) -- {message}")

    def log_info(self, message):
        print(f"{__class__.__name__} (INFO) -- {message}")

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def join(self):
        """멀티캐스트 그룹에 가입"""
        self.connect()

    def connect(self):
        """Connect to multicast group"""
        self.log_info(f"{self.name} connect() -- starting")
        try:
            if self.connected:
                return
            # UDP 소켓 생성 (멀티캐스트용)
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            # 소켓 주소 재사용 허용 (이전 연결이 TIME_WAIT 상태일 때)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # 멀티캐스트 포트에 바인드
            try:
                self.socket.bind(("", self.bind_port))
            except OSError:
                self.socket.close()
                self.socket = None
                raise
            # 멀티캐스트 그룹 및 인터페이스를 바이너리 형태로 변환
            group_bin = socket.inet_aton(self.group_ip)
            interface_bin = socket.inet_aton(self.interface_ip)
            # 멤버십: 그룹 IP + 인터페이스 IP 결합
            self.membership = group_bin + interface_bin
            # 멀티캐스트 그룹에 가입 (IP_ADD_MEMBERSHIP)
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, self.membership)
            # 멀티캐스트 TTL 설정 - 패킷이 라우팅될 수 있는 네트워크 범위 제한
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.ttl)
            # 멀티캐스트 루프백 설정 (자신이 보낸 패킷을 받을지 여부)
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1 if self.loopback else 0)
            # 특정 네트워크 인터페이스가 지정된 경우 해당 인터페이스 설정
            if self.interface_ip != "0.0.0.0":
                self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, interface_bin)
            # 소켓을 논블로킹 모드로 설정하고 타임아웃 설정
            self.socket.setblocking(False)
            self.socket.settimeout(1.0)
            # 연결 상태 업데이트 및 이벤트 발생
            self.connected = True
            self.emit("connected")
            self.emit("online")
            # 수신 스레드 시작 (중복 실행 방지)
            if not self.receive_thread or not self.receive_thread.is_alive():
                self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
                self.receive_thread.start()
        except Exception as e:
            self.connected = False
            self.log_error(f"{self.name} connect() -- failed {e=}")

    def leave(self):
        """멀티캐스트 그룹에서 탈퇴"""
        self.disconnect()

    def disconnect(self):
        """멀티캐스트 그룹 연결 종료"""
        self.connected = False
        if self.socket:
            try:
                # 멀티캐스트 그룹에서 탈퇴 (IP_DROP_MEMBERSHIP)
                if self.membership:
                    self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, self.membership)
            except Exception as e:
                self.log_error(f"{self.name} disconnect() -- failed to leave group {e=}")
            try:
                self.socket.close()
            finally:
                self.socket = None
                self.membership = None
        # 수신 스레드 종료 대기 (현재 스레드 제외)
        if self.receive_thread and self.receive_thread.is_alive() and threading.current_thread() != self.receive_thread:
            try:
                self.receive_thread.join(timeout=1.0)
            except RuntimeError as e:
                self.log_error(f"{self.name} disconnect() -- receive_thread join failed {e=}")
        self.emit("offline")
        self.log_info(f"{self.name} disconnect() -- disconnected")

    def send(self, msg: bytes | bytearray | str):
        """멀티캐스트 그룹으로 메시지 전송"""
        if not self.socket or not self.connected:
            return
        try:
            if isinstance(msg, str):
                msg = msg.encode()
            self.socket.sendto(msg, (self.group_ip, self.port))
            if self.debug:
                self.log_debug(f"{self.name} send() -- sending {msg=}")
        except Exception as e:
            self.log_error(f"{self.name} send() -- failed to send {e=}")

    def _receive_loop(self):
        """멀티캐스트 패킷 수신 루프"""
        if self.debug:
            self.log_debug(f"{self.name} _receive_loop() -- thread started")
        while self.connected:
            try:
                if not self.socket:
                    break
                # 멀티캐스트 패킷 수신
                data, addr = self.socket.recvfrom(self.buffer_size)
                # 이벤트 객체 생성 및 수신 데이터 이벤트 발생
                event = SimpleNamespace()
                event.source = self
                event.arguments = {"data": data, "address": addr}
                self.emit("received", event)
                if self.debug:
                    self.log_debug(f"{self.name} _receive_loop() -- received {data=} {addr=}")
            except socket.timeout:
                # 타임아웃 발생 시 계속 수신 대기
                continue
            except OSError as e:
                if self.connected:
                    self.log_error(f"{self.name} _receive_loop() -- socket {e=}")
                break
            except Exception as e:
                if self.connected:
                    self.log_error(f"{self.name} _receive_loop() -- receiving {e=}")
                break
        if self.debug:
            self.log_debug(f"{self.name} _receive_loop() -- thread ended")
