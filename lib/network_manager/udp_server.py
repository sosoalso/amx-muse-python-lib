# 마지막 수정일 : 20260713
"""여러 상대로부터 UDP 를 받는 서버.

TCP 서버와 달리 접속이라는 개념이 없어서, recvfrom 으로 받은 주소를 clients 에
"최근 수신 시각"으로만 기록해 둔다. client_timeout 동안 소식이 없는 주소는
cleanup 스레드가 목록에서 지운다 (send()로 전체 broadcast 할 때 대상 목록으로 쓰임).
"""

import atexit
import socket
import threading
import time
from typing import Dict, Tuple

from lib.event_manager import EventManager
from lib.network_manager.common import (
    DEFAULT_BUFFER_SIZE,
    DEFAULT_UDP_SERVER_CLIENT_TIMEOUT,
    ReceiveListener,
    close_socket,
    make_received_event,
    to_bytes,
)
from lib.utility import CommonLogger, start_thread


class UdpServer(CommonLogger, EventManager):
    """수신용 UDP 서버.

    수명주기:
        start() -> bind 성공 시 수신 루프 + (client_timeout>0 이면) 정리 스레드 시작
        stop()  -> 소켓 종료, clients 목록 비움 (atexit 에도 등록됨)

    이벤트:
        "online"/"offline" : 서버 시작/종료 시
        "received"         : 데이터 수신 시 (event.arguments["data"], ["address"])
    """

    def __init__(self, port, buffer_size=DEFAULT_BUFFER_SIZE, client_timeout=DEFAULT_UDP_SERVER_CLIENT_TIMEOUT, name=None):
        # MRO 의존 대신 명시 호출 (CommonLogger 에 __init__ 이 생겨도 안전)
        EventManager.__init__(self, "received", "online", "offline")
        self.name = name or f"udpserver_{port}"
        self.port = port
        self.buffer_size = buffer_size
        self.client_timeout = client_timeout
        self.socket: socket.socket | None = None
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.running = False
        self.clients: Dict[Tuple[str, int], float] = {}
        self.echo = False
        self._thread_receive_loop: threading.Thread | None = None
        self._thread_cleanup: threading.Thread | None = None
        self._client_lock = threading.Lock()
        atexit.register(self.stop)

    def online(self, handler):
        """ "online" 이벤트(서버 시작) 핸들러 등록 단축 메서드."""
        self.on("online", handler)

    def offline(self, handler):
        """ "offline" 이벤트(서버 종료) 핸들러 등록 단축 메서드."""
        self.on("offline", handler)

    def is_running(self):
        return self.running

    def start(self):
        """포트를 bind 하고 수신 루프를 시작한다. 이미 실행 중이면 아무것도 안 함."""
        if self.running:
            return
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind(("", self.port))
            self.socket.settimeout(0.2)
            self.running = True
            self.log_debug("start() : server starting")
            # emit: online()
            self.emit("online")
            self._thread_receive_loop = start_thread(self._receive_loop, self.socket)
            if self.client_timeout > 0:
                self._thread_cleanup = start_thread(self._cleanup_loop)
        except Exception as e:
            self.running = False
            self._close_server_socket()
            self.log_error(f"start() : failed to start server {e=}")

    def stop(self):
        """서버를 멈추고 clients 목록을 비운다. 실행 중이었으면 offline 이벤트 발생."""
        if not self.running and not self.socket:
            return
        was_running = self.running
        self.running = False
        with self._client_lock:
            self.clients.clear()
        self._close_server_socket()
        if was_running:
            # emit: offline()
            self.emit("offline")
        self.log_debug("stop() : stop signal sent")

    def send_to(self, host: str, port: int, msg: bytes | bytearray | str):
        """지정한 host:port 하나에만 전송한다."""
        if not self.socket:
            return
        try:
            self.log_debug(f"send_to() : {host=} {port=} {msg=}")
            self.socket.sendto(to_bytes(msg), (host, port))
        except Exception as e:
            self.log_error(f"send_to() : failed to send {msg=} {e=}")

    def send(self, msg: bytes | bytearray | str, exclude_client: tuple[str, int] | None = None):
        """clients 에 기록된 모든 상대에게 전송한다 (exclude_client 는 제외)."""
        try:
            with self._client_lock:
                client_addrs = list(self.clients.keys())
            for client_addr in client_addrs:
                if client_addr != exclude_client:
                    self.send_to(client_addr[0], client_addr[1], msg)
        except Exception as e:
            self.log_error(f"send() : failed to send {msg=} {e=}")

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        # emit: received(event: ReceivedEvent)  — event.arguments["data"]: bytes
        self.emit("received", make_received_event(self, data, address))

    def _receive_loop(self, recv_sock: socket.socket):
        """데이터를 받아 clients 목록을 갱신하고 "received" 이벤트로 전달한다. echo=True 면 그대로 되돌려 보낸다."""
        self.log_debug("_receive_loop() : thread started")
        try:
            while self.running and self.socket is recv_sock:
                try:
                    data, addr = recv_sock.recvfrom(self.buffer_size)
                    if not data:
                        continue
                    with self._client_lock:
                        self.clients[addr] = time.time()
                    self.log_debug(f"_receive_loop() : received {data=} {addr=}")
                    try:
                        self._emit_received(data, addr)
                    except Exception as e:
                        self.log_error(f"_receive_loop() : emit error {e=}")
                    if self.echo:
                        recv_sock.sendto(data, addr)
                except socket.timeout:
                    continue
                except OSError as e:
                    if self.running and self.socket is recv_sock:
                        self.log_error(f"_receive_loop() : socket {e=}")
                    break
                except Exception as e:
                    if self.running:
                        self.log_error(f"_receive_loop() : message receive {e=}")
                    break
        finally:
            # 자기 소켓일 때만 상태 정리 - stop() 직후 재시작된 새 서버의 소켓/상태를 건드리지 않음
            if self.socket is recv_sock:
                was_running = self.running
                self.running = False
                self.socket = None
                if was_running:
                    try:
                        # emit: offline()
                        self.emit("offline")
                    except Exception as e:
                        self.log_error(f"_receive_loop() : emit error {e=}")
            close_socket(recv_sock)
            self.log_debug("_receive_loop() : thread ended")

    def _cleanup_loop(self):
        """client_timeout 동안 소식 없는 clients 항목을 주기적으로 지운다."""
        self.log_debug("_cleanup_loop() : thread started")
        while self.running:
            time.sleep(min(self.client_timeout / 2, 5.0))
            if not self.running:
                break
            now = time.time()
            with self._client_lock:
                stale = [addr for addr, last_seen in self.clients.items() if now - last_seen >= self.client_timeout]
            for addr in stale:
                with self._client_lock:
                    self.clients.pop(addr, None)
                self.log_debug(f"_cleanup_loop() : client timed out {addr=}")
        self.log_debug("_cleanup_loop() : thread ended")

    def _close_server_socket(self):
        if self.socket:
            close_socket(self.socket)
            self.socket = None
