from mojo import context

# ---------------------------------------------------------------------------- #
VERSION = "2026.04.10"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
def serial_disable_fault_detection(dv):
    dv.disableFaultDetection()


def serial_enable_fault_detection(dv):
    dv.enableFaultDetection()


def get_fault(dv):
    return dv.getFault()


def serial_flush_receive_buffer(dv):
    # 수신 버퍼에 남아있는 데이터를 모두 제거
    dv.flushReceiveBuffer()


def serial_disable_receive(dv):
    dv.disableReceive()


def serial_enable_receive(dv):
    dv.enableReceive()


def serial_clear_fault(dv):
    dv.clearFault()


def serial_get_status(dv):
    return dv.status.value


def init_serial(dv, baudrate="9600", bit="8", stop="1", parity="NONE", mode="232"):
    try:
        # 시리얼 통신 매개변수의 유효한 값들을 정의
        valid_baudrates = {"1200", "4800", "9600", "19200", "38400", "57600", "115200"}
        valid_bits = {"7", "8"}
        valid_stops = {"1", "2"}
        valid_parities = {"NONE", "EVEN", "ODD", "MARK", "SPACE"}
        valid_modes = {"232", "422", "485"}

        # 입력된 매개변수 값이 유효한 범위에 있는지 검증
        if baudrate not in valid_baudrates:
            raise ValueError(f"잘못된 baudrate: {baudrate}")
        if bit not in valid_bits:
            raise ValueError(f"잘못된 data bits: {bit}")
        if stop not in valid_stops:
            raise ValueError(f"잘못된 stop bits: {stop}")
        if parity not in valid_parities:
            raise ValueError(f"잘못된 parity: {parity}")
        if mode not in valid_modes:
            raise ValueError(f"잘못된 mode: {mode}")

        # 검증 완료된 매개변수를 기기에 적용
        dv.setCommParams(baudrate, bit, stop, parity, mode)
        serial_enable_receive(dv)
    except Exception as e:
        context.log.error(f"init_serial() 에러: {e}")


def init_io(dv, io="INPUT", input_mode="ANALOG"):
    try:
        # IO 포트의 유효한 동작 모드 정의
        valid_io_modes = {"INPUT", "OUTPUT"}
        valid_input_modes = {"ANALOG", "DIGITAL"}

        # 입력 매개변수 유효성 검증
        if io not in valid_io_modes:
            raise ValueError(f"Invalid IO mode: {io}")
        if io == "INPUT" and input_mode not in valid_input_modes:
            raise ValueError(f"Invalid input mode: {input_mode}")

        # IO 모드 설정
        dv.mode.value = io
        if io == "INPUT":
            dv.InputMode.value = input_mode
    except Exception as e:
        context.log.error(f"init_io() 에러: {e}")


# ---------------------------------------------------------------------------- #
def init_ir(dv, mode="IR"):
    try:
        # IR 포트의 유효한 동작 모드 정의
        valid_modes = {"IR", "SERIAL"}

        # 입력된 IR 모드 유효성 검증
        if mode not in valid_modes:
            raise ValueError(f"잘못된 IR mode: {mode}")

        # IR 모드 설정 및 IR 모드일 경우 캐리어 활성화
        dv.mode.value = mode
        if mode == "IR":
            dv.carrier.value = True
    except Exception as e:
        context.log.error(f"init_ir() 에러: {e}")
