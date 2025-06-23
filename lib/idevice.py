# idevice
from enum import Enum

# ---------------------------------------------------------------------------- #
VERSION = "2025.06.20"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #


class IDeviceSerialBaudrate(Enum):
    BAUD_1200 = "1200"
    BAUD_4800 = "4800"
    BAUD_9600 = "9600"
    BAUD_19200 = "19200"
    BAUD_38400 = "38400"
    BAUD_57600 = "57600"
    BAUD_115200 = "115200"


class IDeviceSerialStopBits(Enum):
    STOP_1 = 1
    STOP_2 = 2


class IDeviceSerialDataBits(Enum):
    DATA_7 = 7
    DATA_8 = 8


class IDeviceSerialFlowControl(Enum):
    NONE = "NONE"
    HARDWARE = "HARDWARE"


class IDeviceSerialMode(Enum):
    MODE_232 = "232"
    MODE_422 = "422"
    MODE_485 = "485"


class IDeviceSerialParity(Enum):
    NONE = "NONE"
    EVEN = "EVEN"
    ODD = "ODD"
    MARK = "MARK"
    SPACE = "SPACE"


def serial_disable_fault_detection(dv):
    dv.disableFaultDetection()


def serial_enable_fault_detection(dv):
    dv.enableFaultDetection()


def get_fault(dv):
    return dv.getFault()


def serial_flush_receive_buffer(dv):
    dv.flushReceiveBuffer()


def serial_disable_receive(dv):
    dv.disableReceive()


def serial_enable_receive(dv):
    dv.enableReceive()


def serial_clear_fault(dv):
    dv.clearFault()


def serial_get_status(dv):
    return dv.status.value


def init_serial(
    dv,
    baudrate=IDeviceSerialBaudrate.BAUD_9600,
    bit=IDeviceSerialDataBits.DATA_8,
    stop=IDeviceSerialStopBits.STOP_1,
    parity=IDeviceSerialParity.NONE,
    mode=IDeviceSerialMode.MODE_232,
):
    dv.setCommParams(baudrate, bit, stop, parity, mode)
    serial_enable_receive(dv)


class IDeviceIOMode(Enum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"


class IDeviceIOInputMode(Enum):
    ANALOG = "ANALOG"
    DIGITAL = "DIGITAL"


def init_io(dv, io=IDeviceIOMode.INPUT, input_mode=IDeviceIOInputMode.ANALOG):
    dv.mode.value = io
    if io == IDeviceIOMode.INPUT:
        dv.iDeviceIOInputMode.value = input_mode


# ---------------------------------------------------------------------------- #
class IDeviceIRMode(Enum):
    IR = "IR"
    SERIAL = "SERIAL"


def init_ir(dv, mode=IDeviceIRMode.IR):
    dv.mode.value = mode
    if mode == IDeviceIRMode.IR:
        dv.carrier.value = True
