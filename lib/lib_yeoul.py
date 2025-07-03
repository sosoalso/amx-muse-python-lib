import functools
import inspect
import threading

from mojo import context

# ---------------------------------------------------------------------------- #
VERSION = "2025.07.02"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
get_device = context.devices.get
get_service = context.services.get


def get_timeline():
    return context.services.get("timeline")


# ---------------------------------------------------------------------------- #
log_info = context.log.info
log_error = context.log.error
log_warn = context.log.warn
log_debug = context.log.debug


def set_log_level(level):
    valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "debug", "info", "warning", "error"]
    if level not in valid_levels:
        raise ValueError(f"Invalid log level: {level}. Choose from {valid_levels}.")
    context.log.level = level.upper()


# ---------------------------------------------------------------------------- #
def handle_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            context.log.error(f"함수 {func.__name__} 에러 발생: {e}")
            return None

    return wrapper


# ---------------------------------------------------------------------------- #
@handle_exception
def pulse(duration, off_method, *off_args, **off_kwargs):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            threading.Timer(duration, off_method, args=off_args, kwargs=off_kwargs).start()
            return result

        return wrapper

    return decorator


# ---------------------------------------------------------------------------- #
@handle_exception
def debounce(timeout_ms: float):
    def decorator(func):
        lock = threading.Lock()

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            func_timer = None
            with lock:
                if func_timer and func_timer.is_alive():
                    func_timer.cancel()
                func_timer = threading.Timer(timeout_ms / 1000, func, args=args, kwargs=kwargs)
                func_timer.start()

        return wrapper

    return decorator


# ---------------------------------------------------------------------------- #
@handle_exception
def _debug(max_depth=3):
    log_message = ""
    current_frame = inspect.currentframe()
    depth = 0
    while current_frame and (depth < max_depth + 2):
        if depth > 1:
            func_name = current_frame.f_code.co_name if current_frame else "Unknown"
            args, _, _, values = inspect.getargvalues(current_frame)
            args_str = "*args: " + ", ".join(f"{arg}={values[arg]}" for arg in args) if args else ""
            kwargs_str = ", ".join(f"{key}={value}" for key, value in values.get("kwargs", {}).items())
            if kwargs_str:
                args_str += f" **kwargs: {kwargs_str}"
            log_message += f"  $c{depth}f: {func_name}({args_str})\n"
        current_frame = current_frame.f_back
        depth += 1
    log_message = log_message.removesuffix("\n")
    context.log.debug("_debug\n" + log_message)


# ---------------------------------------------------------------------------- #
@handle_exception
def _hello(device):
    context.log.debug("=" * 79)
    context.log.debug(device)
    context.log.debug("type : ", type(device))
    context.log.debug("-" * 34)
    attributes = dir(device)
    context.log.debug("-" * 34)
    filtered_attributes = [attr for attr in attributes if not attr.startswith("__") and not attr.endswith("__")]
    for attr in filtered_attributes:
        context.log.debug("-" * 34)
        value = getattr(device, attr)
        # ---------------------------------------------------------------------------- #
        if callable(value):
            context.log.debug(f"this is Method() -- {attr}")
            sig = inspect.signature(value)
            context.log.debug(f"signature -- {sig}")
            context.log.debug(f"signature parameters -- {sig.parameters}")
            if all(param.default != inspect.Parameter.empty for param in sig.parameters.values()):
                if attr == "shutdown":
                    context.log.debug(f"Cannot call {attr} as it is literally SHUTDOWN")
                else:
                    context.log.debug(f"calling method () -- {attr}")
                    context.log.debug(f"return value == {value()}")
            else:
                context.log.debug(f"Cannot call {attr} as it requires arguments: {sig.parameters}")
        # ---------------------------------------------------------------------------- #
        elif isinstance(value, property):
            context.log.debug(f"this is Property -- {attr} : {value}")
        # ---------------------------------------------------------------------------- #
        else:
            context.log.debug(f"this is Attribute -- {attr} : {value}")
        # ---------------------------------------------------------------------------- #
    context.log.debug("=" * 79)
