# 마지막 수정일 : 20260514
from mojo import context

muse_log_info = context.log.info
muse_log_error = context.log.error
muse_log_warn = context.log.warn
muse_log_debug = context.log.debug


def set_log_level(level):
    valid_levels = ["DEBUG", "INFO", "WARN", "ERROR", "debug", "info", "warn", "error"]
    if level not in valid_levels:
        raise ValueError(f"wrong log {level=}. Available log levels: {valid_levels}")
    context.log.level = level.upper()


get_device = context.devices.get
get_service = context.services.get


def get_timeline():
    return context.services.get("timeline")
