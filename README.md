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

버튼/레벨을 실제로 코드에서 연결할 때는 `tp_add_watcher`를 직접 쓰지 말고 `lib/button.py`의 `add_button`/`add_level`을 씁니다. 같은 (tp, port, 번호)에 여러 번 등록해도 내부적으로 핸들러 하나만 캐싱해서 재사용하기 때문에, 중복 등록 걱정 없이 필요할 때마다 그냥 호출하면 됩니다.

```python
from lib.button import add_button, add_level

# push: 눌리는 순간 1회
add_button(tp, 1, 30, "push", lambda: camera.pan_left())
# release: 손 뗀 순간 1회 - 조이스틱형 버튼에서 이동 정지시킬 때
add_button(tp, 1, 30, "release", lambda: camera.pan_stop())
# repeat: 누르고 있는 동안 반복. 기본 0.3초 간격이 아니라 다른 값을 쓰고 싶으면
# "repeat_0.6" 이나 "repeat=0.6" 처럼 액션 문자열에 값을 같이 적으면 파싱해서 적용됨 (0.1~3.0 범위)
add_button(tp, 1, 30, "repeat_0.6", lambda: camera.pan_left())
# hold: 일정 시간 이상 눌리고 있으면 1회. 기본 30초라 너무 기니까 "hold_3.0"(0.5~30 범위)으로 줄임
add_button(tp, 1, 30, "hold_3.0", lambda: camera.goto_preset(1))

# 레벨: (tp, port, 레벨번호, 콜백) - 값은 이미 debounce 처리되어 들어옴
add_level(tp, 1, 20, lambda value: mixer.set_volume(value))
```

같은 버튼/레벨이 터치패널 여러 대(벽부형 + 태블릿 등)에 똑같이 있으면, `tp` 하나씩 따로 등록하지 말고 `_ss`가 붙은 함수에 `tp` 리스트/튜플을 넘기면 한 번에 다 등록됩니다. `button.py`(`add_button_ss`/`add_level_ss`)와 `tp.py`(`tp_set_button_ss`/`tp_send_level_ss`/`tp_send_command_ss` 등 피드백 함수들) 양쪽에 다 있습니다.

```python
from lib.button import add_button_ss
from lib.tp import tp_set_button_ss

tp_list = [tp1, tp2]  # 벽부형 + 태블릿

add_button_ss(tp_list, 1, 30, "push", lambda: camera.pan_left())   # 둘 다 동시 등록
tp_set_button_ss(tp_list, 1, 30, True)                              # 둘 다 동시 피드백
```

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
        self.dv.online(lambda *args: self.start_poll())        # 연결되면 폴링 시작
        self.dv.offline(lambda *args: self.poll.shutdown())    # 끊기면 폴링 중단
        self.dv.connect()

    def start_poll(self, *args):
        self.poll.set_interval(10.0, lambda: self.dv.send("%1POWR ?\r"))

    def parse_response(self, *args):
        ...  # 응답 파싱 후
        self.emit("power", value=self.power)                # 상위(터치패널 등)로 상태 발행

