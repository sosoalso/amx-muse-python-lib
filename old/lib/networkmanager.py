# 마지막 수정일 : 20260514
import atexit
import socket
import threading
import time
from types import SimpleNamespace
from typing import Any, Dict, Tuple, Callable
from lib.eventmanager import EventManager
from lib.utility import CommonLogger, run_thread, start_thread, join_thread


class ReceiveListener:
    def __init__(self, register_listener: Callable):
        self._register_listener = register_listener

    def listen(self, listener):
        self._register_listener(listener)


DEFAULT_BUFFER_SIZE = 2048


# section: TcpServer
class TcpServer(CommonLogger, EventManager):
    def __init__(self, port, buffer_size=DEFAULT_BUFFER_SIZE, name=None):
        super().__init__("received", "online", "offline", "connected", "disconnected")
        self.port = port
        self.name = name or f"tcp_server:{port}"
        self.buffer_size = buffer_size
        self.socket: socket.socket | None = None
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.running = False
        self.clients: Dict[Tuple[str, int], Dict[str, Any]] = {}  # 클라이언트 주소를 키로 하고 소켓 정보를 값으로 저장하는 딕셔너리
        self.client_timeout = 60.0  # 클라이언트의 타임아웃 시간 (초)
        self.time_cleanup_clients = float(self.client_timeout // 2)  # 클라이언트 정리 작업 수행 간격 (타임아웃의 절반)
        self.echo = False
        self.restart = True
        self._thread_start_server: threading.Thread | None = None
        self._thread_cleanup_clients: threading.Thread | None = None
        self._thread_receive_loop: threading.Thread | None = None
        self._client_lock = threading.Lock()  # 클라이언트 딕셔너리 접근 시 스레드 안전성을 위한 락

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def is_running(self):
        return self.running

    def start(self):
        """서버 시작"""
        self.log_info("start()")
        self.running = True
        self._thread_start_server = run_thread(self._thread_start_server, self._start_server)

    def stop(self):
        """서버 중지"""
        self.running = False
        self._close_all_clients()
        self._close_server_socket()
        join_thread(self._thread_start_server)
        self.log_info("stop() server stopped")

    def send_to(self, client_socket: socket.socket, data: bytes | bytearray | str):
        """특정 클라이언트 소켓으로 데이터 전송"""
        try:
            if isinstance(data, str):
                data = data.encode()
            client_socket.sendall(data)
        except Exception as e:
            self.log_error(f"send_to() failed to send {e=}")

    def send(self, data: bytes | bytearray | str, exclude_client: tuple[str, int] | None = None):
        """지정된 클라이언트를 제외한 모든 클라이언트로 브로드캐스트"""
        try:
            with self._client_lock:
                clients_copy = dict(self.clients)  # 락 안에서 복사만 수행하고, 네트워크 I/O는 락 밖에서 수행
            for client_addr, client_info in clients_copy.items():
                if client_addr != exclude_client:
                    client_socket = client_info.get("socket")
                    if client_socket:
                        self.send_to(client_socket, data)
        except Exception as e:
            self.log_error(f"send() failed to send {e=}")

    def _is_address_in_use_error(self, error: OSError) -> bool:
        return error.errno in (48, 98) or getattr(error, "winerror", None) == 10048

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        event = SimpleNamespace()
        event.source = self
        event.arguments = {"data": data, "address": address}
        self.emit("received", event)

    def _close_all_clients(self):
        """모든 클라이언트 연결 종료"""
        with self._client_lock:
            addresses = list(self.clients.keys())  # 현재 클라이언트 주소 목록 복사
        for address in addresses:
            self._close_client(address, emit_events=False)  # 이벤트 없이 각 클라이언트 소켓 닫기

    def _close_client(self, address: Tuple[str, int], client_socket: socket.socket | None = None, *, emit_events: bool = True) -> bool:
        with self._client_lock:
            removed_client = self.clients.pop(address, None)
        socket_to_close = client_socket or (removed_client.get("socket") if removed_client else None)
        if socket_to_close:
            self._close_socket(socket_to_close)
        if removed_client and emit_events:
            self.emit("offline", address=address)
            self.emit("disconnected", address=address)
        return removed_client is not None

    def _close_socket(self, sock: socket.socket):
        """소켓 shutdown 및 close (OSError 무시)"""
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            sock.close()
        except OSError:
            pass

    def _close_server_socket(self):
        if self.socket:
            self._close_socket(self.socket)
            self.socket = None
            self._thread_cleanup_clients = run_thread(self._thread_cleanup_clients, self._cleanup_clients)

    def _start_server(self):
        self.log_debug("_start_server() thread start")
        time.sleep(1.0)
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # 이전 연결이 TIME_WAIT 상태일 때 포트 재사용 가능하게 설정
            try:
                self.socket.bind(("", self.port))
            except OSError as e:
                if self._is_address_in_use_error(e):
                    self.log_warn("_start_server() Address already in use, ignoring")
                else:
                    self.log_error(f"_start_server() failed to bind {e=}")
                    self.running = False
                return
            self.socket.listen()  # 서버 소켓을 리스닝 상태로 변경
            self._thread_cleanup_clients = run_thread(self._thread_cleanup_clients, self._cleanup_clients)
            while self.running:  # 클라이언트 연결을 무한으로 수락하는 루프
                try:
                    client, address = self.socket.accept()
                    self.log_debug(f"_start_server() client connected {address=}")
                    with self._client_lock:
                        self.clients[address] = {"socket": client, "last_seen": time.time()}  # 새로운 클라이언트 정보 저장 (소켓, 마지막 수신 시간)
                    self.emit("connected", address=address)
                    self.emit("online", address=address)
                    self._thread_receive_loop = run_thread(self._thread_receive_loop, self._receive_loop, (client, address))
                except OSError:  # 소켓이 닫혀 있을 경우 발생할 수 있음
                    self.running = False
                    break
        except Exception as e:
            self.log_error(f"_start_server() server start failed {e=}")
            self.running = False
            if self.restart:
                self.start()  # 자동 재시작 활성화 시 서버 재시작

    def _receive_loop(self, client_socket: socket.socket, address: Tuple[str, int]):
        self.log_debug(f"_receive_loop() {address=}")
        try:
            while self.running:
                data = client_socket.recv(self.buffer_size)  # 클라이언트로부터 데이터 수신
                if not data:
                    break  # 클라이언트에 의해 연결이 정상 종료됨
                last_seen = time.time()
                with self._client_lock:
                    if address in self.clients:
                        self.clients[address]["last_seen"] = last_seen  # 클라이언트의 마지막 수신 시간 업데이트 (타임아웃 감지용)
                self.log_debug(f"_receive_loop() {data=} {address=}")
                self._emit_received(data, address)
                if self.echo:
                    client_socket.sendall(data)  # 에코 모드 활성화 시 수신한 데이터를 그대로 송신
        except (ConnectionResetError, BrokenPipeError):
            self.log_info(f"_receive_loop() Client disconnected {address=}")
        except Exception as e:
            if self.running:
                self.log_error(f"_receive_loop() {e=}")
        finally:
            removed = self._close_client(address, client_socket)
            if removed:
                self.log_info(f"_receive_loop() Client connection closed {address=}")

    def _cleanup_clients(self):
        """타임아웃된 클라이언트를 주기적으로 정리하는 스레드"""
        self.log_debug("_cleanup_clients() client cleanup thread started")
        while self.running:
            try:
                current_time = time.time()
                expired_sockets: list[tuple[Tuple[str, int], socket.socket]] = []
                with self._client_lock:
                    for client_addr, client_info in self.clients.items():  # 타임아웃 조건을 만족하는 클라이언트 찾기
                        if current_time - client_info["last_seen"] > self.client_timeout:  # 마지막 수신 이후 타임아웃 시간 초과 확인
                            client_socket = client_info.get("socket")
                            if client_socket:
                                expired_sockets.append((client_addr, client_socket))
                for client_addr, client_socket in expired_sockets:  # 타임아웃된 클라이언트 소켓만 닫고, 상태 정리는 수신 스레드 finally에 맡김
                    self._close_socket(client_socket)
                    self.log_debug(f"_cleanup_clients() closed inactive client socket: {client_addr=}")
                time.sleep(self.time_cleanup_clients)  # 설정한 대기시간 만큼 대기
            except Exception as e:
                self.log_error(f"_cleanup_clients() client cleanup {e=}")
                time.sleep(self.time_cleanup_clients)
        self.log_debug("_cleanup_clients() thread ended")


# section: UdpServer
class UdpServer(CommonLogger, EventManager):
    def __init__(self, port, buffer_size=DEFAULT_BUFFER_SIZE, name=None):
        super().__init__("received", "online", "offline")
        self.name = name or f"udp_server:{port}"
        self.port = port
        self.buffer_size = buffer_size
        self.socket: socket.socket | None = None
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.running = False
        self.clients: Dict[Tuple[str, int], float] = {}  # UDP 클라이언트 주소와 마지막 수신 시간을 저장
        self.client_timeout = 60.0
        self.time_cleanup_clients = float(self.client_timeout // 2)
        self.echo = False
        self._thread_receive_loop: threading.Thread | None = None
        self._thread_cleanup_clients: threading.Thread | None = None
        self._client_lock = threading.Lock()

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def is_running(self):
        return self.running

    def start(self):
        self.log_info("start() server starting")
        if self.running and self.socket:
            self.log_info("start() already running")
            return
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP 소켓 생성
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)  # SO_REUSEADDR: 빠른 재시작을 위해 포트 재사용 허용
            self.socket.bind(("", self.port))  # 모든 인터페이스의 지정 포트에 바인드
            self.running = True
            self._thread_receive_loop = run_thread(self._thread_receive_loop, self._receive_loop)
            self._thread_cleanup_clients = run_thread(self._thread_cleanup_clients, self._cleanup_clients)
        except Exception as e:
            self.running = False
            self.log_error(f"start() failed to start server {e=}")

    def stop(self):
        was_running = self.running
        self.running = False
        with self._client_lock:
            self.clients.clear()  # 모든 클라이언트 정보 초기화
        self._close_server_socket()
        join_thread(self._thread_receive_loop)
        join_thread(self._thread_cleanup_clients)
        if was_running:
            self.emit("offline")
        self.log_info("stop() server stopped")

    def send_to(self, host: str, port: int, data: bytes | bytearray | str):
        """특정 주소의 클라이언트로 UDP 패킷 전송"""
        if not self.socket:
            return
        try:
            self.log_debug(f"send_to() {host=} {port=} {data=}")
            if isinstance(data, str):
                data = data.encode()
            self.socket.sendto(data, (host, port))
        except Exception as e:
            self.log_error(f"send_to() failed to send {e=}")

    def send(self, data: bytes | bytearray | str, exclude_client: tuple[str, int] | None = None):
        """지정된 클라이언트를 제외한 모든 클라이언트로 브로드캐스트"""
        try:
            with self._client_lock:
                client_addrs = list(self.clients.keys())
            for client_addr in client_addrs:
                if client_addr != exclude_client:
                    self.send_to(client_addr[0], client_addr[1], data)
        except Exception as e:
            self.log_error(f"send() failed to send {e=}")

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        event = SimpleNamespace()
        event.source = self
        event.arguments = {"data": data, "address": address}
        self.emit("received", event)

    def _receive_loop(self):
        """UDP 패킷 수신 루프"""
        self.log_debug("_receive_loop() thread started")
        while self.running:
            try:
                if not self.socket:
                    self.log_error("_receive_loop() socket initialization needed")
                    break
                # UDP는 비연결형이므로 recvfrom으로 발신자 주소와 함께 수신
                data, addr = self.socket.recvfrom(self.buffer_size)
                if not data:
                    continue
                last_seen = time.time()
                with self._client_lock:
                    # UDP 클라이언트의 마지막 수신 시간 기록
                    self.clients[addr] = last_seen
                self.log_debug(f"_receive_loop() received {data=} {addr=}")
                self._emit_received(data, addr)
                # 에코 모드: 발신 클라이언트로 데이터 반송
                if self.echo:
                    self.socket.sendto(data, addr)
            except OSError as e:
                if self.running:
                    self.log_error(f"_receive_loop() socket {e=}")
                    # Wait and retry on error for recovery
                    time.sleep(1)
            except Exception as e:
                if self.running:
                    self.log_error(f"_receive_loop() message receive {e=}")
                    time.sleep(1)
        self.log_debug("_receive_loop() thread ended")

    def _cleanup_clients(self):
        """타임아웃된 UDP 클라이언트 주기적 정리"""
        self.log_debug("_cleanup_clients() client cleanup thread started")
        while self.running:
            try:
                current_time = time.time()
                with self._client_lock:
                    expired_clients = []
                    for client_addr, last_seen in self.clients.items():  # 타임아웃된 클라이언트 찾기
                        if current_time - last_seen > self.client_timeout:
                            expired_clients.append(client_addr)
                    for client_addr in expired_clients:
                        try:
                            del self.clients[client_addr]  # 타임아웃된 클라이언트 제거
                            self.emit("offline", address=client_addr)
                            self.log_debug(f"_cleanup_clients() removed inactive client: {client_addr=}")
                        except KeyError:  # 클라이언트가 이미 제거된 경우
                            pass
                time.sleep(self.time_cleanup_clients)
            except Exception as e:
                self.log_error(f"_cleanup_clients() client cleanup {e=}")
                time.sleep(self.time_cleanup_clients)

    def _close_server_socket(self):
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                self.log_error(f"_close_server_socket() failed to close socket {e=}")
            finally:
                self.socket = None


# section: TcpClient
class TcpClient(CommonLogger, EventManager):
    def __init__(self, ip, port, reconnect_time=30.0, buffer_size=DEFAULT_BUFFER_SIZE, name=None):
        super().__init__("disconnected", "connected", "received", "online", "offline")
        self.name = name or f"tcp:{ip}:{port}"
        self.ip = ip
        self.port = port
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.reconnect_time = reconnect_time  # 연결 재시도 간격 (초)
        self.timeout_send_once = 1.0  # 일회성 전송 모드에서 응답 대기 타임아웃
        self.buffer_size = buffer_size
        self.connected = False
        self.socket: socket.socket | None = None
        self._thread_connect: threading.Thread | None = None
        self._thread_receive_loop: threading.Thread | None = None
        # 자동 재연결 활성화 플래그
        self.reconnect = False
        self.last_received_time = 0
        atexit.register(self.disconnect)

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def is_connected(self):
        return self.connected

    def connect(self):
        """재접속 가능 모드로 변경하고 서버에 연결"""
        self.log_info("connect()")
        self.reconnect = True
        if self.connected:  # 이미 접속했다면 리턴
            self.log_debug("connect() already connected")
            return
        self._thread_connect = run_thread(self._thread_connect, self._connect)

    def _wait_and_reconnect(self):
        self.log_debug(f"_wait_and_reconnect() waiting for {self.reconnect_time} seconds before reconnect")
        self._wait_reconnect_interval()
        self._handle_reconnect()

    def _wait_reconnect_interval(self) -> bool:
        time.sleep(self.reconnect_time)
        return self.reconnect

    def _handle_reconnect(self):
        """재연결 플래그가 활성화되어 있으면 재연결 스케줄링"""
        self.log_debug("_handle_reconnect() handling reconnect")
        if self.reconnect:
            self.connect()

    def _close_current_socket(self):
        if self.socket:
            self._close_socket(self.socket, error_context="_close_current_socket()")
        self.socket = None

    def _close_socket(self, sock: socket.socket, error_context: str | None = None):
        try:
            sock.shutdown(socket.SHUT_RDWR)  # 소켓의 읽기/쓰기 모두 종료
        except OSError as e:
            if error_context:
                self.log_error(f"{error_context} socket shutdown failed {e=}")
        try:
            sock.close()  # 소켓 닫기
        except OSError as e:
            if error_context:
                self.log_error(f"{error_context} socket close failed {e=}")

    # 접속 관리
    def _connect(self):
        """서버에 연결을 시도하고 실패 시 주기적으로 재시도"""
        while not self.connected:  # 연결될 때까지 반복 시도
            try:
                self.log_debug(f"_connect() attempting to connect reconnect_time={self.reconnect_time}")
                self.socket = socket.create_connection((self.ip, self.port))  # 서버에 연결 시도
                if self.socket:
                    self._set_state_connected()
                    self._thread_receive_loop = run_thread(self._thread_receive_loop, self._receive_loop)  # 수신 스레드 시작
                    break
            except ConnectionRefusedError:
                self.log_error("_connect() connection refused by server")
                if not self._wait_reconnect_interval():
                    break
            except TimeoutError:
                self.log_error("_connect() connection timeout occurred")
                if not self._wait_reconnect_interval():
                    break
            except Exception as e:
                # 기타 예외 발생한 경우
                self.log_error(f"_connect() {e=}")
                if not self._wait_reconnect_interval():
                    break

    def _set_state_connected(self):
        self.connected = True
        self.emit("connected")
        self.emit("online")

    def _set_state_disconnected(self):
        was_connected = self.connected
        self.connected = False
        if was_connected:
            self.emit("offline")
            self.emit("disconnected")
        return was_connected

    def _receive_loop(self):
        """서버로부터 데이터 수신 루프"""
        self.log_debug("_receive_loop() thread started")
        while self.connected:
            try:
                if not self.socket:
                    self.log_error("_receive_loop() socket initialization needed")
                    self._set_state_disconnected()
                    break
                # 서버로부터 데이터 수신
                data = self.socket.recv(self.buffer_size)
                if data:
                    self.log_debug(f"_receive_loop() received {data=}")
                    self._emit_received(data, address=(self.ip, self.port))
                else:
                    # 데이터가 없음 = 서버가 연결을 종료함
                    self.log_info("_receive_loop() no data received, connection closed")
                    self._set_state_disconnected()
                    self._wait_and_reconnect()
                    break
            except socket.timeout:
                self._wait_and_reconnect()
            except Exception as e:
                self.log_error(f"_receive_loop() -- {e=}")
                self._set_state_disconnected()
                self._wait_and_reconnect()

    def disconnect(self):
        """서버와의 연결 종료"""
        self.log_info("disconnect()")
        self.reconnect = False  # 재연결 플래그 비활성화
        self._set_state_disconnected()
        self._close_current_socket()
        join_thread(self._thread_connect)  # 연결 스레드 종료 대기 (현재 스레드 제외)
        join_thread(self._thread_receive_loop)  # 수신 스레드 종료 대기 (현재 스레드 제외)
        self.log_info("disconnect() connection stopped reconnect disabled")

    def send(self, message: bytes | bytearray | str):
        """메시지 전송 (재연결 모드 또는 일회성 전송)"""
        if isinstance(message, str):
            message = message.encode()
        # 재연결 모드: 지속적인 연결 유지
        if self.reconnect:
            if not (self.socket and self.connected):
                return
            try:
                self.log_debug(f"send() sending {message=}")
                self.socket.sendall(message)
            except Exception as e:
                self.log_error(f"send() failed to send {e=}")
                was_connected = self._set_state_disconnected()
                if not was_connected:
                    return
                self.log_warn(f"send() connection closed. Attempting reconnect after {self.reconnect_time} seconds.")
                start_thread(self._wait_and_reconnect)
        else:
            start_thread(self._send_once, message)

    def _send_once(self, message: bytes | bytearray):  # 일회성 전송 모드: 매번 새로운 연결 생성
        try:
            # 연결 생성 및 데이터 전송
            sock = socket.create_connection((self.ip, self.port), timeout=self.timeout_send_once)
            sock.sendall(message)
            self.log_debug(f"_send_once() sending {message=}")
            try:
                sock.settimeout(self.timeout_send_once)  # 서버의 응답 대기
                data = sock.recv(self.buffer_size)  # 서버에서 응답 수신
                if data:
                    self.log_debug(f"_send_once() received {data=}")
                    self._emit_received(data, address=(self.ip, self.port))
                else:
                    self.log_info("_send_once() connection closed by server, no response received")
            except socket.timeout:
                self.log_info(f"_send_once() no response received within {self.timeout_send_once} seconds")
            finally:
                self._close_socket(sock, error_context="_send_once()")
                self.log_info("_send_once() connection closed")
        except Exception as e:
            self.log_error(f"_send_once() failed to send {e=}")

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        event = SimpleNamespace()
        event.source = self
        event.arguments = {"data": data, "address": address}
        self.emit("received", event)


# section: UdpClient
class UdpClient(CommonLogger, EventManager):
    def __init__(
        self,
        ip,
        port,
        connection_timeout=60.0,
        buffer_size=DEFAULT_BUFFER_SIZE,
        bound_port=None,
        name=None,
    ):
        super().__init__("connected", "received", "online", "offline", "disconnected")
        self.name = name or f"udp:{ip}:{port}"
        self.ip = ip
        self.port = port
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.buffer_size = buffer_size
        self.connected = False
        self.socket: socket.socket | None = None
        self.bound_port: int | None = bound_port  # 클라이언트가 바인드할 로컬 포트 (None이면 OS가 자동 할당)
        self.bind_port: int | None = None  # 실제 바인드된 포트 번호
        self.last_received_time = 0  # 마지막 패킷 수신 시간 (연결 타임아웃 감지용)
        self.connection_timeout = connection_timeout  # 연결 타임아웃 시간 (초)
        self.time_monitor_connection = float(self.connection_timeout // 2)  # 연결 모니터링 주기 (타임아웃의 절반)
        self._thread_receive_loop: threading.Thread | None = None
        self._thread_monitor_connection: threading.Thread | None = None

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def connect(self):
        """Start UDP connection"""
        self.log_info("connect() starting")
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
            # 스레드들 시작
            self._thread_receive_loop = run_thread(self._thread_receive_loop, self._receive_loop)
            self._thread_monitor_connection = run_thread(self._thread_monitor_connection, self._monitor_connection)
        except Exception as e:
            self.log_error(f"connect() failed to start {e=}")

    def disconnect(self):
        """UDP 연결 종료"""
        self._set_state_disconnected()
        join_thread(self._thread_receive_loop)
        join_thread(self._thread_monitor_connection)
        self._close_current_socket()
        self.log_info("disconnect() disconnected")

    def send(self, msg: bytes | bytearray | str):
        """지정된 주소로 UDP 패킷 전송"""
        if self.socket and self.connected:
            try:
                if isinstance(msg, str):
                    msg = msg.encode()
                self.socket.sendto(msg, (self.ip, self.port))
                self.log_debug(f"send() sending - {msg=}")
            except Exception as e:
                self.log_error(f"send() failed to send: {e=}")

    def _set_state_connected(self):
        self.connected = True
        self.emit("connected")
        self.emit("online")

    def _set_state_disconnected(self):
        was_connected = self.connected
        self.connected = False
        if was_connected:
            self.emit("offline")
            self.emit("disconnected")
        return was_connected

    def _connect(self):
        """UDP 소켓 생성 및 바인드"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP 소켓 생성
            self.socket.setblocking(False)  # 소켓을 논블로킹 모드로 설정
            self.socket.settimeout(1.0)  # 타임아웃 1초로 설정
            self.socket.bind(("", 0 if self.bound_port is None else self.bound_port))  # 로컬 포트에 바인드 (포트 미지정 시 OS가 자동 할당)
            self.bind_port = self.socket.getsockname()[1]  # 바인딩된 실제 포트 번호 저장
            self._set_state_connected()  # 연결 완료 이벤트 발생
            self.log_debug(f"_connect() bound port: {self.bind_port}")
        except Exception as e:
            self.connected = False
            self.log_error(f"_connect() failed to connect {e=}")

    def _handle_reconnect(self):
        """연결 상태를 초기화하고 재연결 시도"""
        try:
            old_connected = self._set_state_disconnected()
            self._close_current_socket(error_context="_handle_reconnect()")
            if old_connected:
                time.sleep(1.0)
                self.connect()  # 이전에 연결되어 있었다면 잠시 대기 후 재연결 시도
        except Exception as e:
            self.log_error(f"_handle_reconnect() failed to reconnect: {e=}")

    def _receive_loop(self):
        """UDP 패킷 수신 루프"""
        self.log_debug("_receive_loop() thread started")
        should_reconnect = False
        while self.connected:
            try:
                if not self.socket:
                    self.log_error("_receive_loop() socket initialization needed")
                    break
                data, addr = self.socket.recvfrom(self.buffer_size)  # UDP 패킷 수신 및 발신자 주소 획득
                self.last_received_time = time.time()  # 수신 시간 업데이트 (연결 타임아웃 감지용)
                self.log_debug(f"_receive_loop() received - {data=} {addr=}")
                self._emit_received(data, addr)
            except socket.timeout:
                continue  # 타임아웃 발생 시 계속 수신 대기
            except OSError as e:
                if self.connected:
                    self.log_error(f"_receive_loop() socket {e=}")
                    should_reconnect = True
                break
            except Exception as e:
                if self.connected:
                    self.log_error(f"_receive_loop() receiving message {e=}")
                    should_reconnect = True
                break
        if should_reconnect and self._set_state_disconnected():
            self._handle_reconnect()
        self.log_debug("_receive_loop() thread ended")

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        event = SimpleNamespace()
        event.source = self
        event.arguments = {"data": data, "address": address}
        self.emit("received", event)

    def _monitor_connection(self):
        """연결 타임아웃을 감지하고 필요시 재연결 수행"""
        while self.connected:
            try:
                current_time = time.time()
                # 모니터링 주기만큼 대기
                time.sleep(self.time_monitor_connection)
                self.log_debug(f"_monitor_connection() {self.connected=} {self.last_received_time=} {current_time=}")
                if self.last_received_time > 0 and current_time - self.last_received_time > self.connection_timeout:
                    self.log_debug("_monitor_connection() connection timeout, attempting reconnect")
                    self._handle_reconnect()  # 마지막 수신 이후 타임아웃 시간 초과 시 재연결 시도
            except Exception as e:
                if self.connected:
                    self.log_error(f"_monitor_connection() monitoring {e=}")
                time.sleep(self.time_monitor_connection)
        self.log_debug("_monitor_connection()-- thread ended")

    def _close_current_socket(self, error_context: str | None = None):
        if self.socket:
            self._close_socket(self.socket, error_context=error_context)
            self.socket = None

    def _close_socket(self, sock: socket.socket, error_context: str | None = None):
        try:
            sock.close()
        except OSError as e:
            if error_context:
                self.log_error(f"{error_context} failed to close socket {e=}")


class MulticastGroup(CommonLogger, EventManager):
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
        self.connected = False
        self.name = name or f"mc:{group_ip}:{port}"
        self.group_ip = group_ip
        self.port = port
        self.interface_ip = interface_ip  # 멀티캐스트를 수신할 인터페이스 (0.0.0.0 = 기본 인터페이스)
        self.buffer_size = buffer_size
        self.ttl = ttl  # Time To Live: 패킷이 라우팅될 수 있는 최대 홉(hop) 수
        self.loopback = loopback  # 루프백: 자신이 보낸 패킷을 받을지 여부
        self.bind_port = port if bind_port is None else bind_port
        self.socket: socket.socket | None = None
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.membership = None  # 멀티캐스트 그룹 멤버십 정보 (그룹 IP + 인터페이스 IP)
        self._thread_receive_loop: threading.Thread | None = None

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def join(self):
        """멀티캐스트 그룹에 가입 (connect() 호출)"""
        self.connect()

    def connect(self):
        """멀티캐스트 그룹에 가입"""
        self.log_info("connect() starting")
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
            group_bin = socket.inet_aton(self.group_ip)
            interface_bin = socket.inet_aton(self.interface_ip)
            # 멀티캐스트 그룹 및 인터페이스를 바이너리 형태로 변환
            self.membership = group_bin + interface_bin
            # 멤버십: 그룹 IP + 인터페이스 IP 결합
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, self.membership)  # 멀티캐스트 그룹에 가입 (IP_ADD_MEMBERSHIP)
            # 멀티캐스트 TTL 설정 - 패킷이 라우팅될 수 있는 네트워크 범위 제한
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.ttl)
            # 멀티캐스트 루프백 설정 (자신이 보낸 패킷을 받을지 여부)
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1 if self.loopback else 0)
            # 특정 네트워크 인터페이스가 지정된 경우 해당 인터페이스 설정
            if self.interface_ip != "0.0.0.0":
                self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, interface_bin)
            self.socket.setblocking(False)  # 소켓을 논블로킹 모드로 설정
            self.socket.settimeout(1.0)  #  타임아웃 설정
            self.connected = True
            self.emit("connected")
            self.emit("online")
            # 수신 스레드 시작 (중복 실행 방지)
            self._thread_receive_loop = run_thread(self._thread_receive_loop, self._receive_loop)
        except Exception as e:
            self.connected = False
            self.log_error(f"connect() failed {e=}")

    def leave(self):
        """멀티캐스트 그룹에서 탈퇴 (disconnect() 호출)"""
        self.disconnect()

    def disconnect(self):
        """멀티캐스트 그룹 연결 종료"""
        self.connected = False
        if self.socket:
            try:
                if self.membership:
                    # 멀티캐스트 그룹에서 탈퇴 (IP_DROP_MEMBERSHIP)
                    self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, self.membership)
            except Exception as e:
                self.log_error(f"disconnect() failed to leave group {e=}")
            self._close_socket(self.socket)
            self.socket = None
            self.membership = None
        # 수신 스레드 종료 대기 (현재 스레드 제외)
        join_thread(self._thread_receive_loop)
        self.emit("offline")
        self.log_info("disconnect() disconnected")

    def send(self, msg: bytes | bytearray | str):
        """멀티캐스트 그룹으로 메시지 전송"""
        if not self.socket or not self.connected:
            return
        try:
            if isinstance(msg, str):
                msg = msg.encode()
            self.socket.sendto(msg, (self.group_ip, self.port))
            self.log_debug(f"send() sending {msg=}")
        except Exception as e:
            self.log_error(f"send() failed to send {e=}")

    def _receive_loop(self):
        """멀티캐스트 패킷 수신 루프"""
        self.log_debug("_receive_loop() thread started")
        while self.connected:
            try:
                if not self.socket:
                    break
                # 멀티캐스트 패킷 수신
                data, addr = self.socket.recvfrom(self.buffer_size)
                # 이벤트 객체 생성 및 수신 데이터 이벤트 발생
                self._emit_received(data, addr)
                self.log_debug(f"_receive_loop() received {data=} {addr=}")
            except socket.timeout:
                # 타임아웃 발생 시 계속 수신 대기
                continue
            except OSError as e:
                if self.connected:
                    self.log_error(f"_receive_loop() socket {e=}")
                break
            except Exception as e:
                if self.connected:
                    self.log_error(f"_receive_loop() receiving {e=}")
                break
        self.log_debug("_receive_loop() thread ended")

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        event = SimpleNamespace()
        event.source = self
        event.arguments = {"data": data, "address": address}
        self.emit("received", event)

    def _close_socket(self, sock: socket.socket):
        try:
            sock.close()
        except OSError as e:
            self.log_error(f"disconnect() failed to close socket {e=}")
