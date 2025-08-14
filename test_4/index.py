import random
import threading
import time

from mojo import context

IDEVICE = context.devices.get("idevice")
TP_10001 = context.devices.get("AMX-10001")
TP_10002 = context.devices.get("AMX-10002")
# ---------------------------------------------------------------------------- #
# TL_01 = context.services.get("timeline")

context.log.level = "DEBUG"


# ---------------------------------------------------------------------------- #
def on_tp_online(evt):
    context.log.info(f"on_tp_online: {evt.__dict__}")


def on_tp_offline(evt):
    context.log.info(f"on_tp_offline: {evt.__dict__}")


def watch_tp_button(evt):
    context.log.warn(f"watch_tp_button: {evt.__dict__}")


def watch_tp_channel(evt):
    context.log.info(f"watch_tp_channel: {evt.__dict__}")


# ---------------------------------------------------------------------------- #
def make_tp_feedback(*args):
    while True:
        context.log.info("make_tp_feedback")
        TP_10001.port[1].channel[1].value = not TP_10001.port[1].channel[1].value
        TP_10002.port[1].channel[1].value = not TP_10002.port[1].channel[1].value
        random_number = random.randint(2, 512)
        TP_10001.port[1].channel[random_number].value = random.choice([True, False])
        TP_10002.port[1].channel[random_number].value = random.choice([True, False])
        time.sleep(1)


# ---------------------------------------------------------------------------- #
if __name__ == "__main__":
    for i in range(1, 513):
        TP_10001.port[1].button[i].watch(watch_tp_button)
        TP_10002.port[1].button[i].watch(watch_tp_button)
        TP_10001.port[1].channel[i].watch(watch_tp_channel)
        TP_10002.port[1].channel[i].watch(watch_tp_channel)
    # ---------------------------------------------------------------------------- #
    TP_10001.online(on_tp_online)
    TP_10001.offline(on_tp_offline)
    # ---------------------------------------------------------------------------- #
    # TL_01.expired.listen(make_tp_feedback)
    # TL_01.start([1000], True, -1)
    IDEVICE.online(lambda evt: context.log.info(f"idevice is online  {evt=}"))
    threading.Thread(target=make_tp_feedback, daemon=True).start()
    # leave this as the last line in the Python script
    context.run(globals())
