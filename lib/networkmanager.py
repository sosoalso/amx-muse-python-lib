# ---------------------------------------------------------------------------- #
import socket
import threading

# import time
from concurrent.futures import ThreadPoolExecutor

from lib.eventmanager import EventManager


# ---------------------------------------------------------------------------- #
class TcpClient(EventManager):
    """
    TcpClient 클래스는 TCP 클라이언트 소켓을 관리하고 서버와의 통신을 처리합니다.
    Attributes:
        BUFFER_SIZE (int): 수신 버퍼 크기.
        name (str): 클라이언트 이름.
        ip (str): 서버 IP 주소.
        port (int): 서버 포트 번호.
        reconnect (bool): 재연결 여부.
        time_reconnect (int): 재연결 시도 간격 (초).
        connected (bool): 연결 상태.
        socket (socket): 소켓 객체.
        receive_callback (function): 수신 콜백 함수.
        executor (ThreadPoolExecutor): 스레드 풀 실행자.
        lock (threading.Lock): 스레드 동기화용 락.
    """

    """
    TcpClient의 생성자.
    Args:
        name (str): 클라이언트 이름.
        ip (str): 서버 IP 주소.
        port (int): 서버 포트 번호.
        reconnect (bool, optional): 재연결 여부. 기본값은 True.
        time_reconnect (int, optional): 재연결 시도 간격 (초). 기본값은 5.
    """
    """
    수신 콜백 함수를 설정합니다.
    Args:
        callback (function): 수신 콜백 함수.
    """
    """
    서버에 연결을 시도합니다.
    """
    """
    서버에 연결을 시도하고, 연결이 실패하면 재연결을 시도합니다.
    """
    """
    재연결을 처리합니다.
    """
    """
    수신 스레드를 실행합니다.
    """
    """
    서버로부터 메시지를 수신하고, 수신 콜백 함수를 호출합니다.
    """
    """
    바이트 메시지를 서버로 전송합니다.
    Args:
        message (bytes): 전송할 바이트 메시지.
    """
    """
    문자열 메시지를 서버로 전송합니다.
    Args:
        message (str): 전송할 문자열 메시지.
    """
    """
    서버와의 연결을 종료합니다.
    """
    """
    연결 상태를 반환합니다.
    Returns:
        bool: 연결 상태.
    """
    BUFFER_SIZE = 1024

    def __init__(self, name, ip, port, reconnect=True, time_reconnect=5):
        super().__init__("connected")
        self.name = name
        self.ip = ip
        self.port = port
        self.reconnect = reconnect
        self.time_reconnect = time_reconnect
        self.connected = False
        self.socket = None
        self.receive_callback = None
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.lock = threading.Lock()

    def set_receive_callback(self, callback):
        self.receive_callback = callback

    def connect(self):
        if not self.connected:
            self.executor.submit(self._connect)

    def _connect(self):
        while not self.connected:
            try:
                with self.lock:
                    self.socket = socket.create_connection((self.ip, self.port))
                    if self.socket:
                        self.connected = True
                        self._run_thread_receive()
            except ConnectionRefusedError as e:
                # time.sleep(self.time_reconnect)
                threading.Event().wait(self.time_reconnect)

                if not self.reconnect:
                    break
            except TimeoutError as e:
                # time.sleep(self.time_reconnect)
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break
            except Exception as e:
                # time.sleep(self.time_reconnect)
                threading.Event().wait(self.time_reconnect)
                if not self.reconnect:
                    break

    def _handle_reconnect(self):
        if self.reconnect:
            self.connect()

    def _run_thread_receive(self):
        self.executor.submit(self._receive)
        self.trigger_event("connected")

    def _receive(self):
        while self.socket and self.connected:
            try:
                msg = self.socket.recv(self.BUFFER_SIZE)
                if msg and self.receive_callback is not None:
                    self.receive_callback(msg)
            except Exception as e:
                with self.lock:
                    self.connected = False
                if self.reconnect:
                    self.connect()
                break

    def send_byte(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendall(message)
            except Exception as e:
                with self.lock:
                    self.connected = False
                self._handle_reconnect()

    def send(self, message):
        if self.socket and self.connected:
            try:
                self.socket.sendall(bytes(message, "UTF-8"))
            except Exception as e:
                with self.lock:
                    self.connected = False
                self._handle_reconnect()

    def disconnect(self):
        if self.socket and self.connected:
            try:
                self.socket.close()
            finally:
                with self.lock:
                    self.socket = None
                    self.connected = False

    def is_connected(self):
        return self.connected


# ---------------------------------------------------------------------------- #
class UdpClient:
    def __init__(self, name, ip, port):
        self.name = name
        self.ip = ip
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, message):
        try:
            self.socket.sendto(bytes(message, "UTF-8"), (self.ip, self.port))
        except Exception as e:
            pass

    def send_byte(self, message):
        try:
            self.socket.sendto(message, (self.ip, self.port))
        except Exception as e:
            pass

    def close(self):
        try:
            self.socket.close()
        except Exception as e:
            pass

    def open(self):
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        except Exception as e:
            pass


# ---------------------------------------------------------------------------- #
class UdpServer:
    BUFFER_SIZE = 1024

    def __init__(self, port):
        self.port = port
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.bind(("", self.port))
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.running = False
        self.receive_callback = None

    def start_server_thread(self):
        self.running = True
        self.executor.submit(self._start_server)

    def _start_server(self):
        while self.running:
            try:
                data, addr = self.socket.recvfrom(self.BUFFER_SIZE)
                if self.receive_callback is not None:
                    self.receive_callback(data=data, addr=addr)
            except Exception as e:
                if not self.running:
                    break

    def set_receive_callback(self, callback):
        self.receive_callback = callback

    def stop_server(self):
        self.running = False
        self.socket.close()
        self.executor.shutdown(wait=True)


# ---------------------------------------------------------------------------- #
