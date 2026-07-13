# AMX MUSE Python Lib

AMX MUSE 컨트롤러(터치패널 기반 AV 제어 시스템)로 작업하면서 개인적으로 편하려고 소소하게 만들어 쓰고 있는 파이썬 공용 라이브러리 + 장비 드라이버 모음입니다.
거창한 프레임워크는 아니고, 매번 반복되는 부분(이벤트 관리, 통신, 터치패널 연동 등)을 저 나름대로 정리해 둔 것에 가깝습니다. 외부 패키지 설치 없이 표준 라이브러리만으로 동작합니다.

## 이게 뭔가요?

AMX MUSE는 NetLinx 대신 파이썬으로 프로그래밍하는 AMX 컨트롤러 플랫폼입니다. MUSE로 AV 제어 프로그램 짤 때마다 매번 새로 만들게 되는 것들 — 이벤트 관리, 재연결되는 TCP/UDP 통신, 터치패널 채널/레벨 연동, 스케줄러, 설정 저장 등 — 을 제 나름대로 정리해서 재사용하고 있습니다.

- **`lib/`** — MUSE 런타임 위에 얹는 범용 인프라. 특정 장비 브랜드와 무관하게 어떤 프로젝트에서나 재사용 가능.
- **`dv/`** — `lib/`을 조합해서 실제 서드파티 AV 장비(프로젝터, 매트릭스, 카메라, 컨퍼런스 시스템 등)를 브랜드별 프로토콜로 제어하는 드라이버들.

MUSE 컨트롤러가 아닌 일반 PC 환경에서도 (mojo 런타임 없이) `lib/utility.py`의 `CommonLogger`가 `print`로 폴백해서, 로직 테스트 정도는 로컬에서도 돌려볼 수 있습니다.

## 폴더 구조

```
lib/                    범용 인프라
├── event_manager.py    이벤트 pub/sub 코어 (on/off/emit/once) — 거의 모든 클래스가 상속
├── utility.py          CommonLogger, 스레드 헬퍼, handle_exception/debounce/pulse 데코레이터
├── tp.py               MUSE 터치패널 채널/레벨/명령(^TXT, ^PGE 등) 저수준 래퍼
├── button.py           (tp, port, 번호)당 핸들러 하나만 만들도록 캐싱하는 버튼/레벨 등록 진입점
├── button_handler.py   눌림/뗌 원시 이벤트 → push/release/hold/repeat 액션으로 변환 (tp에 hold/repeat가 기본으로 없어서 답답해서 만듦)
├── idevice.py          MUSE 컨트롤러 내장 포트(Serial/IO/IR/Relay) 제어 래퍼
├── scheduler.py        setTimeout/setInterval 스타일 스레드 스케줄러
├── timeline.py         NetLinx timeline 재구현 (시간표 기반 순차 이벤트)
├── userdata.py         설정/상태를 JSON 파일로 영속화하는 key-value 저장소
├── ui_menu.py          터치패널 페이지 전환/메뉴 팝업 내비게이션 헬퍼
├── simple_url_requests.py  표준 라이브러리(urllib)만으로 만든 비동기 HTTP 클라이언트
├── mic_manager.py      회의실 마이크 on/off 순서 관리 (카메라 트래킹 연동)
├── camtrack_preset.py  좌석/마이크 ↔ 카메라 프리셋 매핑 저장소
├── bss_controller.py   BSS Soundweb London DSP 상위 래퍼
├── london_controller.py BSS London DI 프로토콜(TCP) 구현
└── network_manager/    TCP/UDP 클라이언트·서버, 멀티캐스트 그룹
    ├── tcp_client.py   자동 재연결 TCP 클라이언트
    ├── tcp_server.py   다중 클라이언트 TCP 서버
    ├── udp_client.py   UDP 클라이언트 (연결 유지 흉내 + 1회성 전송)
    ├── udp_server.py   UDP 서버 (발신자 목록 추적)
    └── multicast_group.py  멀티캐스트 그룹 join/leave (AV-over-IP 상태 브로드캐스트)

dv/                     실제 장비 드라이버 (브랜드/모델별 프로토콜 구현)
```

## 핵심 개념

### 1. EventManager — 모든 것의 기반

`lib/event_manager.py`의 `EventManager`를 상속하면 그 클래스는 곧바로 이벤트 발행자가 됩니다.

```python
class MyDevice(CommonLogger, EventManager):
    def __init__(self):
        super().__init__("power", "mute")   # 이 클래스가 낼 수 있는 이벤트 이름을 미리 등록

    def turn_on(self):
        self.power = True
        self.emit("power", value=True)      # 상태가 바뀌면 emit

device = MyDevice()
device.on("power", lambda value: print(f"전원: {value}"))  # 구독
```

