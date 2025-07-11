from lib.lib_yeoul import handle_exception

# ---------------------------------------------------------------------------- #
VERSION = "2025.06.24"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
@handle_exception
def serial_disable_fault_detection(dv):
    dv.disableFaultDetection()


@handle_exception
def serial_enable_fault_detection(dv):
    dv.enableFaultDetection()


@handle_exception
def get_fault(dv):
    return dv.getFault()


@handle_exception
def serial_flush_receive_buffer(dv):
    dv.flushReceiveBuffer()


@handle_exception
def serial_disable_receive(dv):
    dv.disableReceive()


@handle_exception
def serial_enable_receive(dv):
    dv.enableReceive()


@handle_exception
def serial_clear_fault(dv):
    dv.clearFault()


@handle_exception
def serial_get_status(dv):
    return dv.status.value


@handle_exception
def init_serial(dv, baudrate="9600", bit="8", stop="1", parity="NONE", mode="232"):
    valid_baudrates = {"1200", "4800", "9600", "19200", "38400", "57600", "115200"}
    valid_bits = {"7", "8"}
    valid_stops = {"1", "2"}
    valid_parities = {"NONE", "EVEN", "ODD", "MARK", "SPACE"}
    valid_modes = {"232", "422", "485"}
    if baudrate not in valid_baudrates:
        raise ValueError(f"Invalid baudrate: {baudrate}")
    if bit not in valid_bits:
        raise ValueError(f"Invalid data bits: {bit}")
    if stop not in valid_stops:
        raise ValueError(f"Invalid stop bits: {stop}")
    if parity not in valid_parities:
        raise ValueError(f"Invalid parity: {parity}")
    if mode not in valid_modes:
        raise ValueError(f"Invalid mode: {mode}")
    dv.setCommParams(baudrate, bit, stop, parity, mode)
    serial_enable_receive(dv)


@handle_exception
def init_io(dv, io="INPUT", input_mode="ANALOG"):
    valid_io_modes = {"INPUT", "OUTPUT"}
    valid_input_modes = {"ANALOG", "DIGITAL"}
    if io not in valid_io_modes:
        raise ValueError(f"Invalid IO mode: {io}")
    if io == "INPUT" and input_mode not in valid_input_modes:
        raise ValueError(f"Invalid input mode: {input_mode}")
    dv.mode.value = io
    if io == "INPUT":
        dv.InputMode.value = input_mode


# ---------------------------------------------------------------------------- #
@handle_exception
def init_ir(dv, mode="IR"):
    valid_modes = {"IR", "SERIAL"}
    if mode not in valid_modes:
        raise ValueError(f"Invalid IR mode: {mode}")
    dv.mode.value = mode
    if mode == "IR":
        dv.carrier.value = True
