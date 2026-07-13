# 마지막 수정일 : 20260713
"""MUSE 컨트롤러 내장 포트(idevice) 초기화/제어 헬퍼.

dv 는 context.devices.get("idevice") 로 얻은 컨트롤러의 시리얼/IO/IR 포트 배열 원소다.
프로그램 시작 시 init_serial / init_io / init_ir 로 포트 모드를 잡아주고,
나머지 함수들은 MUSE 포트 API(AMX MUSE Programming Guide v1.7, Appendix A) 를 얇게 감싼 래퍼다.

relay_* 함수는 idevice 전용이 아니라 ".state" boolean 파라미터를 갖는 모든 Thing
(예: CE-REL8 같은 외부 릴레이 확장기)에 재사용 가능한 범용 래퍼다.
현재 mojo/__init__.pyi 기준으로는 이 프로젝트의 idevice 자체에는 relay 배열이 없다.
"""

from lib.utility import handle_exception


def log_error(message):
    print(f"mojo_idevice (ERROR) -- {message}")


# ---------------------------------------------------------------------------- #
# Serial 포트
# ---------------------------------------------------------------------------- #
@handle_exception
def serial_send(dv, data: bytes):
    dv.send(data)


def serial_set_flow_control(dv, mode="NONE"):
    try:
        valid_modes = {"NONE", "HARDWARE"}
        if mode not in valid_modes:
            raise ValueError(f"Wrong flow control mode: {mode}")
        dv.setFlowControl(mode)
    except Exception as e:
        log_error(f"serial_set_flow_control() : {e=}")


@handle_exception
def serial_flush_receive_buffer(dv):
    # 수신 버퍼에 남아있는 데이터를 모두 제거
    dv.flushReceiveBuffer()


@handle_exception
def serial_disable_receive(dv):
    dv.disableReceive()


@handle_exception
def serial_enable_receive(dv):
    dv.enableReceive()


@handle_exception
def serial_listen_receive(dv, callback):
    """수신 이벤트 콜백 등록. callback(evt) 형태이며 evt.arguments.get("data", b"") 에 수신 bytes 가 들어온다."""
    dv.receive.listen(callback)


@handle_exception
def serial_request_status(dv):
    """status 는 값을 바로 읽을 수 있는 파라미터가 아니라 이벤트형이라, getStatus() 로 갱신을 요청하고
    serial_listen_status() 로 등록한 콜백을 통해 결과를 받아야 한다."""
    dv.getStatus()


@handle_exception
def serial_listen_status(dv, callback):
    dv.status.listen(callback)


# 시리얼 포트 fault(결선/통신 이상) 감지 관련 래퍼들
@handle_exception
def serial_enable_fault_detection(dv):
    dv.enableFaultDetection()


@handle_exception
def serial_disable_fault_detection(dv):
    dv.disableFaultDetection()


@handle_exception
def get_fault(dv):
    return dv.getFault()


@handle_exception
def serial_clear_fault(dv):
    dv.clearFault()


def init_serial(dv, baudrate="9600", bit=8, stop=1, parity="NONE", mode="232"):
    """시리얼 포트 통신 파라미터를 검증 후 적용하고 수신을 활성화한다.

    baudrate 는 문자열, mode 는 "232"/"422"/"485". 잘못된 값이면 로그만 남기고 넘어간다.
    """
    try:
        # 시리얼 통신 매개변수의 유효한 값들을 정의
        valid_baudrates = {"1200", "2400", "4800", "9600", "19200", "38400", "57600", "115200"}
        valid_bits = {7, 8}
        valid_stops = {1, 2}
        valid_parities = {"NONE", "EVEN", "ODD", "MARK", "SPACE"}
        valid_modes = {"232", "422", "485"}
        # 입력된 매개변수 값이 유효한 범위에 있는지 검증
        if baudrate not in valid_baudrates:
            raise ValueError(f"Wrong baudrate: {baudrate}")
        if bit not in valid_bits:
            raise ValueError(f"Wrong data bits: {bit}")
        if stop not in valid_stops:
            raise ValueError(f"Wrong stop bits: {stop}")
        if parity not in valid_parities:
            raise ValueError(f"Wrong parity: {parity}")
        if mode not in valid_modes:
            raise ValueError(f"Wrong mode: {mode}")
        # 검증 완료된 매개변수를 기기에 적용
        dv.setCommParams(baudrate, bit, stop, parity, mode)
        serial_enable_receive(dv)
    except Exception as e:
        log_error(f"init_serial() : {e=}")


