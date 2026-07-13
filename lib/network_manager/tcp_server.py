# 마지막 수정일 : 20260713
"""다중 클라이언트를 받는 TCP 서버.

외부 시스템(터치패널, 상위 제어기, 타 서버 등)이 이 컨트롤러로 접속해
명령을 보내올 때 수신 창구로 사용한다. 클라이언트마다 수신 스레드를 하나씩 띄우고,
받은 데이터는 "received" 이벤트로 전달한다. 전체/개별 클라이언트로 송신도 가능.
"""

import atexit
import socket
import threading
from typing import Dict, Tuple

from lib.event_manager import EventManager
from lib.network_manager.common import (
    DEFAULT_BUFFER_SIZE,
    ReceiveListener,
    close_socket,
    make_received_event,
    to_bytes,
)
from lib.utility import CommonLogger, start_thread


class TcpServer(CommonLogger, EventManager):
    """수신용 TCP 서버.

    수명주기:
        start() -> bind/listen 성공 시 accept 루프 스레드 시작 (실패하면 running=False 유지)
        stop()  -> 모든 클라이언트/서버 소켓 종료 (atexit 에도 등록됨)

    이벤트:
        "connected"/"online"     : 클라이언트 접속 시 (address=(ip, port) 키워드 인자 포함)
        "disconnected"/"offline" : 클라이언트 접속 종료 시 (address=(ip, port) 키워드 인자 포함)
        "received"               : 데이터 수신 시 (evt.arguments.get("data", b""), ["address"])

    사용 흐름:
        server = TcpServer(5000)
        server.receive.listen(handler)
        server.start()
        server.send(b"broadcast")            # 접속 중인 전체 클라이언트에게 전송
    """

    def __init__(self, port, buffer_size=DEFAULT_BUFFER_SIZE, name=None):
        # MRO 의존 대신 명시 호출 (CommonLogger 에 __init__ 이 생겨도 안전)
        EventManager.__init__(self, "received", "online", "offline", "connected", "disconnected")
        self.port = port
        self.name = name or f"tcpserver_{port}"
        self.buffer_size = buffer_size
        self.socket: socket.socket | None = None
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.running = False
        self.clients: Dict[Tuple[str, int], socket.socket] = {}  # 접속 중인 클라이언트: 주소 -> 소켓
        self.echo = False  # True 면 받은 데이터를 그대로 되돌려 보냄 (테스트/디버깅용)
        self._thread_start_server: threading.Thread | None = None
        self._client_lock = threading.Lock()  # clients 딕셔너리 보호용
        atexit.register(self.stop)  # 프로세스 종료 시 소켓 정리 보장

    def online(self, handler):
        """ "online" 이벤트(클라이언트 접속) 핸들러 등록 단축 메서드."""
        self.on("online", handler)

    def offline(self, handler):
        """ "offline" 이벤트(클라이언트 접속 종료) 핸들러 등록 단축 메서드."""
        self.on("offline", handler)

    def is_running(self):
        return self.running

    def start(self):
        """서버 소켓을 열고 accept 루프 스레드를 시작한다. 실패 시 로그만 남기고 종료."""
        if self.running:
            return
        # 바인드까지 동기로 수행 - 성공해야만 running 이 True 가 됨
        server_sock = None
        try:
            server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # 재시작 시 TIME_WAIT 상태의 이전 포트를 바로 재사용할 수 있게 함
            server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # accept 타임아웃을 짧게 - accept 루프가 running 플래그를 주기적으로 확인
            server_sock.settimeout(0.2)
            server_sock.bind(("", self.port))
            server_sock.listen()
        except OSError as e:
            if server_sock:
                self._close_socket(server_sock)
            if self._is_address_in_use_error(e):
                self.log_warn("start() : Address already in use, ignoring")
            else:
                self.log_error(f"start() : failed to start {e=}")
            return
        self.socket = server_sock
        self.running = True
        self.log_info("start() : server starting")
        self._thread_start_server = start_thread(self._accept_loop, server_sock)

    def stop(self):
        """서버를 정지한다. 모든 클라이언트 소켓과 서버 소켓을 닫는다."""
        if not self.running and not self.socket:
            return
        self.running = False
        self._close_all_clients()
        self._close_server_socket()
        self.log_info("stop() : stop signal sent")

    def send_to(self, client_socket: socket.socket, msg: bytes | bytearray | str):
        """특정 클라이언트 소켓으로 전송. 성공 여부(bool)를 반환한다."""
        try:
            client_socket.sendall(to_bytes(msg))
            return True
        except Exception as e:
            self.log_error(f"send_to() : failed to send {msg=} {e=}")
            return False

    def send(self, msg: bytes | bytearray | str, exclude_client: tuple[str, int] | None = None):
        """접속 중인 모든 클라이언트에게 전송 (exclude_client 는 제외).

        전송에 실패한 클라이언트는 죽은 연결로 보고 목록에서 제거하고 닫는다.
        """
        with self._client_lock:
            clients = list(self.clients.items())
        for address, client_socket in clients:
            if address == exclude_client:
                continue
            if not self.send_to(client_socket, msg):
                self._close_client(address, client_socket)

    def _is_address_in_use_error(self, error: OSError) -> bool:
        """포트가 이미 사용 중인 에러인지 판별 (48=macOS, 98=Linux, 10048=Windows)."""
        return error.errno in (48, 98) or getattr(error, "winerror", None) == 10048

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        # emit: received(evt: ReceivedEvent)  — evt.arguments.get("data", b""): bytes
        self.emit("received", make_received_event(self, data, address))

    def _close_all_clients(self):
        with self._client_lock:
            clients = list(self.clients.items())
            self.clients.clear()
        for _address, client_socket in clients:
            self._close_socket(client_socket)

    def _close_client(self, address: Tuple[str, int], client_socket: socket.socket | None = None, *, emit_events: bool = True) -> bool:
        """클라이언트를 목록에서 제거하고 소켓을 닫는다.

        목록에 실제로 있었던 경우에만 offline/disconnected 이벤트를 발생시켜
        여러 경로에서 중복 호출돼도 이벤트가 한 번만 나가게 한다.
        반환값은 목록에서 제거됐는지 여부.
        """
        with self._client_lock:
            removed_socket = self.clients.pop(address, None)
        socket_to_close = client_socket or removed_socket
        if socket_to_close:
            self._close_socket(socket_to_close)
        if removed_socket and emit_events:
            # emit: offline(address: tuple[str, int])
            self.emit("offline", address=address)
            # emit: disconnected(address: tuple[str, int])
            self.emit("disconnected", address=address)
        return removed_socket is not None

    def _close_socket(self, sock: socket.socket):
        # shutdown=True: blocking 중인 recv/accept 를 깨워 해당 스레드가 즉시 종료되게 함
        close_socket(sock, shutdown=True)

    def _close_server_socket(self):
        if self.socket:
            self._close_socket(self.socket)
            self.socket = None

    def _accept_loop(self, server_sock: socket.socket):
        """클라이언트 접속을 받아 클라이언트별 수신 스레드를 띄우는 루프.

        stop() 으로 running 이 내려가거나 서버 소켓이 닫히면(OSError) 종료된다.
        """
        self.log_debug("_accept_loop() thread start")
        try:
            while self.running and self.socket is server_sock:
                try:
                    client, address = server_sock.accept()
                    # 클라이언트 recv 타임아웃도 짧게 - 수신 루프가 running 플래그를 자주 확인
                    client.settimeout(0.2)
                    self.log_debug(f"_accept_loop() : client connected {address=}")
                    with self._client_lock:
                        self.clients[address] = client
                    # emit: connected(address: tuple[str, int])
                    self.emit("connected", address=address)
                    # emit: online(address: tuple[str, int])
                    self.emit("online", address=address)
                    start_thread(self._receive_loop, client, address)
                except socket.timeout:
                    continue
                except OSError:
                    break
        except Exception as e:
            self.log_error(f"_accept_loop() : {e=}")
        finally:
            # 자기 소켓일 때만 상태 정리 - stop() 직후 재시작된 새 서버의 소켓/상태를 건드리지 않음
            if self.socket is server_sock:
                self.running = False
                self.socket = None
            self._close_socket(server_sock)
            self.log_debug("_accept_loop() thread end")

    def _receive_loop(self, client_socket: socket.socket, address: Tuple[str, int]):
        self.log_debug(f"_receive_loop() : {address=}")
        try:
            while self.running:
                try:
                    data = client_socket.recv(self.buffer_size)
                except socket.timeout:
                    continue
                if not data:
                    break
                self.log_debug(f"_receive_loop() : {data=} {address=}")
                self._emit_received(data, address)
                if self.echo:
                    client_socket.sendall(data)
        except (ConnectionResetError, BrokenPipeError):
            self.log_info(f"_receive_loop() : Client disconnected {address=}")
        except Exception as e:
            if self.running:
                self.log_error(f"_receive_loop() : {e=}")
        finally:
            removed = self._close_client(address, client_socket)
            if removed:
                self.log_info(f"_receive_loop() : Client connection closed {address=}")
