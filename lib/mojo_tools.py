from mojo import context

# ---------------------------------------------------------------------------- #
VERSION = "2026.04.24"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
get_device = context.devices.get
# ---------------------------------------------------------------------------- #
muse_log_info = context.log.info
muse_log_error = context.log.error
muse_log_warn = context.log.warn
muse_log_debug = context.log.debug


def set_log_level(level):
    valid_levels = ["DEBUG", "INFO", "WARN", "ERROR", "debug", "info", "warn", "error"]
    if level not in valid_levels:
        raise ValueError(f"wrong log {level=}. Available log levels: {valid_levels}")
    context.log.level = level.upper()


# ---------------------------------------------------------------------------- #
get_service = context.services.get


def get_timeline():
    # context.log.error("타임라인은 정상적인 동작을 확인하기 전까지 개인적으로 사용을 매우 매우 비권장...")
    return context.services.get("timeline")