# ---------------------------------------------------------------------------- #
# IO 포트
# ---------------------------------------------------------------------------- #
def init_io(dv, io="INPUT", input_mode="ANALOG"):
    """IO 포트를 입력/출력으로 설정한다. 입력일 때는 ANALOG/DIGITAL/BOTH 모드도 함께 지정."""
    try:
        # IO 포트의 유효한 동작 모드 정의
        valid_io_modes = {"INPUT", "OUTPUT"}
        valid_input_modes = {"ANALOG", "DIGITAL", "BOTH"}
        # 입력 매개변수 유효성 검증
        if io not in valid_io_modes:
            raise ValueError(f"Invalid IO mode: {io}")
        if io == "INPUT" and input_mode not in valid_input_modes:
            raise ValueError(f"Invalid input mode: {input_mode}")
        # IO 모드 설정
        dv.mode.value = io
        if io == "INPUT":
            dv.inputMode.value = input_mode
    except Exception as e:
        log_error(f"init_io() : {e=}")


@handle_exception
def io_set_output(dv, state: bool):
    dv.output.value = state


@handle_exception
def io_output_on(dv):
    dv.output.value = True


@handle_exception
def io_output_off(dv):
    dv.output.value = False


@handle_exception
def io_get_digital_input(dv):
    return dv.digitalInput.value


@handle_exception
def io_get_analog_input(dv):
    return dv.analogInput.value


@handle_exception
def io_watch_digital_input(dv, callback):
    dv.digitalInput.watch(callback)


@handle_exception
def io_watch_analog_input(dv, callback):
    dv.analogInput.watch(callback)


@handle_exception
def io_set_pullup(dv, enabled: bool):
    dv.digitalInput2KPullup.value = enabled


def io_set_debounce_time(dv, milliseconds: int):
    try:
        if not 5 <= milliseconds <= 250:
            raise ValueError(f"debounceTimeMilliseconds out of range(5-250): {milliseconds}")
        dv.debounceTimeMilliseconds.value = milliseconds
    except Exception as e:
        log_error(f"io_set_debounce_time() : {e=}")


def io_set_debounce_min_delta(dv, volts: float):
    try:
        if not 0.1 <= volts <= 4.9:
            raise ValueError(f"debounceMinDelta out of range(0.1-4.9): {volts}")
        dv.debounceMinDelta.value = volts
    except Exception as e:
        log_error(f"io_set_debounce_min_delta() : {e=}")


def io_set_digital_input_low_max(dv, volts: float):
    try:
        if not 0.0 <= volts <= 9.9:
            raise ValueError(f"digitalInputLowMax out of range(0.0-9.9): {volts}")
        dv.digitalInputLowMax.value = volts
    except Exception as e:
        log_error(f"io_set_digital_input_low_max() : {e=}")


def io_set_digital_input_high_min(dv, volts: float):
    try:
        if not 0.1 <= volts <= 10.0:
            raise ValueError(f"digitalInputHighMin out of range(0.1-10.0): {volts}")
        dv.digitalInputHighMin.value = volts
    except Exception as e:
        log_error(f"io_set_digital_input_high_min() : {e=}")


# ---------------------------------------------------------------------------- #
# IR 포트
# ---------------------------------------------------------------------------- #
def init_ir(dv, mode="IR"):
    """IR 포트를 IR/SERIAL/DATA/TEST 모드로 설정한다. IR 모드면 캐리어 신호를 켠다."""
    try:
        # IR 포트의 유효한 동작 모드 정의
        valid_modes = {"IR", "SERIAL", "DATA", "TEST"}
        # 입력된 IR 모드 유효성 검증
        if mode not in valid_modes:
            raise ValueError(f"Wrong IR mode: {mode}")
        # IR 모드 설정 및 IR 모드일 경우 캐리어 활성화
        dv.mode.value = mode
        if mode == "IR":
            dv.carrier.value = True
    except Exception as e:
        log_error(f"init_ir() : {e=}")


