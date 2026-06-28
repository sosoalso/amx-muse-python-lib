# 마지막 수정일 : 20260629
from mojo import context


def muse_log_info(msg):
    context.log.info(msg)


def muse_log_error(msg):
    context.log.error(msg)


def muse_log_warn(msg):
    context.log.warn(msg)


def muse_log_debug(msg):
    context.log.debug(msg)


def muse_set_log_level(level: str):
    lvl = level.lower()
    valid_levels = ["debug", "info", "warn", "error"]
    if lvl not in valid_levels:
        raise ValueError(f"wrong log {level=}. Available log levels: {valid_levels}")
    context.log.level = lvl.upper()


def get_device(device_name):
    return context.devices.get(device_name)


def get_service(service_name):
    return context.services.get(service_name)


def get_timeline():
    return get_service("timeline")
