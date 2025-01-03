# ---------------------------------------------------------------------------- #
from mojo import context

from lib.eventmanager import EventManager
from lib.lib_tp import tp_add_watcher
from lib.lib_yeoul import get_device, handle_exception
from lib.networkmanager import TcpClient
from lib.scheduler import Scheduler
from lib.userdata import UserData


# ---------------------------------------------------------------------------- #
# INFO : 장비 인스턴스
# ---------------------------------------------------------------------------- #
class GenericDeviceInstance(EventManager):
    def __init__(self, dv, name="generic_device_instance"):
        super().__init__("propname", "poll")
        self.dv = dv
        self.name = name
        self.userdata = UserData()
        self.poll = Scheduler()
        self.command_poll()
        # ---------------------------------------------------------------------------- #
        # NOTE : 프로퍼티 이렇게 초기화하기, 세터에도 set_value 붙일 때 valuename 맞춰줘야 함
        # ---------------------------------------------------------------------------- #
        self.propname = self.userdata.get_value(f"{self.name}_propname") or False  # init

    # ---------------------------------------------------------------------------- #
    @property
    def propname(self):
        return self.power

    @propname.setter
    def propname(self, value):
        self.propname = value
        self.userdata.set_value(f"{self.name}_propname", self.propname)

    # ---------------------------------------------------------------------------- #
    @handle_exception
    def command_set_prop(self, value=None):
        print(f"{__class__} command_set_prop")
        self.trigger_event("propname", value=value, this=self)

    # ---------------------------------------------------------------------------- #
    @handle_exception
    def on_poll(self):
        self.trigger_event("poll", this=self)

    @handle_exception
    def command_poll(self):
        print(f"{__class__} command_poll")
        self.poll.set_interval(self.on_poll, 10)  # sec


# ---------------------------------------------------------------------------- #
# NOTE : 장비 인스턴스 만들기기
# ---------------------------------------------------------------------------- #
my_tcp_socket = TcpClient(name="test", ip="127.0.0.1", port=12345)
# my_serial = context.devices.get("idevice").serial[0]
my_device_instance = GenericDeviceInstance(my_tcp_socket, "genericDeviceInstance")
# my_device_instance = GenericDeviceInstance(my_serial, "genericDeviceInstance")
my_tcp_socket.connect()


# ---------------------------------------------------------------------------- #
# NOTE : 실제 동작 구현
# ---------------------------------------------------------------------------- #
@handle_exception
def genericDeviceInstanceHandleProps(value=None, this=None):
    print(f"genericDeviceInstanceHandleProps {value=} {this=}")
    this.dv.send("POWR1" if value else "POWR0")
    this.propname = value
    this.userdata.set_value(f"{this.name}_power", this.power)


@handle_exception
def genericDeviceInstanceHandlePoll(this=None):
    this.dv.send("polling message")
    # print(f"vidprj_handle_poll {this=} {this.power=} {this.mute=}")


# ---------------------------------------------------------------------------- #
# NOTE : 이벤트에 맞춰 실제 동작 집어넣기
# ---------------------------------------------------------------------------- #
my_device_instance.add_event_handler("propname", genericDeviceInstanceHandleProps)
my_device_instance.add_event_handler("poll", genericDeviceInstanceHandlePoll)


# ---------------------------------------------------------------------------- #
# INFO : 디바이스 응답 파싱
# ---------------------------------------------------------------------------- #
# NOTE : 실제 동작 구현
# ---------------------------------------------------------------------------- #
@handle_exception
def genericDeviceInstanceHandleReceive(*args, this=None):
    print("genericDeviceInstanceHandleReceive")
    data = args[0].arguments["data"].decode()
    print("data: ", data)
    print("this: ", this)
    if isinstance(this, GenericDeviceInstance):
        # NOTE : parse data
        if data.startswith("received_comamnd"):
            this.propname = True  # process data


# NOTE : 인스턴스 별 실제 동작 집어 넣기
my_tcp_socket.receive.listen(lambda evt, this=my_device_instance: genericDeviceInstanceHandleReceive(evt, this=this))


# ---------------------------------------------------------------------------- #
# INFO : 버튼 이벤트 등록
# ---------------------------------------------------------------------------- #
def tp_handle_my_device_propname_button(*args):
    if args[0].value:
        my_device_instance.command_set_prop(state=True)


# ---------------------------------------------------------------------------- #
def ui_register():
    tp_add_watcher(tp_10001, 1, 11, tp_handle_my_device_propname_button)


def start(*args):
    ui_register()


muse.online(start)
