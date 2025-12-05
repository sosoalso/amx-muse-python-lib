import socket
import threading
import time
from types import SimpleNamespace
from typing import Any, Dict, Tuple

from mojo import context

from lib.eventmanager import EventManager

VERSION = "2025.12.05"


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
        self.clients: Dict[Tuple[str, int], Dict[str, Any]] = {}
        self.client_lock = threading.Lock()
        self.client_timeout = 60.0
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
            if not self.cleanup_thread or not self.cleanup_thread.is_alive():
                self.cleanup_thread = threading.Thread(target=self._cleanup_clients, daemon=True)
                self.cleanup_thread.start()
            while self.running:
                try:
                    client, address = self.socket.accept()
                    context.log.debug(f"{self.name} _start_server() 클라이언트 접속 {address=}")
                    with self.client_lock:
                        self.clients[address] = {"socket": client, "last_seen": time.time()}
                    self.emit("connected", address=address)
                    self.emit("online", address=address)
                    threading.Thread(target=self._receive_loop, args=(client, address), daemon=True).start()
                except OSError:  # 소켓이 닫혀 있을 경우 발생할 수 있음
                    self.running = False
                    break
        except Exception as e:
            context.log.error(f"{self.name} _start_server() 서버 시작 실패 에러: {e}")
            self.running = False
            if self.restart:
                self.start()

    def stop(self):
        if self.debug:
            context.log.debug(f"{self.name} stop() 실행")
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
        context.log.info(f"{self.name} stop() 서버 중지")

    def _receive_loop(self, client_socket: socket.socket, address: Tuple[str, int]):
        context.log.debug(f"{self.name} _receive_loop() 시작 {address=}")
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
                if self.debug:
                    context.log.debug(f"{self.name} _receive_loop() 수신 -- {data=} {address=}")
                event = SimpleNamespace()
                event.source = self
                # if not isinstance(data, (bytes, bytearray)):
                #     data = str(data).encode()  # Ensure msg is in bytes
                event.arguments = {"data": data, "address": address}
                self.emit("received", event)
                if self.echo:
                    client_socket.sendall(data)
        except (ConnectionResetError, BrokenPipeError):
            context.log.info(f"{self.name} _receive_loop() 클라이언트 연결 끊김 {address=}")
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
            context.log.info(f"{self.name} _receive_loop() 클라이언트 연결 종료 {address=}")

    def send_to(self, client_socket: socket.socket, data: bytes | bytearray):
        try:
            client_socket.sendall(data)
        except Exception as e:
            context.log.error(f"{self.name} send_to() 전송 실패 에러: {e}")

    def send(self, data: bytes | bytearray, exclude_client: tuple[str, int] | None = None):
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
        if self.debug:
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
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(("", self.port))
            self.running = True
            if not self.receive_thread or not self.receive_thread.is_alive():
                self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
                self.receive_thread.start()
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
        context.log.info(f"{self.name} stop() 서버 중지")

    def _receive_loop(self):
        if self.debug:
            context.log.debug(f"{self.name} _receive_loop() 스레드 시작")
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
                if self.debug:
                    context.log.debug(f"{self.name} _receive_loop() 수신 -- {data=} {addr=}")
                event = SimpleNamespace()
                event.source = self
                # if not isinstance(data, (bytes, bytearray)):
                # data = str(data).encode()  # Ensure msg is in bytes
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
        if self.debug:
            context.log.debug(f"{self.name} _receive_loop() 스레드 종료")

    def send_to(self, host: str, port: int, data: bytes | bytearray):
        if not self.socket:
            return
        try:
            context.log.debug(f"{self.name} send_to() {host=} {port=} {data=}")
            self.socket.sendto(data, (host, port))
        except Exception as e:
            context.log.error(f"{self.name} send_to() 전송 실패 에러: {e}")

    def send(self, data: bytes | bytearray, exclude_client: tuple[str, int] | None = None):
        with self.client_lock:
            try:
                for client_addr in self.clients:
                    if client_addr != exclude_client:
                        self.send_to(client_addr[0], client_addr[1], data)
            except Exception as e:
                context.log.error(f"{self.name} send() {client_addr} 전송 실패 에러: {e}")

    def _cleanup_clients(self):
        if self.debug:
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
        self.reconnect_time = reconnect_time
        self.timeout_send_once = 1.0
        self.buffer_size = buffer_size
        self.connected = False
        self.socket: socket.socket | None = None
        self.connect_thread: threading.Thread | None = None
        self.receive_thread: threading.Thread | None = None
        self.reconnect = False
        self.last_received_time = 0

    def online(self, handler):
        self.on("online", handler)

    def offline(self, handler):
        self.on("offline", handler)

    def connect(self):
        self.reconnect = True
        context.log.info(f"{self.name} connect() 연결 시작")
        if not self.reconnect:
            context.log.debug(f"{self.name} connect() reconnect 비활성화")
            return
        if self.connected:
            context.log.debug(f"{self.name} connect() 이미 연결됨")
            return
        if not self.connect_thread or not self.connect_thread.is_alive():
            self.connect_thread = threading.Thread(target=self._connect, daemon=True)
            self.connect_thread.start()

    def _connect(self):
        while not self.connected:
            try:
                self.socket = socket.create_connection((self.ip, self.port))
                if self.socket:
                    if not self.reconnect:
                        self.socket.settimeout(self.timeout_send_once)  # reconnect 하지 않으면 수신 타임아웃 설정하기
                    self._run_thread_receive()
                    self.connected = True
            except ConnectionRefusedError:
                context.log.error(f"{self.name} _connect() 연결 거부")
                time.sleep(self.reconnect_time)
                if not self.reconnect:
                    break
            except TimeoutError:
                context.log.error(f"{self.name} _connect() 연결 타임아웃")
                time.sleep(self.reconnect_time)
                if not self.reconnect:
                    break
            except Exception as e:
                context.log.error(f"{self.name} _connect() 에러: {e}")
                time.sleep(self.reconnect_time)
                if not self.reconnect:
                    break

    def disconnect(self):
        self.reconnect = False
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)  # 읽기/쓰기 모두 종료
            except OSError as e:
                print(f"소켓 shutdown 실패: {e}")
            finally:
                self.socket.close()  # 소켓 닫기
        self.connected = False
        self.socket = None
        if self.connect_thread and self.connect_thread.is_alive() and threading.current_thread() != self.connect_thread:
            try:
                self.connect_thread.join(timeout=1.0)
            except RuntimeError as e:
                context.log.error(f"{self.name} disconnect() connect_thread 조인 에러: {e}")
        if self.receive_thread and self.receive_thread.is_alive() and threading.current_thread() != self.receive_thread:
            try:
                self.receive_thread.join(timeout=1.0)
            except RuntimeError as e:
                context.log.error(f"{self.name} disconnect() receive_thread 조인 에러: {e}")
        context.log.info(f"{self.name} disconnect() 연결 중지 -- reconnect 해제")

    def handle_reconnect(self):
        if self.reconnect:
            self.connect()

    def _run_thread_receive(self):
        if not self.receive_thread or not self.receive_thread.is_alive():
            self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
            self.receive_thread.start()

    def _receive_loop(self):
        if self.debug:
            context.log.debug(f"{self.name} _receive_loop() 스레드 시작")
        self.emit("connected")
        self.emit("online")
        while self.connected:
            try:
                if not self.socket:
                    context.log.error(f"{self.name} _receive_loop() 소켓 초기화 필요")
                else:
                    data = self.socket.recv(self.buffer_size)
                    if data:
                        if self.debug:
                            context.log.debug(f"{self.name} _receive_loop() 수신 -- {data=}")
                        event = SimpleNamespace()
                        event.source = self
                        # if not isinstance(data, (bytes, bytearray)):
                        #     data = str(data).encode()  # Ensure data is in bytes
                        event.arguments = {"data": data}
                        self.emit("received", event)
                    else:
                        self.connected = False
                        context.log.info(f"{self.name} connect() 수신 없음 연결 끊김")
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
        context.log.debug(f"{self.name} _receive_loop() 스레드 종료")

    def send(self, message):
        if self.reconnect:
            if self.socket and self.connected:
                try:
                    if self.debug:
                        context.log.debug(f"{self.name} send() 송신 -- {message=}")
                    self.socket.sendall(message)
                except Exception as e:
                    context.log.error(f"{self.name} send() 송신 실패 에러: {e}")
                    self.connected = False
                    self.handle_reconnect()
        else:

            def send_once():
                try:
                    sock = socket.create_connection((self.ip, self.port), timeout=self.timeout_send_once)
                    sock.sendall(message)
                    if self.debug:
                        context.log.debug(f"{self.name} send_once() 송신 -- {message=}")
                    try:
                        sock.settimeout(self.timeout_send_once)
                        data = sock.recv(self.buffer_size)
                        if data:
                            if self.debug:
                                context.log.debug(f"{self.name} send_once() 수신 -- {data=}")
                            event = SimpleNamespace()
                            event.source = self
                            event.arguments = {"data": data}
                            self.emit("received", event)
                        else:
                            context.log.info(f"{self.name} send_once() 서버에 의해 연결이 종료되어 응답을 받지 못함")
                    except socket.timeout:
                        context.log.info(f"{self.name} send_once() {self.timeout_send_once}초 이내에 응답을 받지 못함")
                    finally:
                        sock.close()
                        context.log.info(f"{self.name} send_once() 연결 닫힘")
                except Exception as e:
                    context.log.error(f"{self.name} send_once() 전송 실패 에러: {e=}")

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
        self.bound_port: int | None = bound_port
        self.bind_port: int | None = None
        self.last_received_time = 0
        self.connection_timeout = connection_timeout
        self.time_monitor_connection = float(self.connection_timeout // 2)

    def connect(self):
        context.log.info(f"{self.name} connect() 시작")
        try:
            if self.connected:
                return
            self._connect()
            if not self.connected:
                return
            self.last_received_time = time.time()  # 연결 시 수신 시간 초기화
            if not self.receive_thread or not self.receive_thread.is_alive():
                self.receive_thread = threading.Thread(target=self._receive_loop, daemon=True)
                self.receive_thread.start()
            if not self.monitor_thread or not self.monitor_thread.is_alive():
                self.monitor_thread = threading.Thread(target=self._monitor_connection, daemon=True)
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
            if self.debug:
                context.log.debug(f"{self.name} _connect() 바인딩된 포트: {self.bind_port}")
            self.connected = True
            self.emit("connected")
            self.emit("online")
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

    def handle_reconnect(self):
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
            if old_connected:  # 이전에 연결되어 있었다면 재연결 시도
                time.sleep(1.0)  # 잠시 대기 후 재연결
                self.connect()
        except Exception as e:
            context.log.error(f"{self.name} handle_reconnect() 재연결 실패: {e}")

    def send(self, msg: bytes | bytearray):
        if self.socket and self.connected:
            try:
                self.socket.sendto(msg, (self.ip, self.port))
                if self.debug:
                    context.log.debug(f"{self.name} send() 송신 - {msg=}")
            except Exception as e:
                context.log.error(f"{self.name} send() 송신 실패: {e}")

    def _receive_loop(self):
        if self.debug:
            context.log.debug(f"{self.name} _receive_loop() 스레드 시작")
        while self.connected:
            try:
                if not self.socket:
                    context.log.error(f"{self.name} 소켓 초기화 필요")
                    break
                data, addr = self.socket.recvfrom(self.buffer_size)
                self.last_received_time = time.time()  # 수신 시간 업데이트
                if self.debug:
                    context.log.debug(f"{self.name} _receive_loop() 수신 - {data=} {addr=}")
                event = SimpleNamespace()
                event.source = self
                # if not isinstance(data, (bytes, bytearray)):
                # data = str(data).encode()  # Ensure data is in bytes
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
                    context.log.error(f"{self.name} _receive_loop() 메세지 수신 중 에러: {e}")
                break
        if self.debug:
            context.log.debug(f"{self.name} _receive_loop() 스레드 종료")

    def _monitor_connection(self):
        if self.debug:
            context.log.debug(f"{self.name} _monitor_connection() 스레드 시작")
        while self.connected:
            try:
                current_time = time.time()
                time.sleep(self.time_monitor_connection)
                if self.debug:
                    context.log.debug(f"{self.connected=} {self.last_received_time=} {current_time=}")
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
