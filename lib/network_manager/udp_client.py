# 마지막 수정일 : 20260713
"""UDP 클라이언트.

TCP 와 달리 연결이라는 개념이 없어서, 여기서는 소켓을 열어두고 일정 시간(reconnect_time)
응답이 없으면 소켓을 새로 열어보는 방식으로 "연결 유지"를 흉내낸다.
connect() 없이 send() 만 호출하면 그때그때 소켓을 새로 열어 1회성으로 보내고 바로 닫는다
(응답을 받을 필요 없는 단발성 명령용). 응답을 받아야 하거나 지속적으로 주고받는 장비는
connect() 로 모니터링을 켜두는 것을 권장한다.
"""

import atexit
import socket
import threading
import time
from typing import Tuple

from lib.event_manager import EventManager
from lib.network_manager.common import (
    DEFAULT_BUFFER_SIZE,
    DEFAULT_UDP_CLIENT_RECONNECT_TIME,
    ReceiveListener,
    close_socket,
    make_received_event,
    to_bytes,
)
from lib.utility import CommonLogger, start_thread


class UdpClient(CommonLogger, EventManager):
    """UDP 클라이언트.

    수명주기:
        connect()    -> 소켓을 열고, 응답 모니터링 스레드를 시작
        disconnect() -> 모니터링 중단 + 소켓 종료 (atexit 에도 등록됨)

    이벤트:
        "connected"/"online"     : 소켓 오픈 성공 시
        "disconnected"/"offline" : 무응답으로 재연결하거나 disconnect() 할 때
        "received"               : 데이터 수신 시 (evt.arguments.get("data", b""))

    reconnect_time 이 0 이하면 무응답 감지를 끄고 소켓을 계속 유지한다.
    """

    def __init__(
        self,
        ip,
        port,
        reconnect_time=DEFAULT_UDP_CLIENT_RECONNECT_TIME,
        buffer_size=DEFAULT_BUFFER_SIZE,
        bound_port=None,
        name=None,
    ):
        # MRO 의존 대신 명시 호출 (CommonLogger 에 __init__ 이 생겨도 안전)
        EventManager.__init__(self, "connected", "received", "online", "offline", "disconnected")
        self.name = name or f"udpclient_{ip}_{port}"
        self.ip = ip
        self.port = port
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.buffer_size = buffer_size
        self.connected = False
        self.reconnect = False
        self.socket: socket.socket | None = None
        self.bound_port: int | None = bound_port
        self.bind_port: int | None = None
        self.reconnect_time = reconnect_time
        self._thread_receive_loop: threading.Thread | None = None
        self._thread_monitor_loop: threading.Thread | None = None
        self._state_lock = threading.Lock()
        self._last_received_at = 0.0
        self._monitor_gen = 0  # connect 마다 증가 - 옛 monitor 스레드가 자연 종료되도록 하는 세대 토큰
        atexit.register(self.disconnect)

    def online(self, handler):
        """ "online" 이벤트(소켓 오픈) 핸들러 등록 단축 메서드."""
        self.on("online", handler)

    def offline(self, handler):
        """ "offline" 이벤트(재연결/종료) 핸들러 등록 단축 메서드."""
        self.on("offline", handler)

    def is_connected(self):
        return self.connected

    def connect(self):
        """소켓을 열고 무응답 감시(monitor) 스레드를 시작한다. 이미 열려 있으면 아무것도 안 함."""
        with self._state_lock:
            self.reconnect = True
            if self.socket:
                return
            self._monitor_gen += 1
            gen = self._monitor_gen

        self._connect_socket()
        # 최초 연결이 실패해도 monitor 가 재시도하도록 항상 시작
        self._thread_monitor_loop = start_thread(self._monitor_loop, gen)

    def disconnect(self):
        """감시를 끄고 소켓을 닫는다. 열려 있었으면 offline/disconnected 이벤트 발생."""
        with self._state_lock:
            if not (self.connected or self.socket or self.reconnect):
                return
            self.reconnect = False
        if not self.connected and not self.socket:
            return
        self._set_state_disconnected()
        self._close_current_socket()
        self.log_debug("disconnect() : disconnect signal sent")

    def send(self, msg: bytes | bytearray | str):
        """데이터를 전송한다.

        - connect() 로 연결 유지 중이면: 현재 소켓으로 전송한다.
        - connect() 를 안 했으면: 소켓을 새로 열어 1회성으로 보내고 바로 닫는다(응답 대기 없음).
        """
        msg = to_bytes(msg)
        with self._state_lock:
            sock = self.socket
            is_connected = self.connected
        if not (sock and is_connected):
            self._send_once(msg)
            return
        try:
            sock.sendto(msg, (self.ip, self.port))
            self.log_debug(f"send() : sending - {msg=}")
        except Exception as e:
            self.log_error(f"send() : failed to send {msg=} {e=}")
            self._set_state_disconnected()
            self._close_current_socket()

    def _send_once(self, msg: bytes | bytearray):
        """connect() 없이 1회성 전송: 소켓을 새로 열어 바로 보내고 닫는다. UDP 는 handshake 가 없어 스레드 없이 바로 처리."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            try:
                if self.bound_port is not None:
                    sock.bind(("", self.bound_port))
                sock.sendto(msg, (self.ip, self.port))
                self.log_debug(f"_send_once() : sending {msg=}")
            finally:
                close_socket(sock)
        except Exception as e:
            self.log_error(f"_send_once() : failed to send {msg=} {e=}")

    def _connect_socket(self):
        """소켓을 새로 열어 self.socket 에 세팅하고 수신 스레드를 시작한다. 실패하면 False."""
        sock = self._open_socket()
        if not sock:
            return False

        with self._state_lock:
            if not self.reconnect:
                close_socket(sock)
                return False
            was_connected = self.connected
            self.socket = sock
            self.bind_port = sock.getsockname()[1]
            self.connected = True
            self._last_received_at = time.time()

        if not was_connected:
            self.log_debug(f"_connect_socket() : connected to {self.ip}:{self.port}")
            try:
                # emit: connected()
                self.emit("connected")
                # emit: online()
                self.emit("online")
            except Exception as e:
                self.log_error(f"_connect_socket() : emit error {e=}")
        self._thread_receive_loop = start_thread(self._receive_loop, sock)
        return True

    def _set_state_disconnected(self):
        """connected 플래그를 내리고, 연결 -> 끊김 전이일 때만 offline/disconnected 이벤트를 낸다."""
        with self._state_lock:
            was_connected = self.connected
            self.connected = False
        if was_connected:
            self.log_debug(f"_set_state_disconnected() : disconnected from {self.ip}:{self.port}")
            try:
                # emit: offline()
                self.emit("offline")
                # emit: disconnected()
                self.emit("disconnected")
            except Exception as e:
                self.log_error(f"_set_state_disconnected() : emit error {e=}")
        return was_connected

    def _open_socket(self) -> socket.socket | None:
        """UDP 소켓을 만들어 bound_port(없으면 임의 포트)에 bind 한다. 실패하면 None."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(0.2)
            sock.bind(("", 0 if self.bound_port is None else self.bound_port))
            self.log_debug(f"_open_socket() : bind_port={sock.getsockname()[1]}")
            return sock
        except Exception as e:
            self.log_error(f"_open_socket() : failed to open {e=}")
            return None

    def _monitor_loop(self, gen: int):
        """reconnect_time 동안 무응답이면 소켓을 새로 여는 감시 루프.

        gen(세대 토큰)이 connect() 호출 시점의 것과 다르면 옛 감시 스레드로 보고 종료한다
        (재연결로 새 monitor 스레드가 이미 떠 있는데 옛 스레드가 겹쳐 도는 것 방지).
        """
        self.log_debug("_monitor_loop() : thread started")
        while True:
            with self._state_lock:
                if not self.reconnect or gen != self._monitor_gen:
                    break
                sock = self.socket
                connected = self.connected
                last_received_at = self._last_received_at

            if sock and connected and self.reconnect_time > 0:
                if time.time() - last_received_at >= self.reconnect_time:
                    self.log_debug(f"_monitor_loop() : no response for {self.reconnect_time} seconds, reconnecting")
                    self._set_state_disconnected()
                    self._close_current_socket()
                    self._connect_socket()
            elif not sock:
                self._connect_socket()

            # reconnect_time 이 0 이하(타임아웃 비활성)면 느슨하게 폴링
            time.sleep(0.5 if self.reconnect_time <= 0 else min(0.5, max(0.1, self.reconnect_time / 2)))
        self.log_debug("_monitor_loop() : thread ended")

    def _receive_loop(self, recv_sock: socket.socket):
        """recv_sock 에서 데이터를 받아 "received" 이벤트로 전달한다.

        재연결 등으로 self.socket 이 recv_sock 이 아니게 되면(옛 소켓) 루프를 끝낸다.
        """
        self.log_debug("_receive_loop() : thread started")
        while True:
            try:
                with self._state_lock:
                    if not self.reconnect or self.socket is not recv_sock:
                        break
                    is_connected = self.connected
                if not is_connected:
                    break
                data, addr = recv_sock.recvfrom(self.buffer_size)
                with self._state_lock:
                    self._last_received_at = time.time()
                self.log_debug(f"_receive_loop() : received - {data=} {addr=}")
                try:
                    self._emit_received(data, addr)
                except Exception as e:
                    self.log_error(f"_receive_loop() : emit error {e=}")
            except socket.timeout:
                continue
            except OSError as e:
                with self._state_lock:
                    is_current_socket = self.socket is recv_sock
                if self.reconnect and is_current_socket:
                    self.log_error(f"_receive_loop() : socket {e=}")
                break
            except Exception as e:
                if self.reconnect:
                    self.log_error(f"_receive_loop() : receiving message {e=}")
                break
        with self._state_lock:
            is_current_socket = self.socket is recv_sock
            if is_current_socket:
                self.socket = None
                self.bind_port = None
        if is_current_socket:
            self._set_state_disconnected()
            close_socket(recv_sock)
        self.log_debug("_receive_loop() : thread ended")

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        # emit: received(evt: ReceivedEvent)  — evt.arguments.get("data", b""): bytes
        self.emit("received", make_received_event(self, data, address))

    def _close_current_socket(self):
        with self._state_lock:
            sock = self.socket
            self.socket = None
            self.bind_port = None
        if sock:
            self._close_socket(sock)

    def _close_socket(self, sock: socket.socket):
        close_socket(sock)
