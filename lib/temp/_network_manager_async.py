# asyncio 기반 네트워크 매니저
# 표준 asyncio API 사용: asyncio.start_server, asyncio.open_connection, StreamReader/StreamWriter
# 기존 EventManager 상속으로 콜백 호환성 유지
import asyncio
from types import SimpleNamespace
from typing import Callable, Optional, Dict, Tuple
import socket as socket_module
from lib.event_manager import EventManager
from lib.utility import CommonLogger


class ReceiveListener:
    def __init__(self, register_listener: Callable):
        self._register_listener = register_listener

    def listen(self, listener):
        self._register_listener(listener)


DEFAULT_BUFFER_SIZE = 2048
DEFAULT_TCP_SERVER_CLIENT_TIMEOUT = 60.0
DEFAULT_UDP_SERVER_CLIENT_TIMEOUT = 60.0
DEFAULT_TCP_CLIENT_RECONNECT_TIME = 30.0
DEFAULT_UDP_CLIENT_RECONNECT_TIME = 60.0


class AsyncTcpServer(CommonLogger, EventManager):
    """asyncio 기반 TCP 서버 (표준 asyncio API 사용)"""

    def __init__(self, port: int, buffer_size: int = DEFAULT_BUFFER_SIZE, name: Optional[str] = None):
        super().__init__("received", "online", "offline", "connected", "disconnected")
        self.port = port
        self.name = name or f"asynctcpserver_{port}"
        self.buffer_size = buffer_size
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.client_timeout = DEFAULT_TCP_SERVER_CLIENT_TIMEOUT
        self.echo = False
        self._server = None
        self._clients: Dict[Tuple[str, int], dict] = {}
        self._clients_lock = asyncio.Lock()
        self._running = False
        self._main_task = None
        self._cleanup_task = None

    def online(self, handler):
        """온라인 이벤트 핸들러 등록"""
        self.on("online", handler)

    def offline(self, handler):
        """오프라인 이벤트 핸들러 등록"""
        self.on("offline", handler)

    def is_running(self):
        return self._running

    def start(self):
        """서버 시작 (이벤트 루프 필요)"""
        self.log_info("start() : server starting")
        if self._main_task:
            self.log_warn("start() : server already running")
            return
        try:
            loop = asyncio.get_running_loop()
            self._main_task = loop.create_task(self._run_server())
            self._cleanup_task = loop.create_task(self._cleanup_inactive_clients())
        except RuntimeError:
            self.log_error("start() : no running event loop")

    def stop(self):
        """서버 중지"""
        self.log_info("stop() : server stopping")
        self._running = False
        if self._server:
            self._server.close()
        if self._main_task:
            self._main_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        self.log_info("stop() : server stopped")

    def send_to(self, address: Tuple[str, int], data: bytes | str):
        """특정 클라이언트로 데이터 전송"""
        try:
            if isinstance(data, str):
                data = data.encode()
            if address in self._clients:
                writer = self._clients[address].get("writer")
                if writer:
                    writer.write(data)
                    # 비동기 작업이지만 동기 호출이므로 task 생성
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(writer.drain())
                    except RuntimeError:
                        pass
        except Exception as e:
            self.log_error(f"send_to() : failed to send {e=}")

    def send(self, data: bytes | str, exclude_address: Optional[Tuple[str, int]] = None):
        """모든 클라이언트로 브로드캐스트"""
        try:
            if isinstance(data, str):
                data = data.encode()
            for addr in list(self._clients.keys()):
                if addr != exclude_address:
                    self.send_to(addr, data)
        except Exception as e:
            self.log_error(f"send() : failed to send {e=}")

    async def _run_server(self):
        """메인 서버 루프"""
        self.log_debug("_run_server() : starting")
        try:
            self._server = await asyncio.start_server(
                self._handle_client,
                "0.0.0.0",
                self.port,
            )
            self._running = True
            self.log_info(f"_run_server() : listening on port {self.port}")
            async with self._server:
                await self._server.serve_forever()
        except Exception as e:
            self.log_error(f"_run_server() : server error {e=}")
            self._running = False

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """클라이언트 연결 처리"""
        addr = writer.get_extra_info("peername")
        self.log_debug(f"_handle_client() : client connected {addr=}")
        async with self._clients_lock:
            self._clients[addr] = {
                "reader": reader,
                "writer": writer,
                "last_seen": asyncio.get_event_loop().time(),
            }
        self.emit("connected", address=addr)
        self.emit("online", address=addr)
        try:
            while self._running:
                data = await reader.read(self.buffer_size)
                if not data:
                    break
                async with self._clients_lock:
                    if addr in self._clients:
                        self._clients[addr]["last_seen"] = asyncio.get_event_loop().time()
                self.log_debug(f"_handle_client() : received {data=} from {addr}")
                self._emit_received(data, addr)
                if self.echo:
                    writer.write(data)
                    await writer.drain()
        except asyncio.CancelledError:
            self.log_debug(f"_handle_client() : client task cancelled {addr=}")
        except Exception as e:
            self.log_error(f"_handle_client() : error {e=} {addr=}")
        finally:
            await self._close_client(addr, writer, emit_events=True)

    async def _close_client(self, addr: Tuple[str, int], writer: Optional[asyncio.StreamWriter], emit_events: bool = True):
        """클라이언트 연결 종료"""
        if writer:
            try:
                writer.close()
                await writer.wait_closed()
            except Exception as e:
                self.log_debug(f"_close_client() : error closing writer {e=}")
        async with self._clients_lock:
            removed = self._clients.pop(addr, None)
        if removed and emit_events:
            self.emit("offline", address=addr)
            self.emit("disconnected", address=addr)
            self.log_info(f"_close_client() : client disconnected {addr=}")

    async def _cleanup_inactive_clients(self):
        """타임아웃된 클라이언트 정리"""
        self.log_debug("_cleanup_inactive_clients() : started")
        while self._running:
            try:
                await asyncio.sleep(self.client_timeout // 2)
                current_time = asyncio.get_event_loop().time()
                async with self._clients_lock:
                    expired = [addr for addr, info in self._clients.items() if current_time - info["last_seen"] > self.client_timeout]
                for addr in expired:
                    async with self._clients_lock:
                        info = self._clients.pop(addr, None)
                    if info:
                        writer = info.get("writer")
                        await self._close_client(addr, writer, emit_events=True)
                        self.log_debug(f"_cleanup_inactive_clients() : removed {addr=}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log_error(f"_cleanup_inactive_clients() : error {e=}")

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        event = SimpleNamespace()
        event.source = self
        event.arguments = {"data": data, "address": address}
        self.emit("received", event)


class AsyncTcpClient(CommonLogger, EventManager):
    """asyncio 기반 TCP 클라이언트 (표준 asyncio API 사용)"""

    def __init__(
        self,
        ip: str,
        port: int,
        reconnect_time: float = DEFAULT_TCP_CLIENT_RECONNECT_TIME,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        name: Optional[str] = None,
    ):
        super().__init__("disconnected", "connected", "received", "online", "offline")
        self.name = name or f"asynctcpclient_{ip}_{port}"
        self.ip = ip
        self.port = port
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.reconnect_time = reconnect_time
        self.buffer_size = buffer_size
        self._reader: Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False
        self._reconnect = False
        self._main_task = None

    def online(self, handler):
        """온라인 이벤트 핸들러 등록"""
        self.on("online", handler)

    def offline(self, handler):
        """오프라인 이벤트 핸들러 등록"""
        self.on("offline", handler)

    def is_connected(self) -> bool:
        return self._connected

    def connect(self):
        """재접속 모드로 시작"""
        self.log_info("connect() : connecting")
        self._reconnect = True
        if self._connected:
            self.log_debug("connect() : already connected")
            return
        try:
            loop = asyncio.get_running_loop()
            if self._main_task is None or self._main_task.done():
                self._main_task = loop.create_task(self._connect_loop())
        except RuntimeError:
            self.log_error("connect() : no running event loop")

    def disconnect(self):
        """연결 종료"""
        self.log_info("disconnect() : disconnecting")
        self._reconnect = False
        self._set_state_disconnected()
        if self._writer:
            self._writer.close()
        if self._main_task:
            self._main_task.cancel()

    def send(self, message: bytes | str):
        """메시지 전송"""
        if isinstance(message, str):
            message = message.encode()
        if self._reconnect:
            if not (self._writer and self._connected):
                self.log_warn("send() : not connected")
                return
            try:
                self._writer.write(message)
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(self._writer.drain())
                except RuntimeError:
                    pass
                self.log_debug(f"send() : sent {message=}")
            except Exception as e:
                self.log_error(f"send() : failed to send {e=}")
                self._set_state_disconnected()
        else:
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._send_once(message))
            except RuntimeError:
                self.log_error("send() : no running event loop")

    def _set_state_connected(self):
        self._connected = True
        self.emit("connected")
        self.emit("online")

    def _set_state_disconnected(self):
        was_connected = self._connected
        self._connected = False
        if was_connected:
            self.emit("offline")
            self.emit("disconnected")

    async def _connect_loop(self):
        """재연결 루프"""
        while self._reconnect:
            try:
                self.log_debug(f"_connect_loop() : attempting to connect {self.ip}:{self.port}")
                self._reader, self._writer = await asyncio.wait_for(
                    asyncio.open_connection(self.ip, self.port),
                    timeout=10.0,
                )
                self._set_state_connected()
                await self._receive_loop()
            except asyncio.TimeoutError:
                self.log_error("_connect_loop() : connection timeout")
                self._set_state_disconnected()
                await asyncio.sleep(self.reconnect_time)
            except ConnectionRefusedError:
                self.log_error("_connect_loop() : connection refused")
                self._set_state_disconnected()
                await asyncio.sleep(self.reconnect_time)
            except Exception as e:
                self.log_error(f"_connect_loop() : error {e=}")
                self._set_state_disconnected()
                await asyncio.sleep(self.reconnect_time)

    async def _receive_loop(self):
        """수신 루프"""
        try:
            while self._connected and self._reconnect:
                if not self._reader:
                    break
                data = await self._reader.read(self.buffer_size)
                if not data:
                    self.log_info("_receive_loop() : server closed connection")
                    self._set_state_disconnected()
                    break
                self.log_debug(f"_receive_loop() : received {data=}")
                self._emit_received(data)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.log_error(f"_receive_loop() : error {e=}")
            self._set_state_disconnected()

    async def _send_once(self, message: bytes):
        """일회성 전송 (새 연결 생성)"""
        try:
            _reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.ip, self.port),
                timeout=5.0,
            )
            writer.write(message)
            await writer.drain()
            self.log_debug(f"_send_once() : sent {message=}")
            writer.close()
            await writer.wait_closed()
        except Exception as e:
            self.log_error(f"_send_once() : error {e=}")

    def _emit_received(self, data: bytes):
        event = SimpleNamespace()
        event.source = self
        event.arguments = {"data": data, "address": (self.ip, self.port)}
        self.emit("received", event)