projector = PjLink("192.168.0.10")
projector.init()
projector.on("power", lambda value: tp_set_button(tp, port, btn_power, value))  # 피드백 연결
```

## 디버그 로그 켜서 보기

기본적으로는 조용합니다. `log_debug()`는 그 로거 인스턴스의 `debug` 플래그가 `True`일 때만 출력되고, 전부 다 켜면 시끄러워서 필요한 부분만 골라 켜는 걸 추천합니다.

1. **MUSE 런타임(context.log)을 쓰는 경우 먼저**: `context.log.level`을 `debug`로 놓아야, 아래서 켠 `log_debug()` 내용이 실제로 콘솔에 찍힙니다. (mojo 런타임 없는 PC 환경이면 이 단계는 필요 없고 바로 `print`로 나갑니다)

2. **장비 드라이버(`dv/`) 하나만 보고 싶을 때**: 거의 다 `CommonLogger`를 상속하니, 그 인스턴스의 `debug`만 켜면 됩니다.
   ```python
   projector = PjLink("192.168.0.10")
   projector.debug = True   # 이 인스턴스의 log_debug()만 출력
   ```

3. **`EventManager` 자체(on/off/emit 내부 동작)를 보고 싶을 때**: 각 dv 인스턴스가 아니라 `lib/event_manager.py` 모듈 안의 전역 로거 하나를 씁니다.
   ```python
   from lib.event_manager import event_manager_logger
   event_manager_logger.debug = True
   ```

4. **`tp.py`(터치패널 연동)를 보고 싶을 때**: 개인적으로 제일 자주 켜는 부분입니다 — 버튼 워처가 잘 등록됐는지, 눌림 이벤트가 실제로 잡히는지 바로 보여서 유용함. 섹션별로 로거가 따로 있어서 `tp_set_debug_flag(...)`로 필요한 것만 골라 켤 수 있습니다.
   ```python
   from lib.tp import tp_set_debug_flag
   tp_set_debug_flag(
       debug_tp_add_watcher=True,        # 버튼 워처 등록/트리거 - 제일 유용함
       debug_tp_add_watcher_level=False,
       debug_tp_add_notification=False,
       debug_tp_add_notification_level=False,
       debug_tp_set_button=False,
       debug_tp_send_level=False,
       debug_tp_send_command=False,
   )
   ```

요약하면: `context.log.level`을 `debug`로 열어두고, 보고 싶은 대상(dv 인스턴스 / `event_manager_logger` / `tp.py` 섹션별 로거)의 `debug`만 켜는 구조입니다.

## 설정값 저장하기 (`lib/userdata.py`)

볼륨, 카메라 프리셋, 마지막 선택 소스처럼 컨트롤러 재부팅 후에도 남아있어야 하는 값은 JSON 파일로 저장합니다. 상황에 따라 둘 중 하나를 씁니다.

**`Userdata`** — key-value 하나씩 다루고, `set_value()` 호출 즉시 파일에 저장됩니다(자동저장).

```python
from lib.userdata import Userdata

userdata = Userdata("volume.json", default_value={"volume": 50})
userdata.set_value("volume", 70)              # 호출 즉시 파일에 반영됨
current = userdata.get_value("volume", 50)    # 70 (없으면 기본값 50)
userdata.delete_value("volume")
```

- 파일 위치는 기본적으로 프로젝트 폴더 **옆**(안이 아니라) `<프로젝트폴더명>_userdata/`에 잡힙니다 (`foldername` 인자로 변경 가능). 프로젝트 폴더 안에 두면 소스를 다시 업로드할 때 폴더가 통째로 갈아엎어지면서 저장해 둔 값도 같이 날아가기 때문에, 일부러 프로젝트 폴더 밖에 둡니다.
- 이 폴더에 직접 들어가 보고 싶으면 컨트롤러에 SFTP로 접속해서 `mojo/program/` 경로 밑을 찾아보면 됩니다.
- 파일이 없으면 `default_value`로 새로 만들고, JSON이 깨져 있으면 지우지 않고 `.broken_시각` 이름으로 백업해 둔 뒤 새로 만듭니다
- 키는 내부적으로 항상 문자열로 저장되니(JSON 특성상), 정수 키를 넣었어도 꺼낼 땐 문자열처럼 다뤄집니다

**`Var`** — 값 하나하나가 아니라 클래스 속성 자체를 통째로 설정값처럼 씁니다. 자동저장은 없고, `save_to_json()`/`load_from_json()`을 직접 호출해야 반영됩니다.

```python
from lib.userdata import Var

class Settings(Var):
    volume = 50
    last_source = "hdmi1"

