# 마지막 수정일 : 20260713
"""회의실 마이크 상태 관리 모듈.

DSP/회의 마이크 시스템에서 마이크 on/off 를 통지받아 켜진 순서를 추적하고,
"마지막에 켜진 마이크"와 최대 동시 개수(max_mics) 정책을 이벤트로 알려준다.
카메라 트래킹(마지막 발언자 좌석으로 카메라 이동) 같은 로직이 이 이벤트를 구독해서 쓴다.
"""

from lib.event_manager import EventManager
from lib.utility import CommonLogger


class MicManager(CommonLogger, EventManager):
    """마이크 on/off 순서 추적 + 정책 적용 후 이벤트로 알리는 관리자.

    발생 이벤트:
    - mic_on(mic_index)      : 마이크 켜짐
    - mic_off(mic_index)     : 마이크 꺼짐 (max_mics 초과로 강제 꺼야 할 때도 발생)
    - mic_all_off()          : 켜진 마이크가 하나도 없음
    - last_mic_on(mic_index) : 마지막으로 켜진(현재 발언 중인) 마이크 변경

    사용 흐름: 장비 드라이버가 notify_mic_on/off 를 호출 → 구독자(on())가
    실제 장비 제어(카메라 이동, 채널 뮤트 등)를 수행한다.
    last_on_mics 는 켜진 순서를 유지하는 리스트로, 끝(-1)이 가장 최근 마이크다.
    """

    def __init__(self, max_mic_index=40, last_mic_enabled=True, max_mics=0):
        # super() 는 MRO 상 CommonLogger 를 거쳐 EventManager 에 닿는데,
        # CommonLogger 에 __init__ 이 생기면 깨지므로 명시적으로 호출
        EventManager.__init__(self, "mic_on", "mic_off", "mic_all_off", "last_mic_on")
        self.max_mic_index = max_mic_index
        self.last_mic_enabled = last_mic_enabled
        self.max_mics = max_mics  # 0 또는 -1이면 제한 없음
        self.vip_mics = set()  # 꺼지면 안 되는 VIP 마이크 인덱스
        self.last_on_mics = []

    def is_mic_on(self, mic_index):
        return mic_index in self.last_on_mics

    def get_last_on_mic(self):
        return self.last_on_mics[-1] if self.last_on_mics else None

    def get_last_mic_enabled(self) -> bool:
        return self.last_mic_enabled

    def set_last_mic_enabled(self, is_enabled: bool) -> bool:
        self.last_mic_enabled = is_enabled
        return self.get_last_mic_enabled()

    # ---------------------------------------------------------------------------- #
    def set_vip_mic(self, mic_index):
        self.log_debug(f"set_vip_mic() {mic_index=}")
        self.vip_mics.add(mic_index)

    def unset_vip_mic(self, mic_index):
        self.log_debug(f"unset_vip_mic() {mic_index=}")
        self.vip_mics.discard(mic_index)

    def is_vip_mic(self, mic_index):
        return mic_index in self.vip_mics

    def set_max_mics(self, max_mics):
        """최대 동시 마이크 개수 변경. 부수효과: 켜짐 상태 전체 초기화 + mic_all_off 발생."""
        self.log_debug(f"set_max_mics() {max_mics=}")
        self.max_mics = max_mics
        self.last_on_mics.clear()
        # emit: mic_all_off()
        self.emit("mic_all_off")

    # ---------------------------------------------------------------------------- #
    def notify_mic_on(self, mic_index):
        """마이크 켜짐 통지 처리.

        last_on_mics 끝에 추가하고(이미 켜져 있으면 최신 위치로 갱신),
        max_mics 초과 시 가장 오래된 비 VIP 마이크를 mic_off 이벤트로 끄게 한 뒤
        마지막에 mic_on 이벤트를 발생시킨다.
        이미 켜져 있고 이미 가장 최근 상태면 아무 것도 하지 않는다 (notify_mic_off 의
        idempotency guard와 대칭 - 장비 쪽에서 되돌아오는 echo 성 재통지에 안전하게 대비).
        """
        self.log_debug(f"notify_mic_on() {mic_index=}")
        if self.last_on_mics and self.last_on_mics[-1] == mic_index:
            return
        # 이미 켜져 있던 마이크면 리스트에서 빼고 다시 넣어 "가장 최근" 위치로 갱신
        if mic_index in self.last_on_mics:
            self.last_on_mics.remove(mic_index)
        self.last_on_mics.append(mic_index)
        # max_mics 가 유효한 경우에만 초과 마이크 끄기 (VIP 제외)
        if self.max_mics > 0:
            non_vip = [m for m in self.last_on_mics if m not in self.vip_mics]
            while len(non_vip) > self.max_mics:
                oldest = non_vip.pop(0)
                self.last_on_mics.remove(oldest)
                self.log_debug(f"notify_mic_on() : max_mics exceeded, turning off {oldest=} {self.last_on_mics=}")
                # emit: mic_off(mic_index: int)
                self.emit("mic_off", oldest)
        # emit: mic_on(mic_index: int)
        self.emit("mic_on", mic_index)

    def notify_mic_off(self, mic_index):
        """마이크 꺼짐 통지 처리.

        mic_off 이벤트 후 남은 마이크가 있으면 last_mic_on(가장 최근 마이크)을,
        하나도 없으면 mic_all_off 를 발생시킨다. 추적 중이 아닌 마이크는 무시.
        """
        self.log_debug(f"notify_mic_off() {mic_index=}")
        if mic_index not in self.last_on_mics:
            return
        self.last_on_mics.remove(mic_index)
        # emit: mic_off(mic_index: int)
        self.emit("mic_off", mic_index)
        if self.last_on_mics:
            if self.last_mic_enabled:
                # emit: last_mic_on(mic_index: int)
                self.emit("last_mic_on", self.last_on_mics[-1])
        else:
            # emit: mic_all_off()
            self.emit("mic_all_off")

    def notify_all_mic_off(self):
        """전체 마이크 꺼짐 통지 처리. 상태를 비우고 mic_all_off 를 발생시킨다."""
        self.log_debug("notify_all_mic_off()")
        self.last_on_mics.clear()
        # emit: mic_all_off()
        self.emit("mic_all_off")
