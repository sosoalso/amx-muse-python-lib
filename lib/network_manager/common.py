"""network_manager 공용 헬퍼/상수 모듈.

TCP/UDP 클라이언트·서버가 공통으로 쓰는 수신 리스너 어댑터, bytes 변환,
수신 이벤트 객체 생성, 안전한 소켓 종료 함수와 기본 타임아웃 상수를 모아둔다.
"""

import socket
from types import SimpleNamespace
from typing import Callable


class ReceiveListener:
    """수신 이벤트 등록용 어댑터.

    AMX MUSE 네이티브 디바이스의 `dv.receive.listen(handler)` 형태와 같은
    사용법을 제공하기 위한 얇은 래퍼. 내부적으로는 EventManager 의
    "received" 이벤트에 리스너를 등록하는 함수만 위임받아 호출한다.
    """

    def __init__(self, register_listener: Callable):
        self._register_listener = register_listener

    def listen(self, listener):
        """수신 콜백을 등록한다. 콜백은 event(.arguments["data"]) 를 받는다."""
        self._register_listener(listener)


def to_bytes(data: bytes | bytearray | str) -> bytes | bytearray:
    """str 이면 UTF-8 로 인코딩하고, bytes/bytearray 는 그대로 돌려준다."""
    return data.encode() if isinstance(data, str) else data


def make_received_event(source, data: bytes, address: tuple[str, int]):
    """수신 이벤트 객체를 만든다.

    MUSE 네이티브 이벤트와 비슷한 모양(event.source, event.arguments)으로
    맞춰서, 리스너 쪽에서 event.arguments["data"] / ["address"] 로 꺼내 쓴다.
    """
    event = SimpleNamespace()
    event.source = source
    event.arguments = {"data": data, "address": address}
    return event


def close_socket(sock: socket.socket, shutdown=False):
    """소켓을 예외 없이 닫는다.

    shutdown=True 면 close 전에 양방향 shutdown 을 먼저 시도한다
    (TCP 에서 상대에게 종료를 알리고 blocking recv 를 깨우는 용도).
    이미 닫힌 소켓이어도 OSError 를 삼켜 안전하게 여러 번 호출할 수 있다.
    """
    if shutdown:
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
    try:
        sock.close()
    except OSError:
        pass


# ---- 기본값 상수 ---- #
# 버퍼 크기: recv 한 번에 읽는 최대 바이트 수
DEFAULT_BUFFER_SIZE = 2048
# 서버가 무응답 클라이언트를 목록에서 정리하기까지의 시간(초)
DEFAULT_TCP_SERVER_CLIENT_TIMEOUT = 30.0
DEFAULT_UDP_SERVER_CLIENT_TIMEOUT = 30.0
# TCP 클라이언트: 연결 실패/끊김 후 재시도까지 대기 시간(초)
DEFAULT_TCP_CLIENT_RECONNECT_TIME = 30.0
# TCP 클라이언트: recv 블로킹 타임아웃(초) - 짧게 잡아 종료 플래그를 자주 확인
DEFAULT_TCP_CLIENT_SOCKET_TIMEOUT = 0.3
# UDP 클라이언트: 이 시간(초) 동안 수신이 없으면 소켓을 재생성
DEFAULT_UDP_CLIENT_RECONNECT_TIME = 30.0
# TCP 클라이언트: connect() 자체의 타임아웃(초)
DEFAULT_TCP_CLIENT_CONNECT_TIMEOUT = 3.0