# IR 포트를 SERIAL 모드로 쓸 때의 통신 파라미터. Serial 포트와 유효 범위가 다르다
# (baudrate 4종뿐, mode(232/422/485) 인자 없음).
def ir_set_comm_params(dv, baudrate="9600", bit=8, stop=1, parity="NONE"):
    try:
        valid_baudrates = {"1200", "4800", "9600", "19200"}
        valid_bits = {7, 8}
        valid_stops = {1, 2}
        valid_parities = {"NONE", "EVEN", "ODD", "MARK", "SPACE"}
        if baudrate not in valid_baudrates:
            raise ValueError(f"Wrong baudrate: {baudrate}")
        if bit not in valid_bits:
            raise ValueError(f"Wrong data bits: {bit}")
        if stop not in valid_stops:
            raise ValueError(f"Wrong stop bits: {stop}")
        if parity not in valid_parities:
            raise ValueError(f"Wrong parity: {parity}")
        dv.setCommParams(baudrate, bit, stop, parity)
    except Exception as e:
        log_error(f"ir_set_comm_params() : {e=}")


# IR 펄스 송출 시간(ms) 설정 : 장비가 IR 명령을 못 받을 때 조절
@handle_exception
def ir_set_on_time(dv, milliseconds):
    dv.setOnTime(milliseconds)


@handle_exception
def ir_set_off_time(dv, milliseconds):
    dv.setOffTime(milliseconds)


@handle_exception
def ir_send_ch(dv, ch: int):
    """큐를 비우고 인덱스로 지정한 IR 코드를 즉시 송출."""
    dv.clearAndSendIr(ch)


@handle_exception
def ir_send_name(dv, name: str):
    """큐를 비우고 .irl 파일에 등록된 이름으로 IR 코드를 즉시 송출."""
    dv.clearAndSendNamedIr(name)


@handle_exception
def ir_buffered_send_ch(dv, ch: int):
    """이미 진행 중인 송출이 있으면 큐에 이어 등록 (끊지 않음)."""
    dv.bufferedSendIr(ch)


@handle_exception
def ir_buffered_send_name(dv, name: str):
    dv.bufferedSendNamedIr(name)


@handle_exception
def ir_on(dv, ch: int):
    """지정한 IR 코드를 버튼을 누르고 있는 것처럼 연속 송출 (offIr 로 멈출 때까지)."""
    dv.onIr(ch)


@handle_exception
def ir_on_name(dv, name: str):
    dv.onNamedIr(name)


@handle_exception
def ir_off(dv):
    dv.offIr()


@handle_exception
def ir_keypad_macro(dv, code: int):
    """ir_set_keypad_mode() 로 설정한 패턴에 따라 숫자 키패드 코드를 큐에 등록."""
    dv.keypadMacro(code)


@handle_exception
def ir_set_keypad_mode(dv, mode: int):
    dv.keypadMode(mode)


@handle_exception
def ir_load_file(dv, filename: str):
    """CE-IRS4 설정 웹페이지에 업로드된 .irl 파일을 로드."""
    dv.loadIrFile(filename)


@handle_exception
def ir_enable_fault_detection(dv):
    dv.enableFaultDetection()


@handle_exception
def ir_disable_fault_detection(dv):
    dv.disableFaultDetection()


@handle_exception
def ir_listen_fault(dv, callback):
    """IR 버드 미부착/역결선 등 fault 이벤트 콜백 등록."""
    dv.fault.listen(callback)


@handle_exception
def ir_send(dv, data: bytes):
    """IR 포트를 1-way COM 포트로 쓸 때(mode=DATA) 데이터 송신."""
    dv.send(data)


@handle_exception
def ir_request_status(dv):
    """status 는 이벤트형이라 getStatus() 로 갱신을 요청하고 ir_listen_status() 로 결과를 받는다."""
    dv.getStatus()


@handle_exception
def ir_listen_status(dv, callback):
    dv.status.listen(callback)


# ---------------------------------------------------------------------------- #
# Relay 포트 (state 파라미터 하나뿐, T/F)
# ---------------------------------------------------------------------------- #


@handle_exception
def relay_get(dv):
    return dv.state.value


@handle_exception
def relay_set(dv, state: bool):
    dv.state.value = state


@handle_exception
def relay_off(dv):
    dv.state.value = False


@handle_exception
def relay_on(dv):
    dv.state.value = True


@handle_exception
def relay_toggle(dv):
    dv.state.value = not dv.state.value


@handle_exception
def relay_watch(dv, callback):
    dv.state.watch(callback)
