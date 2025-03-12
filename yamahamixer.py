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
class YamahaMixer(EventManager):
    def __init__(self, dv, name="yamaha_mixer"):
        super().__init__()
        self.dv = dv
        self.name = name
        self.userdata = UserData()
        # self.poll = Scheduler()
        # self.command_poll()
        # ---------------------------------------------------------------------------- #
        # NOTE : 프로퍼티 이렇게 초기화하기, 세터에도 set_value 붙일 때 valuename 맞춰줘야 함
        # ---------------------------------------------------------------------------- #
        self.power = self.userdata.get_value(f"{self.name}_power") or False  # init
        self.mute = self.userdata.get_value(f"{self.name}_mute") or False  # init

    # ---------------------------------------------------------------------------- #
    @property
    def power(self):
        return self.power

    @power.setter
    def power(self, value):
        self.power = value
        self.userdata.set_value(f"{self.name}_power", self.power)

    # ---------------------------------------------------------------------------- #
    @handle_exception
    def command_set_power(self, value=None):
        print(f"{__class__} command_set_power")
        self.trigger_event("power", value=value, this=self)

    @property
    def mute(self):
        return self.mute

    @mute.setter
    def mute(self, value):
        self.mute = value
        self.userdata.set_value(f"{self.name}_mute", self.mute)

    # ---------------------------------------------------------------------------- #
    @handle_exception
    def command_set_mute(self, value=None):
        print(f"{__class__} command_set_mute")
        self.trigger_event("mute", value=value, this=self)

    # -------
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
# my_tcp_socket = TcpClient(name="test", ip="127.0.0.1", port=12345)
# my_serial = context.devices.get("idevice").serial[0]
# my_device_instance = EpsonVidprj(my_tcp_socket, "epsonVidprj")
# my_device_instance = EpsonVidprj(my_serial, "epsonVidprj")
# my_tcp_socket.connect()


# ---------------------------------------------------------------------------- #
# NOTE : 실제 동작 구현
# ---------------------------------------------------------------------------- #
@handle_exception
def epson_vidprj_handle_power(value=None, this=None):
    print(f"epson_vidprj_handle_power {value=} {this=}")
    this.dv.send("PWR ON\n" if value else "PWR OFF\n")
    this.power = value


@handle_exception
def epson_vidprj_handle_mute(value=None, this=None):
    print(f"epson_vidprj_handle_mute {value=} {this=}")
    this.dv.send("MUTE ON\n" if value else "MUTE OFF\n")
    this.mute = value


@handle_exception
async def on_epson_vidprj_poll(this=None):
    this.dv.send("PWR?\n")
    this.dv.send("MUTE?\n")
    # print(f"vidprj_handle_poll {this=} {this.power=} {this.mute=}")


def epson_vidprj_handle_poll():
    asyncio.run(on_epson_vidprj_poll(this=my_device_instance))


# ---------------------------------------------------------------------------- #
# NOTE : 이벤트에 맞춰 실제 동작 집어넣기
# ---------------------------------------------------------------------------- #
my_device_instance.add_event_handler("propname", epson_vidprj_handle_power)
my_device_instance.add_event_handler("poll", epsonVidprjHandlePoll)


# ---------------------------------------------------------------------------- #
# INFO : 디바이스 응답 파싱
# ---------------------------------------------------------------------------- #
# NOTE : 실제 동작 구현
# ---------------------------------------------------------------------------- #
@handle_exception
def epsonVidprjHandleReceive(*args, this=None):
    print("epsonVidprjHandleReceive")
    data = args[0].arguments["data"].decode()
    print("data: ", data)
    print("this: ", this)
    if isinstance(this, EpsonVidprj):
        # NOTE : parse data
        if data.startswith("received_comamnd"):
            this.propname = True  # process data


# NOTE : 인스턴스 별 실제 동작 집어 넣기
my_tcp_socket.receive.listen(lambda evt, this=my_device_instance: epsonVidprjHandleReceive(evt, this=this))


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
# ---------------------------------------------------------------------------- #
if __name__ == "__main__":
    pass
