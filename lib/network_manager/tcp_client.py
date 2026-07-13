# 마지막 수정일 : 20260713
"""자동 재연결을 지원하는 TCP 클라이언트.

프로젝터, 스위처, 카메라 등 TCP 로 제어하는 AV 장비에 접속할 때 사용한다.
connect() 한 번이면 백그라운드 스레드가 연결 유지/재연결을 계속 책임지고,
수신 데이터는 "received" 이벤트로 콜백에 전달된다.
connect() 없이 send() 만 하면 1회성 연결(보내고 잠깐 응답 대기 후 종료)로 동작한다.
"""

import atexit
import socket
import threading
import time
from typing import Tuple

from lib.event_manager import EventManager
from lib.network_manager.common import (
    DEFAULT_BUFFER_SIZE,
    DEFAULT_TCP_CLIENT_CONNECT_TIMEOUT,
    DEFAULT_TCP_CLIENT_RECONNECT_TIME,
    DEFAULT_TCP_CLIENT_SOCKET_TIMEOUT,
    ReceiveListener,
    close_socket,
    make_received_event,
    to_bytes,
)
from lib.utility import CommonLogger, run_thread, start_thread


class TcpClient(CommonLogger, EventManager):
    """장비 접속용 TCP 클라이언트.

    수명주기:
        connect()  -> 백그라운드 스레드가 연결 시도, 끊기면 reconnect_time 후 재시도
        disconnect() -> 재연결 중단 + 소켓 종료 (atexit 에도 등록됨)

    이벤트:
        "connected"/"online"     : 연결 성공 시
        "disconnected"/"offline" : 연결 끊김 시
        "received"               : 데이터 수신 시 (event.arguments["data"])

    사용 흐름:
        client = TcpClient("192.168.0.10", 23)
        client.receive.listen(handler)   # 또는 client.on("received", handler)
        client.connect()
        client.send(b"PWR ON\\r")
    """

    def __init__(self, ip, port, reconnect_time=DEFAULT_TCP_CLIENT_RECONNECT_TIME, buffer_size=DEFAULT_BUFFER_SIZE, name=None):
        # MRO 의존 대신 명시 호출 (CommonLogger 에 __init__ 이 생겨도 안전)
        EventManager.__init__(self, "disconnected", "connected", "received", "online", "offline")
        self.name = name or f"tcpclient_{ip}_{port}"
        self.ip = ip
        self.port = port
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.reconnect_time = reconnect_time
        self.socket_timeout = DEFAULT_TCP_CLIENT_SOCKET_TIMEOUT
        self.connect_timeout = DEFAULT_TCP_CLIENT_CONNECT_TIMEOUT
        self.timeout_send_once = 1.0  # 1회성 전송(_send_once)의 연결/응답 대기 타임아웃(초)
        self.buffer_size = buffer_size
        self.connected = False
        self.socket: socket.socket | None = None
        self._thread_connect: threading.Thread | None = None
        self.reconnect = False  # True 인 동안만 연결 유지/재연결을 시도 (connect/disconnect 로 토글)
        self._state_lock = threading.Lock()  # connected/socket/reconnect 상태 보호용
        atexit.register(self.disconnect)  # 프로세스 종료 시 소켓 정리 보장

    def online(self, handler):
        """ "online" 이벤트(연결 성공) 핸들러 등록 단축 메서드."""
        self.on("online", handler)

    def offline(self, handler):
        """ "offline" 이벤트(연결 끊김) 핸들러 등록 단축 메서드."""
        self.on("offline", handler)

    def is_connected(self):
        return self.connected

    def connect(self):
        """연결 유지 모드를 켜고 백그라운드 연결 루프 스레드를 시작한다.

        run_thread 는 기존 스레드가 살아 있으면 재시작하지 않으므로
        중복 호출해도 루프 스레드는 하나만 유지된다.
        """
        self.log_debug(f"connect() : {self.ip}:{self.port}")
        with self._state_lock:
            self.reconnect = True
        self._thread_connect = run_thread(self._thread_connect, self._connect_loop)

    def disconnect(self):
        """재연결을 중단하고 현재 소켓을 닫는다. 연결돼 있었으면 offline/disconnected 이벤트 발생."""
        with self._state_lock:
            if not (self.connected or self.socket or self.reconnect):
                return
            self.reconnect = False
        self.log_debug("disconnect() : disconnecting from server")
        self._set_state_disconnected()
        self._close_current_socket()

    def send(self, msg: bytes | bytearray | str):
        """데이터를 전송한다.

        - connect() 로 연결 유지 중이면: 현재 소켓으로 전송, 미연결이면 버림(드롭).
          전송 실패 시 소켓을 닫아 연결 루프가 재연결하도록 만든다.
        - connect() 를 안 했으면: 별도 스레드에서 1회성 연결로 보내고 응답을 잠깐 기다린다.
        """
        msg = to_bytes(msg)

        with self._state_lock:
            reconnect_enabled = self.reconnect
            sock = self.socket
            is_connected = self.connected

        if reconnect_enabled:
            if not (sock and is_connected):
                self.log_debug(f"send() : not connected, dropped {msg=}")
                return
            try:
                self.log_debug(f"send() : sending {msg=}")
                sock.sendall(msg)
            except Exception as e:
                self.log_error(f"send() : failed to send {msg=} {e=}")
                with self._state_lock:
                    if self.socket is sock:
                        self.socket = None
                self._set_state_disconnected()
                self._close_socket(sock)
            return

        # 연결 유지 모드가 아니면 1회성 전송 (blocking connect 를 피하려고 스레드로 분리)
        start_thread(self._send_once, msg)

    def _connect_loop(self):
        """연결 -> 수신 -> 끊김 -> 대기 -> 재연결을 반복하는 백그라운드 루프.

        reconnect 가 False 가 되면 루프가 끝난다. _receive_loop 가 리턴한다는 것은
        연결이 끊겼다는 뜻이므로, 재연결 대기 후 처음부터 다시 시도한다.
        """
        while self.reconnect:
            sock = self._open_socket()
            if not sock:
                self._sleep_reconnect()
                continue

            with self._state_lock:
                # 연결되는 사이 disconnect() 가 호출됐을 수 있으므로 재확인
                if not self.reconnect:
                    self._close_socket(sock)
                    break
                self.socket = sock

            self._set_state_connected()
            self._receive_loop(sock)  # 연결이 살아 있는 동안 여기서 블록됨

            if self.reconnect:
                self._sleep_reconnect()

    def _open_socket(self) -> socket.socket | None:
        """장비에 TCP 연결을 시도한다. 성공하면 소켓, 실패하면 None.

        연결 후에는 recv 타임아웃을 짧게(socket_timeout) 바꿔서
        수신 루프가 종료 플래그를 주기적으로 확인할 수 있게 한다.
        """
        try:
            self.log_debug(f"_open_socket() : connecting to {self.ip}:{self.port}")
            sock = socket.create_connection((self.ip, self.port), timeout=self.connect_timeout)
            sock.settimeout(self.socket_timeout)
            return sock
        except (ConnectionRefusedError, TimeoutError, OSError) as e:
            self.log_debug(f"_open_socket() : connect failed {e=}")
            return None

    def _sleep_reconnect(self):
        """재연결 대기. 통짜 sleep 대신 0.1초 단위로 쪼개서 disconnect() 에 빨리 반응한다."""
        end_time = time.time() + self.reconnect_time
        while self.reconnect and time.time() < end_time:
            time.sleep(0.1)

    def _set_state_connected(self):
        """connected 플래그를 세우고, 미연결 -> 연결 전이일 때만 이벤트를 발생시킨다."""
        with self._state_lock:
            was_connected = self.connected
            self.connected = True
        if not was_connected:
            self.log_debug(f"_set_state_connected() : connected to {self.ip}:{self.port}")
            try:
                # emit: connected()
                self.emit("connected")
                # emit: online()
                self.emit("online")
            except Exception as e:
                self.log_error(f"_set_state_connected() : emit error {e=}")

    def _set_state_disconnected(self):
        """connected 플래그를 내리고, 연결 -> 끊김 전이일 때만 이벤트를 발생시킨다.

        여러 경로(send 실패, 수신 루프 종료, disconnect)에서 불려도
        이벤트는 실제 상태가 바뀔 때 한 번만 나간다. 반환값은 이전 연결 여부.
        """
        with self._state_lock:
            was_connected = self.connected
            self.connected = False
        if was_connected:
            self.log_debug("_set_state_disconnected() : disconnected from server")
            try:
                # emit: offline()
                self.emit("offline")
                # emit: disconnected()
                self.emit("disconnected")
            except Exception as e:
                self.log_error(f"_set_state_disconnected() : emit error {e=}")
        return was_connected

    def _receive_loop(self, recv_sock: socket.socket):
        """현재 소켓에서 데이터를 수신해 "received" 이벤트로 전달한다.

        연결이 끊기거나(빈 recv), 소켓 에러가 나거나, disconnect() 되면 리턴한다.
        리턴하면서 상태를 끊김으로 정리하고 소켓을 닫는다 (_connect_loop 가 재연결 담당).
        """
        self.log_debug("_receive_loop() thread started")
        while self.reconnect:
            try:
                with self._state_lock:
                    # 재연결 등으로 self.socket 이 교체됐으면 이 루프는 옛 소켓이므로 종료
                    if self.socket is not recv_sock:
                        break

                data = recv_sock.recv(self.buffer_size)
                if not data:
                    # 빈 데이터는 상대가 정상적으로 연결을 닫았다는 뜻
                    self.log_debug("_receive_loop() no data received, connection closed")
                    break

                self.log_debug(f"_receive_loop() received {data=}")
                try:
                    self._emit_received(data, address=(self.ip, self.port))
                except Exception as e:
                    self.log_error(f"_receive_loop() : emit error {e=}")
            except socket.timeout:
                # 짧은 recv 타임아웃 - 루프를 돌며 reconnect 플래그/소켓 교체 여부를 재확인
                continue
            except Exception as e:
                if isinstance(e, OSError) and self._is_socket_closed_error(e):
                    self.log_debug(f"_receive_loop() : socket already closed {e=}")
                else:
                    self.log_error(f"_receive_loop() : {e=}")
                break

        with self._state_lock:
            if self.socket is recv_sock:
                self.socket = None
        self._set_state_disconnected()
        self._close_socket(recv_sock)
        self.log_debug("_receive_loop() thread ended")

    def _close_current_socket(self):
        """self.socket 을 락 안에서 떼어낸 뒤 닫는다 (다른 스레드와의 이중 close 방지)."""
        with self._state_lock:
            sock = self.socket
            self.socket = None
        if sock:
            self._close_socket(sock)

    def _close_socket(self, sock: socket.socket):
        # shutdown=True: blocking 중인 recv 를 깨워 수신 루프가 즉시 종료되게 함
        close_socket(sock, shutdown=True)

    def _is_socket_closed_error(self, error: OSError) -> bool:
        """이미 닫힌 소켓에 대한 에러인지 판별 (9=EBADF, 10038=WSAENOTSOCK/Windows)."""
        return error.errno in (9, 10038) or getattr(error, "winerror", None) == 10038

    def _send_once(self, msg: bytes | bytearray):
        """1회성 전송: 새로 연결해서 보내고, 잠깐(timeout_send_once) 응답을 기다린 뒤 닫는다.

        connect() 를 쓰지 않는 간단한 단발 제어(예: 전원 명령 한 번)용.
        응답이 오면 동일하게 "received" 이벤트로 전달된다.
        """
        try:
            sock = socket.create_connection((self.ip, self.port), timeout=self.timeout_send_once)
            sock.sendall(msg)
            self.log_debug(f"_send_once() : sending {msg=}")
            try:
                sock.settimeout(self.timeout_send_once)
                data = sock.recv(self.buffer_size)
                if data:
                    self.log_debug(f"_send_once() : received {data=}")
                    self._emit_received(data, address=(self.ip, self.port))
                else:
                    self.log_debug("_send_once() : connection closed by server, no response received")
            except socket.timeout:
                self.log_debug(f"_send_once() : no response received within {self.timeout_send_once} seconds")
            finally:
                self._close_socket(sock)
                self.log_debug("_send_once() : connection closed")
        except Exception as e:
            self.log_error(f"_send_once() : failed to send {msg=} {e=}")

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        # emit: received(event: ReceivedEvent)  — event.arguments["data"]: bytes
        self.emit("received", make_received_event(self, data, address))
