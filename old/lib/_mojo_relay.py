# 마지막 수정일 : 20260514
from lib.button import add_button_ss
from lib.mojo_tp import tp_set_button
from lib.utility import pulse


class Relay:
    def __init__(self, devchan_list: list[tuple] | tuple[tuple], tp_list: list, port: int, pulse_time: float = 0.5):
        """
        릴레이 제어 객체를 초기화합니다.

        Args:
            devchan_list (list[tuple] | tuple[tuple]): 디바이스-채널 정보를 담은 튜플의 리스트 또는 튜플
                각 요소는 (device_id, channel_id) 형태의 튜플
            tp_list (list): 터치패널 관련 정보 리스트
            port (int): 통신 포트 번호
            pulse_time (float, optional): 릴레이 펄스 신호의 지속 시간(초). 기본값은 0.5초
                - 릴레이를 순간적으로 활성화할 때 사용되는 시간 간격

        Attributes:
            devchan_list: 정규화된 디바이스-채널 리스트 (빈 입력값은 빈 리스트로 변환)
            relay_state (list[dict]): 각 디바이스별 릴레이 상태를 저장하는 딕셔너리 리스트
                - devchan_list 길이만큼 초기화되며, 각 요소는 비어있는 딕셔너리로 시작
            tp_list: 터치패널 정보 리스트
            pulse_time: 릴레이 펄스 신호 지속 시간
            tp_port: 통신 포트 번호

        Note:
            초기화 완료 후 self.init() 메서드를 호출하여 릴레이 통신 초기화 수행
        """
        self.devchan_list = devchan_list if devchan_list else []
        self.relay_state = [{} for _ in range(len(devchan_list))]
        self.tp_list = tp_list
        self.pulse_time = pulse_time
        self.tp_port = port
        self.init()

    def init(self):
        for idx, (dv, ch) in enumerate(self.devchan_list):
            self.relay_state[idx] = {
                "dv": dv,
                "ch": int(ch),
                "state": self._get_relay_devchan_state(idx) or False,
            }

    def _get_relay_devchan(self, idx):
        dv, ch = self.devchan_list[idx]
        return dv[ch]

    def _get_relay_devchan_state(self, idx):
        return self._get_relay_devchan(idx).state.value

    def _set_relay_devchan_state(self, idx, state):
        self._get_relay_devchan(idx).state.value = state

    def get_relay_state(self, idx):
        return self.relay_state[idx]["state"]

    def set_relay_state(self, idx, state):
        self._set_relay_devchan_state(idx, state)
        self.update_relay_state(idx)

    def set_relay_on(self, idx):
        self.set_relay_state(idx, True)
        self.update_relay_state(idx)
        self.refresh_relay_button(idx)

    def set_relay_off(self, idx):
        self.set_relay_state(idx, False)
        self.update_relay_state(idx)
        self.refresh_relay_button(idx)

    def set_relay_toggle(self, idx):
        self.set_relay_state(idx, not self.get_relay_state(idx))
        self.update_relay_state(idx)
        self.refresh_relay_button(idx)

    def set_relay_pulse(self, idx):
        @pulse(self.pulse_time, self.set_relay_off, idx)
        def inner():
            self.set_relay_on(idx)
            self.update_relay_state(idx)
            self.refresh_relay_button(idx)

        inner()

    def update_relay_state(self, idx):
        self.relay_state[idx]["state"] = self._get_relay_devchan_state(idx)

    def add_relay_button(self):
        for idx in range(len(self.devchan_list)):
            add_button_ss(
                self.tp_list,
                self.tp_port,
                idx + 1,
                "push",
                lambda idx=idx: self.set_relay_on(idx),
            )
            add_button_ss(
                self.tp_list,
                self.tp_port,
                idx + 101,
                "push",
                lambda idx=idx: self.set_relay_off(idx),
            )
            add_button_ss(
                self.tp_list,
                self.tp_port,
                idx + 201,
                "push",
                lambda idx=idx: self.set_relay_pulse(idx),
            )
            add_button_ss(
                self.tp_list,
                self.tp_port,
                idx + 301,
                "push",
                lambda idx=idx: self.set_relay_toggle(idx),
            )
            relay_momentary_button = add_button_ss(
                self.tp_list,
                self.tp_port,
                idx + 401,
                "push",
                lambda idx=idx: self.set_relay_on(idx),
            )
            relay_momentary_button.on("release", lambda idx=idx: self.set_relay_off(idx))

    def refresh_relay_button(self, idx):
        for tp in self.tp_list:
            tp_set_button(tp, self.tp_port, idx + 1, self.get_relay_state(idx))
            tp_set_button(tp, self.tp_port, idx + 101, not self.get_relay_state(idx))

    def show_all_relay_state(self):
        print(f"show_all_relay_state() : {self.devchan_list=}")
        for idx in range(len(self.devchan_list)):
            print(f"{idx=} {self.relay_state[idx]['state']=} {self._get_relay_devchan_state(idx)=}")