class AsyncUdpServer(CommonLogger, EventManager):
    """asyncio 기반 UDP 서버 (DatagramProtocol 사용)"""

    def __init__(self, port: int, buffer_size: int = DEFAULT_BUFFER_SIZE, name: Optional[str] = None):
        super().__init__("received", "online", "offline")
        self.port = port
        self.name = name or f"asyncudpserver_{port}"
        self.buffer_size = buffer_size
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.client_timeout = DEFAULT_UDP_SERVER_CLIENT_TIMEOUT
        self.time_cleanup_clients = float(self.client_timeout // 2)
        self.echo = False
        self._transport = None
        self._protocol = None
        self._clients: Dict[Tuple[str, int], float] = {}
        self._running = False
        self._main_task = None
        self._cleanup_task = None

    def online(self, handler):
        """온라인 이벤트 핸들러 등록"""
        self.on("online", handler)

    def offline(self, handler):
        """오프라인 이벤트 핸들러 등록"""
        self.on("offline", handler)

    def is_running(self) -> bool:
        return self._running

    def start(self):
        """서버 시작"""
        self.log_info("start() : server starting")
        try:
            loop = asyncio.get_running_loop()
            self._main_task = loop.create_task(self._run_server())
            self._cleanup_task = loop.create_task(self._cleanup_inactive_clients())
        except RuntimeError:
            self.log_error("start() : no running event loop")

    def stop(self):
        """서버 중지"""
        self.log_info("stop() : server stopping")
        self._running = False
        if self._transport:
            self._transport.close()
        if self._main_task:
            self._main_task.cancel()
        if self._cleanup_task:
            self._cleanup_task.cancel()
        self.log_info("stop() : server stopped")

    def send_to(self, host: str, port: int, data: bytes | str):
        """특정 주소로 UDP 패킷 전송"""
        try:
            if isinstance(data, str):
                data = data.encode()
            if self._transport:
                self._transport.sendto(data, (host, port))
                self.log_debug(f"send_to() : sent to {host}:{port}")
        except Exception as e:
            self.log_error(f"send_to() : failed to send {e=}")

    def send(self, data: bytes | str, exclude_address: Optional[Tuple[str, int]] = None):
        """모든 알려진 클라이언트로 브로드캐스트"""
        try:
            if isinstance(data, str):
                data = data.encode()
            for addr in list(self._clients.keys()):
                if addr != exclude_address:
                    self.send_to(addr[0], addr[1], data)
        except Exception as e:
            self.log_error(f"send() : failed to send {e=}")

    async def _run_server(self):
        """UDP 서버 실행"""
        self.log_debug("_run_server() : starting")
        try:
            loop = asyncio.get_running_loop()
            self._transport, self._protocol = await loop.create_datagram_endpoint(
                self._make_datagram_protocol,
                local_addr=("0.0.0.0", self.port),
            )
            self._running = True
            self.log_info(f"_run_server() : listening on port {self.port}")
            while self._running:
                await asyncio.sleep(0.1)
        except Exception as e:
            self.log_error(f"_run_server() : server error {e=}")
            self._running = False

    def _make_datagram_protocol(self):
        """DatagramProtocol 생성"""
        return _UdpServerProtocol(self)

    async def _cleanup_inactive_clients(self):
        """타임아웃된 클라이언트 정리"""
        self.log_debug("_cleanup_inactive_clients() : started")
        while self._running:
            try:
                await asyncio.sleep(self.time_cleanup_clients)
                current_time = asyncio.get_event_loop().time()
                expired = [addr for addr, last_seen in self._clients.items() if current_time - last_seen > self.client_timeout]
                for addr in expired:
                    self._clients.pop(addr, None)
                    self.emit("offline", address=addr)
                    self.log_debug(f"_cleanup_inactive_clients() : removed {addr=}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log_error(f"_cleanup_inactive_clients() : error {e=}")

    def _emit_received(self, data: bytes, address: Tuple[str, int]):
        event = SimpleNamespace()
        event.source = self
        event.arguments = {"data": data, "address": address}
        self.emit("received", event)


class _UdpServerProtocol(asyncio.DatagramProtocol):
    """UDP 서버 프로토콜"""

    def __init__(self, server: AsyncUdpServer):
        self.server = server
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        self.server.log_debug(f"datagram_received() : {data=} from {addr=}")
        current_time = asyncio.get_event_loop().time()
        # noqa: Access to protected member necessary for UDP server protocol
        if addr not in self.server._clients:
            self.server._clients[addr] = current_time
            self.server.emit("online", address=addr)
        else:
            self.server._clients[addr] = current_time
        # noqa: Access to protected member necessary for UDP server protocol
        self.server._emit_received(data, addr)
        if self.server.echo and self.transport:
            self.transport.sendto(data, addr)

    def error_received(self, exc):
        self.server.log_error(f"error_received() : {exc=}")

    def connection_lost(self, exc):
        if exc:
            self.server.log_error(f"connection_lost() : {exc=}")


class AsyncUdpClient(CommonLogger, EventManager):
    """asyncio 기반 UDP 클라이언트"""

    def __init__(
        self,
        ip: str,
        port: int,
        reconnect_time: float = DEFAULT_UDP_CLIENT_RECONNECT_TIME,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        bound_port: Optional[int] = None,
        name: Optional[str] = None,
    ):
        super().__init__("connected", "received", "online", "offline", "disconnected")
        self.name = name or f"asyncudpclient_{ip}_{port}"
        self.ip = ip
        self.port = port
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self.buffer_size = buffer_size
        self.bound_port = bound_port
        self.bind_port = None
        self.reconnect_time = reconnect_time
        self.time_monitor_connection = float(self.reconnect_time // 2)
        self._transport = None
        self._protocol = None
        self._connected = False
        self._main_task = None
        self._monitor_task = None

    def online(self, handler):
        """온라인 이벤트 핸들러 등록"""
        self.on("online", handler)

    def offline(self, handler):
        """오프라인 이벤트 핸들러 등록"""
        self.on("offline", handler)

    def is_connected(self) -> bool:
        return self._connected

    def connect(self):
        """연결 시작"""
        self.log_info("connect() : connecting")
        if self._connected:
            self.log_debug("connect() : already connected")
            return
        try:
            loop = asyncio.get_running_loop()
            if self._main_task is None or self._main_task.done():
                self._main_task = loop.create_task(self._setup_endpoint())
                self._monitor_task = loop.create_task(self._monitor_connection())
        except RuntimeError:
            self.log_error("connect() : no running event loop")

    def disconnect(self):
        """연결 종료"""
        self.log_info("disconnect() : disconnecting")
        self._set_state_disconnected()
        if self._transport:
            self._transport.close()
        if self._main_task:
            self._main_task.cancel()
        if self._monitor_task:
            self._monitor_task.cancel()

    def send(self, message: bytes | str):
        """메시지 전송"""
        if isinstance(message, str):
            message = message.encode()
        try:
            if self._transport:
                self._transport.sendto(message, (self.ip, self.port))
                self.log_debug(f"send() : sent {message=}")
            else:
                self.log_warn("send() : not connected")
        except Exception as e:
            self.log_error(f"send() : failed to send {e=}")

    def _set_state_connected(self):
        self._connected = True
        self.emit("connected")
        self.emit("online")

    def _set_state_disconnected(self):
        was_connected = self._connected
        self._connected = False
        if was_connected:
            self.emit("offline")
            self.emit("disconnected")

    async def _setup_endpoint(self):
        """UDP 엔드포인트 생성"""
        try:
            loop = asyncio.get_running_loop()
            local_addr = ("0.0.0.0", self.bound_port) if self.bound_port else None
            self._transport, self._protocol = await loop.create_datagram_endpoint(
                self._make_datagram_protocol,
                local_addr=local_addr,
                remote_addr=(self.ip, self.port),
            )
            if local_addr is None:
                self.bind_port = self._transport.get_extra_info("sockname")[1]
            else:
                self.bind_port = self.bound_port
            self._set_state_connected()
            self.log_info(f"_setup_endpoint() : connected from port {self.bind_port}")
        except Exception as e:
            self.log_error(f"_setup_endpoint() : error {e=}")
            self._set_state_disconnected()

    def _make_datagram_protocol(self):
        """DatagramProtocol 생성"""
        return _UdpClientProtocol(self)

    async def _monitor_connection(self):
        """연결 모니터링"""
        while self._connected:
            try:
                await asyncio.sleep(self.time_monitor_connection)
                # UDP는 상태 확인이 어려우므로 기본적으로 연결 상태 유지
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.log_error(f"_monitor_connection() : error {e=}")

    def _emit_received(self, data: bytes):
        event = SimpleNamespace()
        event.source = self
        event.arguments = {"data": data, "address": (self.ip, self.port)}
        self.emit("received", event)


class _UdpClientProtocol(asyncio.DatagramProtocol):
    """UDP 클라이언트 프로토콜"""

    def __init__(self, client: AsyncUdpClient):
        self.client = client
        self.transport: Optional[asyncio.DatagramTransport] = None

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        self.client.log_debug(f"datagram_received() : {data=} from {addr=}")
        # noqa: Access to protected member necessary for UDP client protocol
        self.client._emit_received(data)

    def error_received(self, exc):
        self.client.log_error(f"error_received() : {exc=}")

    def connection_lost(self, exc):
        if exc:
            self.client.log_error(f"connection_lost() : {exc=}")
        # noqa: Access to protected member necessary for UDP client protocol
        self.client._set_state_disconnected()


class AsyncMulticastServer(CommonLogger, EventManager):
    """asyncio 기반 멀티캐스트 서버 (그룹 송신)"""

    def __init__(
        self,
        group: str,
        port: int,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        name: Optional[str] = None,
    ):
        super().__init__("sent", "online", "offline")
        self.group = group
        self.port = port
        self.name = name or f"asyncmulticastserver_{group}_{port}"
        self.buffer_size = buffer_size
        self._transport = None
        self._protocol = None
        self._connected = False
        self._main_task = None

    def online(self, handler):
        """온라인 이벤트 핸들러 등록"""
        self.on("online", handler)

    def offline(self, handler):
        """오프라인 이벤트 핸들러 등록"""
        self.on("offline", handler)

    def is_connected(self) -> bool:
        return self._connected

    def connect(self):
        """멀티캐스트 엔드포인트 생성"""
        self.log_info(f"connect() : joining multicast group {self.group}:{self.port}")
        try:
            loop = asyncio.get_running_loop()
            if self._main_task is None or self._main_task.done():
                self._main_task = loop.create_task(self._setup_multicast())
        except RuntimeError:
            self.log_error("connect() : no running event loop")

    def disconnect(self):
        """멀티캐스트 연결 종료"""
        self.log_info("disconnect() : leaving multicast group")
        self._connected = False
        if self._transport:
            self._transport.close()
        if self._main_task:
            self._main_task.cancel()
        self.emit("offline")

    def send(self, message: bytes | str):
        """멀티캐스트 그룹으로 메시지 송신"""
        if isinstance(message, str):
            message = message.encode()
        try:
            if self._transport:
                self._transport.sendto(message, (self.group, self.port))
                self.log_debug(f"send() : sent to {self.group}:{self.port}")
                self.emit("sent")
            else:
                self.log_warn("send() : not connected")
        except Exception as e:
            self.log_error(f"send() : failed to send {e=}")

    async def _setup_multicast(self):
        """멀티캐스트 엔드포인트 설정"""
        try:
            loop = asyncio.get_running_loop()
            self._transport, self._protocol = await loop.create_datagram_endpoint(
                self._make_datagram_protocol,
                local_addr=("0.0.0.0", self.port),
                allow_broadcast=True,
            )
            self._connected = True
            self.emit("online")
            self.log_info(f"_setup_multicast() : joined group {self.group}:{self.port}")
            while self._connected:
                await asyncio.sleep(0.1)
        except Exception as e:
            self.log_error(f"_setup_multicast() : error {e=}")
            self._connected = False

    def _make_datagram_protocol(self):
        """DatagramProtocol 생성"""
        return _MulticastServerProtocol(self)


class _MulticastServerProtocol(asyncio.DatagramProtocol):
    """멀티캐스트 서버 프로토콜"""

    def __init__(self, server: "AsyncMulticastServer"):
        self.server = server
        self.transport = None

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport
        # 멀티캐스트 루프백 비활성화 (다른 호스트만 받음)
        try:
            import socket

            sock = transport.get_extra_info("socket")
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 0)
        except Exception as e:
            self.server.log_error(f"connection_made() : failed to set multicast loop {e=}")

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        pass  # 서버는 수신하지 않음

    def error_received(self, exc):
        self.server.log_error(f"error_received() : {exc=}")

    def connection_lost(self, exc):
        if exc:
            self.server.log_error(f"connection_lost() : {exc=}")


class AsyncMulticastClient(CommonLogger, EventManager):
    """asyncio 기반 멀티캐스트 클라이언트 (그룹 수신)"""

    def __init__(
        self,
        group: str,
        port: int,
        interface: Optional[str] = None,
        buffer_size: int = DEFAULT_BUFFER_SIZE,
        name: Optional[str] = None,
    ):
        super().__init__("received", "online", "offline", "connected", "disconnected")
        self.group = group
        self.port = port
        self.interface = interface or "0.0.0.0"
        self.name = name or f"asyncmulticastclient_{group}_{port}"
        self.buffer_size = buffer_size
        self.receive = ReceiveListener(lambda listener: self.on("received", listener))
        self._transport = None
        self._protocol = None
        self._connected = False
        self._main_task = None

    def online(self, handler):
        """온라인 이벤트 핸들러 등록"""
        self.on("online", handler)

    def offline(self, handler):
        """오프라인 이벤트 핸들러 등록"""
        self.on("offline", handler)

    def is_connected(self) -> bool:
        return self._connected

    def join(self):
        """멀티캐스트 그룹 가입"""
        self.log_info(f"join() : joining multicast group {self.group}:{self.port}")
        try:
            loop = asyncio.get_running_loop()
            if self._main_task is None or self._main_task.done():
                self._main_task = loop.create_task(self._setup_multicast())
        except RuntimeError:
            self.log_error("join() : no running event loop")

    def leave(self):
        """멀티캐스트 그룹 탈출"""
        self.log_info("leave() : leaving multicast group")
        self._connected = False
        if self._transport:
            self._transport.close()
        if self._main_task:
            self._main_task.cancel()
        self.emit("disconnected")
        self.emit("offline")

    def _set_state_connected(self):
        self._connected = True
        self.emit("connected")
        self.emit("online")

    async def _setup_multicast(self):
        """멀티캐스트 엔드포인트 설정"""
        try:
            loop = asyncio.get_running_loop()
            # 소켓 생성 및 멀티캐스트 옵션 설정
            sock = socket_module.socket(socket_module.AF_INET, socket_module.SOCK_DGRAM)

            # 바인드 전에 모든 socket 옵션 설정 (Windows 호환성)
            try:
                sock.setsockopt(socket_module.SOL_SOCKET, socket_module.SO_REUSEADDR, 1)
                self.log_debug("_setup_multicast() : SO_REUSEADDR configured")
            except OSError as e:
                self.log_warn(f"_setup_multicast() : SO_REUSEADDR configuration failed {e=}")

            # macOS 호환성을 위해 SO_REUSEPORT 설정 시도
            try:
                so_reuseport = getattr(socket_module, "SO_REUSEPORT", None)
                if so_reuseport is not None:
                    sock.setsockopt(socket_module.SOL_SOCKET, so_reuseport, 1)
                    self.log_debug("_setup_multicast() : SO_REUSEPORT configured")
            except (AttributeError, OSError):
                pass

            # 바인드: 멀티캐스트 수신은 INADDR_ANY (0.0.0.0)로 바인드
            try:
                sock.bind(("0.0.0.0", self.port))
                self.log_debug(f"_setup_multicast() : bind successful 0.0.0.0:{self.port}")
            except OSError as e:
                self.log_error(f"_setup_multicast() : bind failed {e=}")
                raise

            # 멀티캐스트 그룹 JOIN (0.0.0.0 = 모든 인터페이스)
            try:
                group_bin = socket_module.inet_aton(self.group)
                all_interfaces = socket_module.inet_aton("0.0.0.0")
                mreq = group_bin + all_interfaces
                sock.setsockopt(socket_module.IPPROTO_IP, socket_module.IP_ADD_MEMBERSHIP, mreq)
                self.log_debug("_setup_multicast() : IP_ADD_MEMBERSHIP configured")
            except OSError as e:
                self.log_error(f"_setup_multicast() : IP_ADD_MEMBERSHIP failed {e=}")
                raise

            # 루프백 활성화 (같은 호스트의 전송도 수신)
            try:
                sock.setsockopt(socket_module.IPPROTO_IP, socket_module.IP_MULTICAST_LOOP, 1)
                self.log_debug("_setup_multicast() : IP_MULTICAST_LOOP configured")
            except OSError as e:
                self.log_error(f"_setup_multicast() : IP_MULTICAST_LOOP failed {e=}")
                raise

            sock.setblocking(False)

            self._transport, self._protocol = await loop.create_datagram_endpoint(
                self._make_datagram_protocol,
                sock=sock,
            )
            self._set_state_connected()
            self.log_info(f"_setup_multicast() : joined group {self.group}:{self.port}")
            while self._connected:
                await asyncio.sleep(0.1)
        except Exception as e:
            self.log_error(f"_setup_multicast() : {e=}")
            self._connected = False

    def _make_datagram_protocol(self):
        """DatagramProtocol 생성"""
        return _MulticastClientProtocol(self)

    def _emit_received(self, data: bytes, addr: Tuple[str, int]):
        event = SimpleNamespace()
        event.source = self
        event.arguments = {"data": data, "address": addr}
        self.emit("received", event)


class _MulticastClientProtocol(asyncio.DatagramProtocol):
    """멀티캐스트 클라이언트 프로토콜"""

    def __init__(self, client: AsyncMulticastClient):
        self.client = client
        self.transport = None

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        self.client.log_debug(f"datagram_received() : {data=} from {addr=}")
        # noqa: Access to protected member necessary for multicast client protocol
        self.client._emit_received(data, addr)

    def error_received(self, exc):
        self.client.log_error(f"error_received() : {exc=}")

    def connection_lost(self, exc):
        if exc:
            self.client.log_error(f"connection_lost() : {exc=}")
        self.client._connected = False