Settings.load_from_json("settings.json")   # 파일 있으면 클래스 속성을 덮어씀 (기존에 있는 속성만)
Settings.volume = 70
Settings.save_to_json("settings.json")      # 명시적으로 저장해야 파일에 반영됨
```

설정값이 몇 개 안 되고 그때그때 즉시 저장돼야 하면 `Userdata`, 설정 묶음을 한 번에 불러오고/저장하고 싶으면 `Var` 쪽이 편합니다.

## 유용한 데코레이터 (`lib/utility.py`)

**`pulse(duration_seconds, off_method)`** — 함수 실행하고 일정 시간 뒤에 자동으로 꺼주는 데코레이터. 릴레이 on 시키고 몇 초 뒤 자동으로 off 시킬 때 씁니다.

```python
def turn_on_relay(self):
    def turn_off():
        self.dv.relay_off()

    @pulse(2.0, turn_off)   # turn_on() 실행 후 2초 뒤 turn_off() 자동 호출
    def turn_on():
        self.dv.relay_on()

    turn_on()
```

**`debounce(timeout_ms)`** — 짧은 시간 안에 연달아 호출되면 마지막 호출만 살아남는 데코레이터. 터치패널 레벨(슬라이더) 이벤트가 손가락 움직일 때마다 훅훅 쏟아지는 걸 걸러낼 때 씁니다 (`lib/button_handler.py`의 `LevelHandler`가 실제로 이렇게 씀).

```python
@debounce(100)  # 100ms 안에 또 들어오면 타이머가 리셋되고, 결국 마지막 호출만 반영됨
def debounced_emit(value):
    self.emit("level", value)

debounced_emit(50)
debounced_emit(51)
debounced_emit(52)   # 100ms 안에 연달아 오면 이 마지막 호출만 실제로 emit 됨
```

## 새 장비 드라이버 추가하기

1. `dv/dv_<브랜드>_<장비종류>.py` 형식으로 파일 생성
2. `CommonLogger, EventManager`를 상속하고, 이 드라이버가 낼 이벤트 이름을 `super().__init__(...)`에 등록
3. 통신은 직접 소켓을 열지 말고 `lib/network_manager`의 `TcpClient`/`UdpClient`/`MulticastGroup` 중 프로토콜에 맞는 걸 사용
4. 주기 폴링이 필요하면 저는 `lib/scheduler.py`의 `Scheduler`를 써왔는데, 이건 그냥 제가 그렇게 써온 거라 꼭 이걸 써야 하는 건 아닙니다 — 편한 걸로 쓰세요
5. 상태가 바뀔 때마다 `self.emit(...)` 로 발행 — 상위 UI 코드는 `.on(...)`으로만 구독하면 되게

시리얼이랑 섞어 쓰거나 통신 방식이 딱 하나로 정해지지 않는 장비는(`dv_cisco_codec.py`처럼), 클래스가 직접 인터페이스를 만들지 않고 생성자에서 `dv`를 인자로 받아서 씁니다. 인터페이스(TCP든 Serial이든)는 밖에서 만들어서 넣어주고, 클래스는 `dv.send()`/`dv.receive.listen()`만 쓸 줄 알면 되는 식입니다.

기존 `dv_pjlink.py`, `dv_wp412.py`(직접 TcpClient 관리), `dv_cisco_codec.py`(dv를 외부에서 주입) 같은 파일을 템플릿 삼는 게 제일 빠릅니다.

## 요구 사항

- Python 3.10+ (`int | float` 타입힌트 문법 사용)
- **외부 패키지 의존성 없음** — 표준 라이브러리만 사용 (MUSE 컨트롤러도 인터넷 연결 + requirements.txt 있으면 pip 설치 자체는 되지만, 번거로워서 내장 라이브러리만으로 처리하는 쪽을 택함)
- MUSE 컨트롤러 없이도 PC에서 로직 단위 테스트 가능 (mojo 런타임 부재 시 로그는 `print`로 폴백)

## 기여

개인적으로 쓰려고 만든 코드라 완성도가 높진 않습니다. 그래도 혹시 AMX MUSE로 비슷한 작업 하시는 분께 조금이라도 참고가 될까 싶어 그냥 공개해 뒀습니다. 버그 제보나 개선 제안은 편하게 남겨 주세요.
