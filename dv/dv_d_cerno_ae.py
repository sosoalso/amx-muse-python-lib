# 마지막 수정일 : 20260713
# ---------------------------------------------------------------------------
# Televic D-Cerno AE 컨퍼런스(회의) 시스템 제어 드라이버
#
# 이 장비는 REST API(HTTP) 방식으로 제어한다.
#  - 명령 보내기 : PUT/DELETE 요청 (마이크 켜기/끄기, 발언 요청 등)
#  - 상태 받기   : GET /api/notification/events 를 "롱폴링" 방식으로 반복 호출
#
# 롱폴링(long polling)이란?
#  - 서버에 "이벤트 줘" 라고 요청을 보내면, 서버는 이벤트가 생길 때까지
#    응답을 안 주고 기다리다가(최대 event_timeout 초) 이벤트가 생기면 그때 응답한다.
#  - 응답을 받으면 곧바로 다시 요청을 보내서 계속 이벤트를 받는 구조다.
#  - 그래서 별도 스레드(_notification_loop)가 무한 반복하면서 이 일을 담당한다.
# ---------------------------------------------------------------------------
import json
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from lib.event_manager import EventManager
from lib.utility import CommonLogger, handle_exception, start_thread


class DCernoAe(CommonLogger, EventManager):
    # 장비의 기본 포트. https 여부에 따라 자동 선택된다.
    DEFAULT_HTTP_PORT = 9080
    DEFAULT_HTTPS_PORT = 9443

    def __init__(
        self,
        ip,                     # 장비 IP 주소
        token=None,             # API 인증 토큰 (있으면 Authorization 헤더에 붙임)
        port=None,              # 포트 직접 지정. None이면 https 여부에 따라 기본값 사용
        https=False,            # True면 https(9443), False면 http(9080)
        verify_ssl=False,       # https일 때 인증서 검증 여부 (장비는 보통 자체 서명이라 False)
        minimum_event_id=0,     # 이벤트 수신 시작 ID (이 번호부터 이벤트를 받겠다는 뜻)
        request_timeout=2.0,    # 일반 명령(GET/PUT/DELETE) 응답 대기 시간(초)
        event_timeout=35.0,     # 이벤트 롱폴링 대기 시간(초). 서버가 이벤트 없으면 이만큼 기다림
        reconnect_time=1.0,     # 통신 에러 후 재접속 시도까지 쉬는 시간(초)
        empty_event_sleep=0.05, # 빈 이벤트를 받았을 때 잠깐 쉬는 시간(초). CPU 과점유 방지용
    ):
        # EventManager 초기화 : 이 드라이버가 발생시킬 수 있는 이벤트 이름들을 등록한다.
        # 사용하는 쪽에서는 add_event_handler("mic_on", 함수) 식으로 구독하면 된다.
        super().__init__(
            "notification",      # 장비에서 온 모든 원본 이벤트 (가공 없이 그대로)
            "seat_changed",      # 좌석(seat) 상태가 갱신될 때마다 (마이크/요청 변화 없어도 발생)
            "mic_changed",       # 마이크 on/off 또는 발언요청 상태가 "변했을 때"만
            "mic_on",            # 마이크가 꺼짐 -> 켜짐으로 바뀌었을 때
            "mic_off",           # 마이크가 켜짐 -> 꺼짐으로 바뀌었을 때
            "mic_request",       # 발언 요청이 새로 들어왔을 때
            "speakers_changed",  # 발언자(마이크 켜진 좌석) 목록이 통째로 바뀌었을 때
            "requests_changed",  # 발언 요청 목록이 통째로 바뀌었을 때
            "online",            # 장비와 통신이 (다시) 되기 시작했을 때
            "offline",           # 장비와 통신이 끊겼을 때
            "error",             # 통신 에러가 발생했을 때 (error=예외객체 전달)
        )
        self.ip = ip
        self.token = token
        self.https = https
        # 포트를 안 줬으면(https=True -> 9443, False -> 9080) 자동 결정
        self.port = port or (self.DEFAULT_HTTPS_PORT if https else self.DEFAULT_HTTP_PORT)
        self.request_timeout = request_timeout
        self.event_timeout = event_timeout
        self.reconnect_time = reconnect_time
        self.empty_event_sleep = empty_event_sleep
        # 로그에 찍힐 이름 : 예) dcernoae_192.168.0.10_9080
        self.name = f"{__class__.__name__.lower()}_{ip}_{self.port}"
        # 좌석별 마지막 상태 저장소 : {좌석번호(int): 좌석상태(dict)}
        self.state = {}
        # 현재 마이크가 켜져 있는 좌석 번호들의 집합(set)
        self.active_mics = set()
        # 현재 발언 요청 중인 좌석 번호들의 집합(set)
        self.active_requests = set()
        # 마지막으로 처리한 이벤트 ID.
        # 다음 폴링 때 "이 ID + 1 이후 것만 줘" 라고 요청해서 중복 수신을 막는다.
        # minimum_event_id - 1 로 시작하면 첫 요청은 minimum_event_id 부터 받는다.
        self.last_event_id = minimum_event_id - 1 if minimum_event_id is not None else None
        # 이벤트 수신 루프 동작 여부 플래그 (False로 바꾸면 루프가 멈춘다)
        self.running = False
        # 이벤트 수신 루프를 돌리는 스레드 객체
        self._thread_notification = None
        # 직전 통신 상태 기억용. online/offline 이벤트를 "변할 때만" 내보내기 위함
        self._was_online = False
        # verify_ssl=False면 인증서 검증을 끈 SSL 컨텍스트를 사용 (자체 서명 인증서 대응)
        self._ssl_context = None if verify_ssl else ssl._create_unverified_context()

    @handle_exception
    def init(self):
        """드라이버 시작. 좌석 상태를 한번 읽어오고 이벤트 수신 루프를 켠다."""
        self.refresh_seats()
        self.start_notification()

    @handle_exception
    def start_notification(self):
        """이벤트 수신 루프(스레드) 시작. 이미 돌고 있으면 새로 만들지 않는다."""
        self.running = True
        if not self._thread_notification or not self._thread_notification.is_alive():
            # daemon=True : 메인 프로그램이 끝나면 이 스레드도 같이 종료됨
            self._thread_notification = threading.Thread(target=self._notification_loop, daemon=True)
            self._thread_notification.start()

    @handle_exception
    def stop_notification(self):
        """이벤트 수신 루프 정지 요청. 루프가 다음 반복에서 알아서 빠져나온다."""
        self.running = False

    # ------------------------------------------------------------------
    # 제어 명령들 (전부 비동기 : 별도 스레드에서 요청을 보내고 바로 리턴)
    # callback       : 성공 시 응답 데이터를 받는 함수
    # error_callback : 실패 시 예외를 받는 함수
    # ------------------------------------------------------------------

    @handle_exception
    def set_mic(self, seat, enable: bool, callback=None, error_callback=None):
        """지정한 좌석의 마이크를 켜거나(True) 끈다(False).
        마이크를 직접 켜는 것이므로 발언 요청 상태는 False로 함께 지운다."""
        body = {"microphoneOn": bool(enable), "requestingToSpeak": False}
        return self._request_async("PUT", f"/api/discussion/seats/{seat}", body=body, callback=callback, error_callback=error_callback)

    @handle_exception
    def mic_on(self, seat, callback=None, error_callback=None):
        """좌석 마이크 켜기. set_mic(seat, True)의 단축 함수."""
        return self.set_mic(seat, True, callback=callback, error_callback=error_callback)

    @handle_exception
    def mic_off(self, seat, callback=None, error_callback=None):
        """좌석 마이크 끄기. set_mic(seat, False)의 단축 함수."""
        return self.set_mic(seat, False, callback=callback, error_callback=error_callback)

    @handle_exception
    def set_request(self, seat, enable: bool, callback=None, error_callback=None):
        """지정한 좌석의 '발언 요청' 상태를 켜거나 끈다. (마이크 상태는 건드리지 않음)"""
        body = {"requestingToSpeak": bool(enable)}
        return self._request_async("PUT", f"/api/discussion/seats/{seat}", body=body, callback=callback, error_callback=error_callback)

    @handle_exception
    def request_mic(self, seat, callback=None, error_callback=None):
        """좌석에서 발언 요청 올리기. set_request(seat, True)의 단축 함수."""
        return self.set_request(seat, True, callback=callback, error_callback=error_callback)

    @handle_exception
    def clear_all_mics(self, callback=None, error_callback=None):
        """켜져 있는 모든 마이크를 한번에 끈다."""
        return self._request_async("DELETE", "/api/discussion/speakers", callback=callback, error_callback=error_callback)

    @handle_exception
    def all_mic_off(self, callback=None, error_callback=None):
        """clear_all_mics()와 동일. 다른 드라이버들과 이름을 맞추기 위한 별칭."""
        return self.clear_all_mics(callback=callback, error_callback=error_callback)

    @handle_exception
    def clear_delegate_mics(self, callback=None, error_callback=None):
        """대표(delegate) 좌석들의 마이크만 끈다. (의장 좌석은 유지)"""
        return self._request_async("DELETE", "/api/discussion/speakers/delegates", callback=callback, error_callback=error_callback)

    @handle_exception
    def clear_requests(self, callback=None, error_callback=None):
        """모든 발언 요청을 한번에 지운다."""
        return self._request_async("DELETE", "/api/discussion/requests", callback=callback, error_callback=error_callback)

    @handle_exception
    def refresh_seats(self, callback=None, error_callback=None):
        """전체 좌석 상태를 장비에서 새로 읽어와서 내부 상태(self.state 등)를 갱신한다.
        시작할 때, 재접속됐을 때, 이벤트 유실(discontinuity)이 감지됐을 때 호출된다."""

        def on_response(data):
            # 응답은 좌석 상태 dict들의 리스트. 좌석마다 상태 갱신 처리를 태운다.
            if isinstance(data, list):
                for seat_state in data:
                    self._handle_seat_changed(seat_state)
            if callback:
                callback(data)

        return self._request_async("GET", "/api/discussion/seats", callback=on_response, error_callback=error_callback)

    # ------------------------------------------------------------------
    # 이벤트 수신 (롱폴링 루프)
    # ------------------------------------------------------------------

    def _notification_loop(self):
        """별도 스레드에서 도는 무한 루프.
        장비에 이벤트를 요청 -> 받으면 처리 -> 다시 요청... 을 반복한다.
        에러가 나면 offline 처리하고 reconnect_time 만큼 쉬었다가 재시도한다."""
        while self.running:
            try:
                event = self._poll_events()  # 이벤트가 올 때까지 최대 event_timeout 초 대기
                self._set_online()           # 응답이 왔다 = 통신 정상 (필요시 online 이벤트 발생)
                if event is not None:
                    self._handle_notification(event)
                else:
                    # 이벤트 없이 빈 응답이 온 경우. 곧바로 재요청하면 CPU를 계속 쓰니 잠깐 쉰다.
                    time.sleep(self.empty_event_sleep)
            except Exception as e:
                # 타임아웃, 연결 거부 등 통신 실패 -> offline 처리 후 잠시 쉬고 재시도
                self._set_offline()
                self.log_error(f"_notification_loop() {e=}")
                self.emit("error", error=e)
                self._sleep_reconnect()

    def _poll_events(self):
        """장비에 이벤트 1건을 요청한다 (롱폴링).
        include-filter=Discussion : 회의(마이크/요청) 관련 이벤트만 받겠다는 뜻.
        minimum-id : 이미 처리한 이벤트(last_event_id) 다음 것부터 달라는 뜻."""
        params = {"include-filter": "Discussion"}
        if self.last_event_id is not None:
            params["minimum-id"] = str(self.last_event_id + 1)

        return self._request("GET", "/api/notification/events", params=params, timeout=self.event_timeout)

    def _handle_notification(self, event):
        """수신한 이벤트 1건을 해석해서 알맞은 처리 함수로 분배한다."""
        # 원본 이벤트를 그대로 알려주는 이벤트 (디버깅/커스텀 처리용)
        self.emit("notification", event=event)

        # discontinuity=True : "중간에 이벤트가 유실됐을 수 있다"는 서버의 알림.
        # 이 경우 이벤트만으로는 상태를 못 믿으니 전체 좌석 상태를 다시 읽어온다.
        if event.get("discontinuity"):
            self.refresh_seats()

        # 이벤트 ID를 기억해 둔다. 다음 폴링 때 이 ID 이후 것만 요청하기 위함.
        event_id = event.get("id")
        if isinstance(event_id, int):
            self.last_event_id = max(self.last_event_id, event_id) if self.last_event_id is not None else event_id

        # 이벤트 종류(name)에 따라 분기
        name = event.get("name")
        data = event["data"] if "data" in event else {}
        if name == "SeatChanged":
            # 좌석 1개의 상태 변화
            self._handle_seat_changed(data)
        elif name == "SpeakersChanged":
            # 발언자(마이크 켜진 좌석) "전체 목록"이 왔을 때
            self._handle_speakers_changed(data)
            self.emit("speakers_changed", data=data)
        elif name == "RequestsChanged":
            # 발언 요청 "전체 목록"이 왔을 때
            self._handle_requests_changed(data)
            self.emit("requests_changed", data=data)

    # ------------------------------------------------------------------
    # 상태 갱신 + 파생 이벤트 발생
    # ------------------------------------------------------------------

    def _handle_seat_changed(self, seat_state):
        """좌석 1개의 새 상태(seat_state dict)를 받아 내부 상태를 갱신하고,
        이전 상태와 비교해서 mic_on / mic_off / mic_request 등의 이벤트를 발생시킨다."""
        if not isinstance(seat_state, dict):
            return

        seat = seat_state.get("seatNumber")
        if seat is None:
            return

        seat = int(seat)
        # 비교를 위해 "이전" 상태를 먼저 꺼내둔다.
        # 처음 보는 좌석이면 prev_mic_on / prev_requesting 은 None (= 이전 상태 모름)
        prev_state = self.state.get(seat)
        prev_mic_on = prev_state.get("microphoneOn") if isinstance(prev_state, dict) else None
        prev_requesting = prev_state.get("requestingToSpeak") if isinstance(prev_state, dict) else None

        # 새 상태를 저장하고, 마이크/요청 집합(set)도 함께 갱신
        self.state[seat] = seat_state
        mic_on = bool(seat_state.get("microphoneOn"))
        requesting = bool(seat_state.get("requestingToSpeak"))
        if mic_on:
            self.active_mics.add(seat)
        else:
            self.active_mics.discard(seat)  # discard는 없어도 에러 안 남
        if requesting:
            self.active_requests.add(seat)
        else:
            self.active_requests.discard(seat)

        # seat_changed : 상태가 갱신될 때마다 무조건 발생
        self.emit("seat_changed", seat=seat, state=seat_state)
        # mic_changed : 마이크 또는 요청 상태가 "실제로 변했을 때"만 발생
        # (prev_mic_on is None = 처음 보는 좌석이므로 변화로 간주)
        if prev_mic_on is None or bool(prev_mic_on) != mic_on or bool(prev_requesting) != requesting:
            self.emit("mic_changed", seat=seat, value=mic_on, requesting=requesting, state=seat_state)

        # mic_on / mic_off : 마이크 상태 "전환" 시점에만 발생
        if prev_mic_on is None:
            # 처음 보는 좌석 : 켜져 있으면 mic_on만 알린다 (꺼져 있는 건 굳이 안 알림)
            if mic_on:
                self.emit("mic_on", seat=seat, state=seat_state)
        elif bool(prev_mic_on) != mic_on:
            # 꺼짐->켜짐 또는 켜짐->꺼짐으로 실제로 바뀐 경우
            if mic_on:
                self.emit("mic_on", seat=seat, state=seat_state)
            else:
                self.emit("mic_off", seat=seat, state=seat_state)
        # mic_request : 요청이 "새로 올라온" 시점에만 발생 (요청 취소는 이벤트 없음)
        if requesting and (prev_requesting is None or not bool(prev_requesting)):
            self.emit("mic_request", seat=seat, state=seat_state)

    def _handle_speakers_changed(self, seats):
        """발언자 전체 목록(seats)을 받아서, 기존에 알고 있던 목록과 비교해
        새로 켜진 좌석 / 새로 꺼진 좌석을 찾아 좌석별 갱신 처리를 태운다."""
        new_active = self._seat_set(seats)
        # 새 목록에는 있는데 기존 목록에 없던 좌석 = 새로 마이크 켜짐
        for seat in sorted(new_active - self.active_mics):
            self._set_seat_flags(seat, microphone_on=True)
        # 기존 목록에는 있는데 새 목록에 없는 좌석 = 마이크 꺼짐
        for seat in sorted(self.active_mics - new_active):
            self._set_seat_flags(seat, microphone_on=False)
        self.active_mics = new_active

    def _handle_requests_changed(self, seats):
        """발언 요청 전체 목록을 받아서 위와 같은 방식으로 차이를 반영한다."""
        new_requests = self._seat_set(seats)
        for seat in sorted(new_requests - self.active_requests):
            self._set_seat_flags(seat, requesting=True)
        for seat in sorted(self.active_requests - new_requests):
            self._set_seat_flags(seat, requesting=False)
        self.active_requests = new_requests

    def _set_seat_flags(self, seat, microphone_on=None, requesting=None):
        """좌석 상태 dict에서 마이크/요청 플래그만 바꿔서 _handle_seat_changed에 넘긴다.
        SpeakersChanged/RequestsChanged 이벤트는 좌석 번호 목록만 주기 때문에,
        저장해 둔 기존 상태를 복사한 뒤 해당 플래그만 덮어써서 처리하는 것."""
        state = dict(self.state.get(seat, {"seatNumber": seat}))  # 복사본을 만들어 원본 보존
        if microphone_on is not None:
            state["microphoneOn"] = microphone_on
        if requesting is not None:
            state["requestingToSpeak"] = requesting
        # 기존 상태에 해당 키가 아예 없었으면 현재 집합 기준으로 채워 넣는다
        state.setdefault("microphoneOn", seat in self.active_mics)
        state.setdefault("requestingToSpeak", seat in self.active_requests)
        self._handle_seat_changed(state)

    def _seat_set(self, seats):
        """좌석 번호 리스트를 int 집합(set)으로 변환. 숫자가 아닌 값은 조용히 건너뛴다."""
        if not isinstance(seats, list):
            return set()
        result = set()
        for seat in seats:
            try:
                result.add(int(seat))
            except (TypeError, ValueError):
                continue
        return result

    # ------------------------------------------------------------------
    # HTTP 통신 (low-level)
    # ------------------------------------------------------------------

    def _request_async(self, method, path, params=None, body=None, callback=None, error_callback=None):
        """HTTP 요청을 별도 스레드에서 보낸다.
        호출한 쪽은 응답을 기다리지 않고 바로 리턴받는다. (UI가 멈추지 않게 하기 위함)
        결과는 callback / error_callback 으로 전달된다."""

        def task():
            try:
                result = self._request(method, path, params=params, body=body, timeout=self.request_timeout)
                if callback:
                    callback(result)
            except Exception as e:
                self.log_error(f"_request_async() {method=} {path=} {e=}")
                self.emit("error", error=e)
                if error_callback:
                    error_callback(e)

        return start_thread(task)

    def _request(self, method, path, params=None, body=None, timeout=None):
        """실제 HTTP 요청을 보내고 응답을 파싱해서 리턴한다. (동기 = 응답 올 때까지 대기)
        body가 있으면 JSON으로 직렬화해서 보낸다."""
        url = self._url(path, params=params)
        data = None
        headers = self._headers()

        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=UTF-8"

        req = urllib.request.Request(url=url, data=data, headers=headers, method=method.upper())
        self.log_debug(f"_request() {method=} {url=} {body=}")

        try:
            with urllib.request.urlopen(req, timeout=timeout, context=self._ssl_context) as response:
                return self._decode_response(response)
        except urllib.error.HTTPError as e:
            # 204(No Content)는 "성공했지만 응답 본문 없음"이라 에러가 아니다.
            # urllib이 이걸 HTTPError로 던지는 경우가 있어서 여기서 걸러준다.
            if e.code == 204:
                return None
            raise

    def _decode_response(self, response):
        """HTTP 응답 본문을 해석한다.
        - 본문 없음(204 또는 빈 응답) -> None
        - Content-Type이 JSON       -> dict/list로 파싱해서 리턴
        - 그 외                      -> 원본 바이트 그대로 리턴"""
        if response.status == 204:
            return None

        raw = response.read()
        if not raw:
            return None

        content_type = response.headers.get("Content-Type", "")
        if "application/json" in content_type:
            return json.loads(raw.decode("utf-8"))
        return raw

    def _url(self, path, params=None):
        """요청 URL 조립. 예) http://192.168.0.10:9080/api/discussion/seats?minimum-id=5"""
        scheme = "https" if self.https else "http"
        url = f"{scheme}://{self.ip}:{self.port}{path}"
        if params:
            url += "?" + urllib.parse.urlencode(params, doseq=True)
        return url

    def _headers(self):
        """공통 요청 헤더. 토큰이 설정돼 있으면 Bearer 인증 헤더를 붙인다."""
        headers = {"Accept": "application/json", "Connection": "keep-alive"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    # ------------------------------------------------------------------
    # 온라인/오프라인 상태 관리
    # ------------------------------------------------------------------

    def _set_online(self):
        """통신 성공 시 호출. 오프라인이었다가 살아난 경우에만 online 이벤트를 내고,
        끊겨 있던 동안 놓친 상태를 따라잡기 위해 전체 좌석 상태를 다시 읽어온다."""
        if not self._was_online:
            self._was_online = True
            self.emit("online")
            self.refresh_seats()

    def _set_offline(self):
        """통신 실패 시 호출. 온라인이었다가 끊긴 경우에만 offline 이벤트를 낸다."""
        if self._was_online:
            self._was_online = False
            self.emit("offline")

    def _sleep_reconnect(self):
        """재접속 전 대기. 통째로 sleep(reconnect_time) 하지 않고 0.1초씩 쪼개서 자는 이유는,
        대기 중에 stop_notification()이 호출되면(running=False) 빨리 빠져나오기 위함이다."""
        end_time = time.time() + self.reconnect_time
        while self.running and time.time() < end_time:
            time.sleep(0.1)