핸들러 하나가 예외를 던져도 로그만 남기고 나머지 핸들러는 계속 호출됩니다 — 터치패널 UI 콜백 하나 잘못 짜도 장비 폴링/다른 UI 갱신이 멈추지 않습니다.

### 2. CommonLogger — 어디서나 같은 방식으로 로그

MUSE 런타임(`context.log`)이 있으면 거기로, 없으면(PC에서 개발/테스트할 때) `print`로 자동 폴백합니다. `dv/`의 거의 모든 드라이버가 `CommonLogger, EventManager`를 함께 상속해서 "로거이자 이벤트 발행자"가 됩니다.

### 3. tp.py — 터치패널 연동

MUSE 터치패널의 채널(버튼)/레벨(슬라이더)/문자열 명령을 감싸서, `tp_add_watcher`로 눌림 이벤트를 콜백에 연결하고 `tp_set_button`/`tp_send_level`로 피드백을 내보냅니다.

그런데 `tp_add_watcher`가 주는 건 딱 "눌렸다/뗐다"뿐이라, 오래 누르고 있으면(hold) 뭘 하거나 누르고 있는 동안 반복(repeat)시키고 싶은 순간 막막해집니다. NetLinx에서는 당연히 되던 걸 MUSE에서 매번 손으로 스레드/타이머 짜서 흉내내다 지쳐서 만든 게 `button_handler.py`입니다 — 이제는 `ButtonHandler`가 push/release/hold/repeat 이벤트를 대신 내주고, dv 드라이버의 `emit("power", ...)`과 터치패널 버튼 이벤트가 같은 on/emit 어휘로 이어집니다.

### 4. network_manager — 통신 계층

TCP는 자동 재연결(`tcp_client.py`), UDP는 무응답 감지 후 소켓 재생성으로 "연결 유지"를 흉내내고 connect() 없이 send()만 호출하면 1회성 전송으로 동작합니다. 전부 백그라운드 스레드 + 락으로 스레드 안전하게 짜여 있습니다.

## 빠른 사용 예시

`dv/dv_pjlink.py` — TcpClient(재연결) + Scheduler(주기 폴링) + EventManager(상태 발행)를 조합하는 전형적인 드라이버 패턴:

```python
class PjLink(CommonLogger, EventManager):
    def __init__(self, ip, port=4352):
        super().__init__("power", "mute", "lamp_time")
        self.dv = TcpClient(ip, port)
        self.poll = Scheduler()

    def init(self):
        self.dv.receive.listen(self.parse_response)        # 수신 데이터 → 파싱
        self.dv.online(lambda *_: self.start_poll())        # 연결되면 폴링 시작
        self.dv.offline(lambda *_: self.poll.shutdown())    # 끊기면 폴링 중단
        self.dv.connect()

    def start_poll(self, *_):
        self.poll.set_interval(10.0, lambda: self.dv.send("%1POWR ?\r"))

    def parse_response(self, *args):
        ...  # 응답 파싱 후
        self.emit("power", value=self.power)                # 상위(터치패널 등)로 상태 발행

projector = PjLink("192.168.0.10")
projector.init()
projector.on("power", lambda value: tp_set_button(tp, port, btn_power, value))  # 피드백 연결
```

## 새 장비 드라이버 추가하기

1. `dv/dv_<브랜드>_<장비종류>.py` 형식으로 파일 생성
2. `CommonLogger, EventManager`를 상속하고, 이 드라이버가 낼 이벤트 이름을 `super().__init__(...)`에 등록
3. 통신은 직접 소켓을 열지 말고 `lib/network_manager`의 `TcpClient`/`UdpClient`/`MulticastGroup` 중 프로토콜에 맞는 걸 사용
4. 주기 폴링이 필요하면 `lib/scheduler.py`의 `Scheduler` 사용
5. 상태가 바뀔 때마다 `self.emit(...)` 로 발행 — 상위 UI 코드는 `.on(...)`으로만 구독하면 되게

기존 `dv_pjlink.py`, `dv_wp412.py` 같은 파일을 템플릿 삼는 게 제일 빠릅니다.

## 요구 사항

- Python 3.10+ (`int | float` 타입힌트 문법 사용)
- **외부 패키지 의존성 없음** — 표준 라이브러리만 사용 (MUSE 컨트롤러도 인터넷 연결 + requirements.txt 있으면 pip 설치 자체는 되지만, 번거로워서 내장 라이브러리만으로 처리하는 쪽을 택함)
- MUSE 컨트롤러 없이도 PC에서 로직 단위 테스트 가능 (mojo 런타임 부재 시 로그는 `print`로 폴백)

## 기여

개인적으로 쓰려고 만든 코드라 완성도가 높진 않습니다. 그래도 혹시 AMX MUSE로 비슷한 작업 하시는 분께 조금이라도 참고가 될까 싶어 그냥 공개해 뒀습니다. 버그 제보나 개선 제안은 편하게 남겨 주세요.
