# 마지막 수정일 : 20260713
"""멀티캐스트 그룹 참가/송수신.

group_ip(멀티캐스트 주소)에 join() 하면 같은 그룹에 속한 다른 장비/서버가 보내는
데이터를 다 같이 받을 수 있다. 1:N 로 상태를 뿌리는 장비(SVSI, NVX 등 AV-over-IP)
제어에 주로 쓰인다. leave() 하면 그룹에서 빠지고 소켓도 닫는다.
"""

import atexit
import socket
import threading
from typing import Tuple

from lib.event_manager import EventManager
from lib.network_manager.common import (
    DEFAULT_BUFFER_SIZE,
    ReceiveListener,
    close_socket,
    make_received_event,
    to_bytes,
)
from lib.utility import CommonLogger, start_thread


class MulticastGroup(CommonLogger, EventManager):
    """멀티캐스트 그룹 참가자.

    수명주기:
        join()/connect()   -> 소켓을 열고 IP_ADD_MEMBERSHIP 으로 그룹에 참가, 수신 스레드 시작
        leave()/disconnect() -> IP_DROP_MEMBERSHIP 로 그룹 탈퇴 + 소켓 종료 (atexit 에도 등록됨)

    이벤트:
        "connected"/"online" : 그룹 참가 성공 시
        "offline"            : 그룹 탈퇴 시 ("disconnected" 는 없음)
        "received"           : 데이터 수신 시 (event.arguments["data"])
    """

    def __init__(
        self,
        group_ip,
        port,
        bind_port=None,
        buffer_size=DEFAULT_BUFFER_SIZE,
        ttl=64,
        loopback=False,
        interface_ip="0.0.0.0",
        name=None,
    ):
        # MRO 의존 대신 명시 호출 (CommonLogger 에 __init__ 이 생겨도 안전)
        EventManager.__init__(self, "connected", "received", "online", "offline")
        self.connected = False
        self.name = name or f"multicastgroup_{group_ip}_{port}"
        self.group_ip = group_ip
        self.port = port
        self.interface_ip = interface_ip
        self.buffer_size = buffer_size
        self.ttl = ttl
        self.loopback = loopback
        self.bind_port = port if bind_port is None else bind_port
        self.socket: socket.socket | None = None
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.membership = None
        self._thread_receive_loop = None
        self._state_lock = threading.Lock()
        self._connect_lock = threading.Lock()  # connect 동시 호출 직렬화 (소켓 누수 방지)
        atexit.register(self.disconnect)

    def online(self, handler):
        """ "online" 이벤트(그룹 참가) 핸들러 등록 단축 메서드."""
        self.on("online", handler)

    def offline(self, handler):
        """ "offline" 이벤트(그룹 탈퇴) 핸들러 등록 단축 메서드."""
        self.on("offline", handler)

    def join(self):
        """connect() 의 별칭 - 의미상 "그룹 참가"를 강조할 때 사용."""
        self.connect()

    def connect(self):
        """소켓을 열고 그룹에 참가(IP_ADD_MEMBERSHIP)한 뒤 수신 스레드를 시작한다. 이미 참가 중이면 아무것도 안 함."""
        self.log_debug("connect() starting")
        with self._connect_lock:
            with self._state_lock:
                if self.connected:
                    return

            sock = None
            membership = None
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(("", self.bind_port))

                group_bin = socket.inet_aton(self.group_ip)
                interface_bin = socket.inet_aton(self.interface_ip)
                membership = group_bin + interface_bin
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, self.ttl)
                sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1 if self.loopback else 0)
                if self.interface_ip != "0.0.0.0":
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, interface_bin)
                sock.settimeout(1.0)

                with self._state_lock:
                    self.socket = sock
                    self.membership = membership
                    self.connected = True

                try:
                    # emit: connected()
                    self.emit("connected")
                    # emit: online()
                    self.emit("online")
                except Exception as e:
                    self.log_error(f"connect() : emit error {e=}")
                # 소켓을 캡처해서 스레드에 전달 - 재연결 시 옛 스레드가 새 소켓을 물지 않음
                self._thread_receive_loop = start_thread(self._receive_loop, sock)
            except Exception as e:
                if sock:
                    self._close_socket(sock)
                with self._state_lock:
                    self.connected = False
                    self.socket = None
                    self.membership = None
                self.log_error(f"connect() : failed {e=}")

    def leave(self):
        """disconnect() 의 별칭 - 의미상 "그룹 탈퇴"를 강조할 때 사용."""
        self.disconnect()

    def disconnect(self):
        """그룹에서 탈퇴(IP_DROP_MEMBERSHIP)하고 소켓을 닫는다. 참가 중이었으면 offline/disconnected 이벤트 발생."""
        with self._state_lock:
            was_connected = self.connected
            self.connected = False
            sock = self.socket
            self.socket = None
            membership = self.membership
            self.membership = None

        if sock:
            try:
                if membership:
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, membership)
            except Exception as e:
                self.log_error(f"disconnect() : failed to leave group {e=}")
            self._close_socket(sock)

        if was_connected:
            try:
                # emit: offline()
                self.emit("offline")
            except Exception as e:
                self.log_error(f"disconnect() : emit error {e=}")
        self.log_debug("disconnect() : disconnect signal sent")

    def send(self, msg: bytes | bytearray | str):
        """그룹 주소(group_ip:port)로 전송한다. 참가 중인 모든 멤버가 같이 받는다."""
        if not self.socket or not self.connected:
            return
        try:
            msg = to_bytes(msg)
            self.socket.sendto(msg, (self.group_ip, self.port))
            self.log_debug(f"send() : sending {msg=}")
        except Exception as e:
            self.log_error(f"send() : failed to send {msg=} {e=}")

    def _receive_loop(self, recv_sock: socket.socket):
        """그룹에서 오는 데이터를 받아 "received" 이벤트로 전달한다.

        소켓 에러로 루프가 죽으면(abnormal_exit) disconnect() 를 호출해 상태/멤버십을 정리한다.
        """
        self.log_debug("_receive_loop() : thread started")
        abnormal_exit = False
        while True:
            with self._state_lock:
                if not self.connected or self.socket is not recv_sock:
                    break
            try:
                data, addr = recv_sock.recvfrom(self.buffer_size)
                try:
                    self._emit_received(data, addr)
                except Exception as e:
                    self.log_error(f"_receive_loop() : emit error {e=}")
                self.log_debug(f"_receive_loop() : received {data=} {addr=}")
            except socket.timeout:
                continue
            except OSError as e:
                with self._state_lock:
                    abnormal_exit = self.connected and self.socket is recv_sock
                if abnormal_exit:
                    self.log_error(f"_receive_loop() : socket {e=}")
                break
            except Exception as e:
                with self._state_lock:
                    abnormal_exit = self.connected and self.socket is recv_sock
                if abnormal_exit:
                    self.log_error(f"_receive_loop() : receiving {e=}")
                break
        if abnormal_exit:
            # 소켓 에러로 루프가 죽었는데 connected 가 True 로 남는 것 방지 - 상태 정리 및 offline 알림
            self.disconnect()
        self.log_debug("_receive_loop() : thread ended")

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        # emit: received(event: ReceivedEvent)  — event.arguments["data"]: bytes
        self.emit("received", make_received_event(self, data, address))

    def _close_socket(self, sock: socket.socket):
        close_socket(sock)
