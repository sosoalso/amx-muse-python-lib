import functools
import inspect
import threading
from functools import wraps

# ---------------------------------------------------------------------------- #
from mojo import context

get_device = context.devices.get
get_service = context.services.get


def get_timeline():
    return get_service("timeline")


# ---------------------------------------------------------------------------- #
def handle_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            uni_log_debug(f"함수 {func.__name__} 에러 발생: {e}")
            return None

    return wrapper


# ---------------------------------------------------------------------------- #


class pulse:
    def __init__(self, duration, off_method, *off_args, **off_kwargs):
        self.duration = duration
        self.off_method = off_method
        self.off_args = off_args
        self.off_kwargs = off_kwargs

    @handle_exception
    def __call__(self, func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            threading.Thread(target=self.pulse_thread).start()
            return result

        return wrapper

    @handle_exception
    def pulse_thread(self):
        # time.sleep(self.duration)
        threading.Event().wait(self.duration)
        self.off_method(*self.off_args, **self.off_kwargs)


# ---------------------------------------------------------------------------- #
@handle_exception
def debounce(timeout_ms: float):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if hasattr(wrapper, "func_timer") and wrapper.func_timer.is_alive():
                wrapper.func_timer.cancel()
            wrapper.func_timer = threading.Timer(timeout_ms / 1000, func, args, kwargs)
            wrapper.func_timer.start()

        return wrapper

    return decorator


# ---------------------------------------------------------------------------- #
def uni_log_info(msg):
    context.log.info(msg.encode("utf-16").decode("utf-16"))


def uni_log_warn(msg):
    context.log.warn(msg.encode("utf-16").decode("utf-16"))


def uni_log_error(msg):
    context.log.error(msg.encode("utf-16").decode("utf-16"))


def uni_log_debug(msg):
    context.log.debug(msg.encode("utf-16").decode("utf-16"))


# ---------------------------------------------------------------------------- #


@handle_exception
def debug(max_depth=7):
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
            log_message += f"  c{depth}f$ {func_name}({args_str})"
        current_frame = current_frame.f_back
        depth += 1
    # log_message = log_message.removeprefix(" $ ")
    uni_log_debug(log_message)  # Uncommented to log the debug message


# ---------------------------------------------------------------------------- #
@handle_exception
def hello(device):
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
