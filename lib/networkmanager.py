import socket
import threading
import time
from types import SimpleNamespace
from typing import Any, Dict, Tuple

from mojo import context

from lib.eventmanager import EventManager

# ---------------------------------------------------------------------------- #
VERSION = "2026.04.10"


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
        self.name = name or f"TcpServer:{port}"
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

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def start(self):
        context.log.info(f"{self.name} start() 서버 시작")
        self.running = True
        if not self.server_thread or not self.server_thread.is_alive():
            self.server_thread = threading.Thread(target=self._start_server, daemon=True)
            self.server_thread.start()

    def _start_server(self):
        context.log.debug(f"{self.name} _start_server() 스레드 시작")
        time.sleep(1.0)
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # SO_REUSEADDR: 이전 연결이 TIME_WAIT 상태일 때 포트 재사용 가능하게 설정
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                self.socket.bind(("", self.port))
            except OSError as e:
                if e.errno == 98:  # 주소가 이미 사용 중인 경우
                    context.log.warn(f"{self.name} _start_server() 주소가 이미 사용중이며 무시")
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
                    context.log.debug(f"{self.name} _start_server() 클라이언트 접속 {address=}")
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
            context.log.error(f"{self.name} _start_server() 서버 시작 실패 에러: {e}")
            self.running = False
            if self.restart:
                # 자동 재시작 활성화 시 서버 재시작
                self.start()

    def stop(self):
        if self.debug:
            context.log.debug(f"{self.name} stop() 실행")
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
                context.log.error(f"{self.name} stop() 클라이언트 소켓 닫기 실패 에러: {e}")
        # 서버 소켓 종료
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except Exception as e:
                context.log.error(f"{self.name} stop() 서버 소켓 닫기 실패 에러: {e}")
        # 서버 스레드 종료 대기 (현재 스레드가 아닌 경우만)
        if self.server_thread and self.server_thread.is_alive() and threading.current_thread() != self.server_thread:
            try:
                # 최대 1초 대기 후 강제 종료
                self.server_thread.join(timeout=1.0)
            except RuntimeError as e:
                context.log.error(f"{self.name} stop() 서버 스레드 조인 실패 에러: {e}")
        context.log.info(f"{self.name} stop() 서버 중지")

    def _receive_loop(self, client_socket: socket.socket, address: Tuple[str, int]):
        context.log.debug(f"{self.name} _receive_loop() 시작 {address=}")
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
                    context.log.debug(f"{self.name} _receive_loop() 수신 -- {data=} {address=}")
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
            context.log.info(f"{self.name} _receive_loop() 클라이언트 연결 끊김 {address=}")
        except Exception as e:
            if self.running:
                context.log.error(f"{self.name} _receive_loop() 에러: {e}")
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
            context.log.info(f"{self.name} _receive_loop() 클라이언트 연결 종료 {address=}")

    def send_to(self, client_socket: socket.socket, data: bytes | bytearray):
        """특정 클라이언트 소켓으로 데이터 전송"""
        try:
            client_socket.sendall(data)
        except Exception as e:
            context.log.error(f"{self.name} send_to() 전송 실패 에러: {e}")

    def send(self, data: bytes | bytearray, exclude_client: tuple[str, int] | None = None):
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
            context.log.error(f"{self.name} send() 전송 실패 에러: {e}")

    def _cleanup_clients(self):
        """타임아웃된 클라이언트를 주기적으로 정리하는 스레드"""
        if self.debug:
            context.log.debug(f"{self.name} _cleanup_clients() 클라이언트 정리 스레드 시작")
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
                        context.log.debug(f"{self.name} _cleanup_clients() 비활성 클라이언트 제거: {client_addr=}")
                # 설정된 주기로 대기
                time.sleep(self.time_cleanup_clients)
            except Exception as e:
                context.log.error(f"{self.name} _cleanup_clients() 클라이언트 정리 에러: {e}")
                time.sleep(self.time_cleanup_clients)
        if self.debug:
            context.log.debug(f"{self.name} _cleanup_clients() 스레드 종료")

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
        self.name = name or f"UdpServer:{port}"
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

    def start(self):
        context.log.info(f"{self.name} start() 서버 시작")
        if self.running and self.socket:
            context.log.info(f"{self.name} start() 이미 실행 중")
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
                context.log.debug(f"{self.name} start() 서버 시작")
        except Exception as e:
            self.running = False
            context.log.error(f"{self.name} start() 서버 시작 실패 에러: {e}")

    def stop(self):
        self.running = False
        with self.client_lock:
            # 모든 클라이언트 정보 초기화
            self.clients.clear()
        if self.socket:
            try:
                self.socket.close()
            except Exception as e:
                context.log.error(f"{self.name} stop() 소켓 닫기 실패 에러: {e}")
            finally:
                self.socket = None
        # 수신 스레드 종료 대기
        if self.receive_thread and self.receive_thread.is_alive() and threading.current_thread() != self.receive_thread:
            try:
                self.receive_thread.join(timeout=1.0)
            except RuntimeError as e:
                context.log.error(f"{self.name} stop() 수신 스레드 조인 실패 에러: {e}")
        # 정리 스레드 종료 대기
        if self.cleanup_thread and self.cleanup_thread.is_alive() and threading.current_thread() != self.cleanup_thread:
            try:
                self.cleanup_thread.join(timeout=1.0)
            except RuntimeError as e:
                context.log.error(f"{self.name} stop() 정리 스레드 조인 실패 에러: {e}")
        context.log.info(f"{self.name} stop() 서버 중지")

    def _receive_loop(self):
        """UDP 패킷 수신 루프"""
        if self.debug:
            context.log.debug(f"{self.name} _receive_loop() 스레드 시작")
        while self.running:
            try:
                if not self.socket:
                    context.log.error(f"{self.name} 소켓 초기화 필요")
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
                    context.log.debug(f"{self.name} _receive_loop() 수신 -- {data=} {addr=}")
                # 이벤트 객체 생성 및 수신 데이터 이벤트 발생
                event = SimpleNamespace()
                event.source = self
                event.arguments = {"data": data, "address": addr}
                self.emit("received", event)
                # 에코 모드: 발신 클라이언트로 데이터 반송
                if self.echo:
                    self.socket.sendto(data, addr)
            except OSError as e:
                if self.running:
                    context.log.error(f"{self.name} _receive_loop() 소켓 에러: {e}")
                    # 에러 발생 시 복구를 위해 대기 후 재시도
                    time.sleep(1)
            except Exception as e:
                if self.running:
                    context.log.error(f"{self.name} _receive_loop() 메세지 수신 에러: {e}")
                    time.sleep(1)
        if self.debug:
            context.log.debug(f"{self.name} _receive_loop() 스레드 종료")

    def send_to(self, host: str, port: int, data: bytes | bytearray):
        """특정 주소의 클라이언트로 UDP 패킷 전송"""
        if not self.socket:
            return
        try:
            context.log.debug(f"{self.name} send_to() {host=} {port=} {data=}")
            self.socket.sendto(data, (host, port))
        except Exception as e:
            context.log.error(f"{self.name} send_to() 전송 실패 에러: {e}")

    def send(self, data: bytes | bytearray, exclude_client: tuple[str, int] | None = None):
        """지정된 클라이언트를 제외한 모든 클라이언트로 브로드캐스트"""
        with self.client_lock:
            try:
                for client_addr in self.clients:
                    # 제외 클라이언트가 아닌 경우만 전송
                    if client_addr != exclude_client:
                        self.send_to(client_addr[0], client_addr[1], data)
            except Exception as e:
                context.log.error(f"{self.name} send() {client_addr} 전송 실패 에러: {e}")

    def _cleanup_clients(self):
        """타임아웃된 UDP 클라이언트 주기적 정리"""
        if self.debug:
            context.log.debug(f"{self.name} _cleanup_clients() 클라이언트 정리 스레드 시작")
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
                            context.log.debug(f"{self.name} _cleanup_clients() 비활성 클라이언트 제거: {client_addr=}")
                        except KeyError:
                            # 클라이언트가 이미 제거된 경우
                            pass
                time.sleep(self.time_cleanup_clients)
            except Exception as e:
                context.log.error(f"{self.name} _cleanup_clients() 클라이언트 정리 에러: {e}")
                time.sleep(self.time_cleanup_clients)
        if self.debug:
            context.log.debug(f"{self.name} _cleanup_clients() 스레드 종료")

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
        self.name = name or f"TcpClient:{ip}:{port}"
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

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def connect(self):
        """재연결 모드로 서버 연결 시작"""
        # 재연결 플래그 활성화
        self.reconnect = True
        context.log.info(f"{self.name} connect() 연결 시작")
        # 재연결이 비활성화되면 반환
        if not self.reconnect:
            context.log.debug(f"{self.name} connect() reconnect 비활성화")
            return
        # 이미 연결되어 있으면 반환
        if self.connected:
            context.log.debug(f"{self.name} connect() 이미 연결됨")
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
                # 서버가 연결을 거부한 경우
                context.log.error(f"{self.name} _connect() 연결 거부")
                time.sleep(self.reconnect_time)
                # 재연결이 비활성화되면 루프 종료
                if not self.reconnect:
                    break
            except TimeoutError:
                # 연결 타임아웃 발생한 경우
                context.log.error(f"{self.name} _connect() 연결 타임아웃")
                time.sleep(self.reconnect_time)
                if not self.reconnect:
                    break
            except Exception as e:
                # 기타 예외 발생한 경우
                context.log.error(f"{self.name} _connect() 에러: {e}")
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
                print(f"소켓 shutdown 실패: {e}")
            finally:
                self.socket.close()  # 소켓 닫기
        self.connected = False
        self.socket = None
        # 연결 스레드 종료 대기 (현재 스레드 제외)
        if self.connect_thread and self.connect_thread.is_alive() and threading.current_thread() != self.connect_thread:
            try:
                self.connect_thread.join(timeout=1.0)
            except RuntimeError as e:
                context.log.error(f"{self.name} disconnect() connect_thread 조인 에러: {e}")
        # 수신 스레드 종료 대기 (현재 스레드 제외)
        if self.receive_thread and self.receive_thread.is_alive() and threading.current_thread() != self.receive_thread:
            try:
                self.receive_thread.join(timeout=1.0)
            except RuntimeError as e:
                context.log.error(f"{self.name} disconnect() receive_thread 조인 에러: {e}")
        context.log.info(f"{self.name} disconnect() 연결 중지 -- reconnect 해제")

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
            context.log.debug(f"{self.name} _receive_loop() 스레드 시작")
        self.emit("connected")
        self.emit("online")
        while self.connected:
            try:
                if not self.socket:
                    context.log.error(f"{self.name} _receive_loop() 소켓 초기화 필요")
                else:
                    # 서버로부터 데이터 수신
                    data = self.socket.recv(self.buffer_size)
                    if data:
                        if self.debug:
                            context.log.debug(f"{self.name} _receive_loop() 수신 -- {data=}")
                        # 이벤트 객체 생성 및 수신 데이터 이벤트 발생
                        event = SimpleNamespace()
                        event.source = self
                        event.arguments = {"data": data}
                        self.emit("received", event)
                    else:
                        # 데이터가 없음 = 서버가 연결을 종료함
                        self.connected = False
                        context.log.info(f"{self.name} connect() 수신 없음 연결 끊김")
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
                context.log.error(f"{self.name} _receive_loop() 에러: {e}")
                self.handle_reconnect()
                break
        context.log.debug(f"{self.name} _receive_loop() 스레드 종료")

    def send(self, message):
        """메시지 전송 (재연결 모드 또는 일회성 전송)"""
        # 재연결 모드: 지속적인 연결 유지
        if self.reconnect:
            if self.socket and self.connected:
                try:
                    if self.debug:
                        context.log.debug(f"{self.name} send() 송신 -- {message=}")
                    self.socket.sendall(message)
                except Exception as e:
                    context.log.error(f"{self.name} send() 송신 실패 에러: {e}")
                    self.connected = False
                    context.log.warn(f"{self.name} send() 연결 끊김. {self.reconnect_time}초 후 재연결 시도.")

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
                        context.log.debug(f"{self.name} send_once() 송신 -- {message=}")
                    try:
                        sock.settimeout(self.timeout_send_once)
                        # 서버의 응답 대기
                        data = sock.recv(self.buffer_size)
                        if data:
                            if self.debug:
                                context.log.debug(f"{self.name} send_once() 수신 -- {data=}")
                            # 이벤트 객체 생성 및 수신 데이터 이벤트 발생
                            event = SimpleNamespace()
                            event.source = self
                            event.arguments = {"data": data}
                            self.emit("received", event)
                        else:
                            context.log.info(f"{self.name} send_once() 서버에 의해 연결이 종료되어 응답을 받지 못함")
                    except socket.timeout:
                        # 타임아웃 시간 내 응답 미수신
                        context.log.info(f"{self.name} send_once() {self.timeout_send_once}초 이내에 응답을 받지 못함")
                    finally:
                        sock.close()
                        context.log.info(f"{self.name} send_once() 연결 닫힘")
                except Exception as e:
                    context.log.error(f"{self.name} send_once() 전송 실패 에러: {e=}")

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
        self.name = name or f"UdpClient:{ip}:{port}"
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

    def connect(self):
        """UDP 연결 시작"""
        context.log.info(f"{self.name} connect() 시작")
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
            context.log.error(f"{self.name} connect() 시작 실패 에러: {e}")

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
                context.log.debug(f"{self.name} _connect() 바인딩된 포트: {self.bind_port}")
            # 연결 상태 업데이트
            self.connected = True
            # 연결 완료 이벤트 발생
            self.emit("connected")
            self.emit("online")
        except Exception as e:
            context.log.error(f"{self.name} _connect() 연결 실패 에러: {e}")
            self.connected = False

    def disconnect(self):
        """UDP 연결 종료"""
        self.connected = False
        # 수신 스레드 종료 대기
        if self.receive_thread and self.receive_thread.is_alive() and threading.current_thread() != self.receive_thread:
            try:
                self.receive_thread.join(timeout=1.0)
            except RuntimeError as e:
                context.log.error(f"{self.name} disconnect() receive_thread 조인 에러: {e}")
        # 소켓 정리
        if self.socket:
            try:
                self.socket.close()
            finally:
                self.socket = None
        context.log.info(f"{self.name} disconnect() 연결 중지")

    def handle_reconnect(self):
        """연결 상태를 초기화하고 재연결 시도"""
        try:
            old_connected = self.connected
            self.connected = False
            if self.socket:
                try:
                    self.socket.close()
                except Exception as e:
                    context.log.error(f"{self.name} handle_reconnect() 소켓 닫기 실패 에러: {e}")
                finally:
                    self.socket = None
            # 이전에 연결되어 있었다면 재연결 시도
            if old_connected:
                # 잠시 대기 후 재연결 시도
                time.sleep(1.0)
                self.connect()
        except Exception as e:
            context.log.error(f"{self.name} handle_reconnect() 재연결 실패: {e}")

    def send(self, msg: bytes | bytearray):
        """지정된 주소로 UDP 패킷 전송"""
        if self.socket and self.connected:
            try:
                self.socket.sendto(msg, (self.ip, self.port))
                if self.debug:
                    context.log.debug(f"{self.name} send() 송신 - {msg=}")
            except Exception as e:
                context.log.error(f"{self.name} send() 송신 실패: {e}")

    def _receive_loop(self):
        """UDP 패킷 수신 루프"""
        if self.debug:
            context.log.debug(f"{self.name} _receive_loop() 스레드 시작")
        while self.connected:
            try:
                if not self.socket:
                    context.log.error(f"{self.name} 소켓 초기화 필요")
                    break
                # UDP 패킷 수신 및 발신자 주소 획득
                data, addr = self.socket.recvfrom(self.buffer_size)
                # 수신 시간 업데이트 (연결 타임아웃 감지용)
                self.last_received_time = time.time()
                if self.debug:
                    context.log.debug(f"{self.name} _receive_loop() 수신 - {data=} {addr=}")
                # 이벤트 객체 생성 및 수신 데이터 이벤트 발생
                event = SimpleNamespace()
                event.source = self
                event.arguments = {"data": data, "address": addr}
                self.emit("received", event)
            except socket.timeout:
                # 타임아웃 발생 시 계속 수신 대기
                continue
            except OSError as e:
                if self.connected:
                    context.log.error(f"{self.name} _receive_loop() 소켓 에러: {e}")
                break
            except Exception as e:
                if self.connected:
                    context.log.error(f"{self.name} _receive_loop() 메세지 수신 중 에러: {e}")
                break
        if self.debug:
            context.log.debug(f"{self.name} _receive_loop() 스레드 종료")

    def _monitor_connection(self):
        """연결 타임아웃을 감지하고 필요시 재연결 수행"""
        if self.debug:
            context.log.debug(f"{self.name} _monitor_connection() 스레드 시작")
        while self.connected:
            try:
                current_time = time.time()
                # 모니터링 주기만큼 대기
                time.sleep(self.time_monitor_connection)
                if self.debug:
                    context.log.debug(f"{self.connected=} {self.last_received_time=} {current_time=}")
                # 마지막 수신 이후 타임아웃 시간 초과 시 재연결 시도
                if self.last_received_time > 0 and current_time - self.last_received_time > self.connection_timeout:
                    if self.debug:
                        context.log.debug(f"{self.name} _monitor_connection() 연결 타임아웃, 연결 재시도")
                    self.handle_reconnect()
            except Exception as e:
                if self.connected:
                    context.log.error(f"{self.name} _monitor_connection() 모니터링 중 에러: {e}")
                time.sleep(self.time_monitor_connection)
        if self.debug:
            context.log.debug(f"{self.name} _monitor_connection() 스레드 종료")


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
        self.name = name or f"UdpMulticast:{group_ip}:{port}"
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

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def join(self):
        """멀티캐스트 그룹에 가입"""
        self.connect()

    def connect(self):
        """멀티캐스트 그룹 연결"""
        context.log.info(f"{self.name} connect() 시작")
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
            context.log.error(f"{self.name} connect() 실패: {e}")

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
                context.log.error(f"{self.name} disconnect() 그룹 탈퇴 실패: {e}")
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
                context.log.error(f"{self.name} disconnect() receive_thread 조인 실패: {e}")
        self.emit("offline")
        context.log.info(f"{self.name} disconnect() 종료")

    def send(self, msg: bytes | bytearray):
        """멀티캐스트 그룹으로 메시지 전송"""
        if not self.socket or not self.connected:
            return
        try:
            self.socket.sendto(msg, (self.group_ip, self.port))
            if self.debug:
                context.log.debug(f"{self.name} send() 송신 - {msg=}")
        except Exception as e:
            context.log.error(f"{self.name} send() 송신 실패: {e}")

    def _receive_loop(self):
        """멀티캐스트 패킷 수신 루프"""
        if self.debug:
            context.log.debug(f"{self.name} _receive_loop() 스레드 시작")
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
                    context.log.debug(f"{self.name} _receive_loop() 수신 - {data=} {addr=}")
            except socket.timeout:
                # 타임아웃 발생 시 계속 수신 대기
                continue
            except OSError as e:
                if self.connected:
                    context.log.error(f"{self.name} _receive_loop() 소켓 에러: {e}")
                break
            except Exception as e:
                if self.connected:
                    context.log.error(f"{self.name} _receive_loop() 수신 에러: {e}")
                break
        if self.debug:
            context.log.debug(f"{self.name} _receive_loop() 스레드 종료")
