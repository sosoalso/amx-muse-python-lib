# 마지막 수정일 : 20260714
"""NTU-89 비디오 매트릭스 - 바이너리 2바이트 커맨드, TX 전용(응답 없음) 시리얼 제어.

원본 AMX NetLinx 코드(ntu_89_video_matrix.axi) 기준 포팅:
    send_string dv, "$C9, ((out - 1) << 4) | (in - 1)"
즉 [0xC9, ((idx_out-1)<<4)|(idx_in-1)] 2바이트를 그대로 보내면 끝. 장비가 응답을 보내지 않으므로
receive 파싱이 필요 없고, routes 는 스위칭 명령을 보낼 때 낙관적으로만 갱신한다(read-back 불가).

NetLinx 쪽의 ntu_89_init() 은 "9600 N,8,1 485 ENABLE" 로 포트를 RS-485 로 여는 것 뿐이라
장비 프로토콜과 무관함 - MUSE 쪽에서는 config.py의 init_serial(iface, baudrate="9600", mode="485")
로 대응하면 된다.

idx_in/idx_out 은 각각 4비트 니블로 인코딩되므로 프로토콜 상 최대 16이지만, 실제 장비 입출력
포트 수는 확인되지 않았음 - NUM_IN/NUM_OUT 은 실제 장비 사양에 맞게 생성자에서 조정할 것.
"""

from lib.event_manager import EventManager
from lib.utility import CommonLogger, handle_exception


class Ntu89VideoMatrix(CommonLogger, EventManager):
    CMD_SWITCH = 0xC9

    def __init__(self, dv):
        super().__init__("route")
        self.dv = dv
        self.num_in = 8
        self.num_out = 8
        self.name = f"{__class__.__name__.lower()}_{getattr(self.dv, 'name', '') or ''}"
        self.routes = {idx_out: 0 for idx_out in range(1, self.num_out + 1)}

    @handle_exception
    def init(self):
        """TX 전용 장비라 수신 파싱은 없음 - 다른 dv 드라이버와 호출 규격만 맞춰둠"""

    @handle_exception
    def switch(self, idx_in: int, idx_out: int):
        """입력 idx_in 을 출력 idx_out 으로 라우팅 (1-based)"""
        if not 1 <= idx_in <= self.num_in:
            raise ValueError(f"invalid idx_in: {idx_in}")
        if not 1 <= idx_out <= self.num_out:
            raise ValueError(f"invalid idx_out: {idx_out}")
        payload = ((idx_out - 1) << 4) | (idx_in - 1)
        self.dv.send(bytes([self.CMD_SWITCH, payload]))
        self.log_debug(f"switch() : {idx_in=} {idx_out=} cmd={[self.CMD_SWITCH, payload]}")
        self.routes[idx_out] = idx_in
        # emit: route(idx_in: int, idx_out: int, routes: dict)
        self.emit("route", idx_in=idx_in, idx_out=idx_out, routes=self.routes)
