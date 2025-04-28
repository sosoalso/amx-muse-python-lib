# ---------------------------------------------------------------------------- #
import functools
import inspect
import threading
from functools import wraps

# ---------------------------------------------------------------------------- #
from mojo import context

get_device = context.devices.get
get_service = context.services.get


# ---------------------------------------------------------------------------- #
def handle_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Exception occurred in {func.__name__}: {e}")
            return None

    return wrapper


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


@handle_exception
def print_with_name(msg):
    current_method = inspect.currentframe().f_back.f_code.co_name
    print(f"{current_method}() >> {msg}")


@handle_exception
def info_with_name(msg):
    current_method = inspect.currentframe().f_back.f_code.co_name
    uni_log_info(f"{current_method}() >> {msg}")


@handle_exception
def warn_with_name(msg):
    current_method = inspect.currentframe().f_back.f_code.co_name
    uni_log_warn(f"{current_method}() >> {msg}")


@handle_exception
def err_with_name(err, msg):
    current_method = inspect.currentframe().f_back.f_code.co_name
    raise err(f"{current_method}() {msg}")


# ---------------------------------------------------------------------------- #
@handle_exception
def hello(device):
    print("=" * 79)
    print(device)
    print("type : ", type(device))
    print("-" * 34)
    attributes = dir(device)
    print("-" * 34)
    filtered_attributes = [attr for attr in attributes if not attr.startswith("__") and not attr.endswith("__")]
    for attr in filtered_attributes:
        print("-" * 34)
        value = getattr(device, attr)
        # ---------------------------------------------------------------------------- #
        if callable(value):
            print(f"this is Method() -- {attr}")
            sig = inspect.signature(value)
            print(f"signature -- {sig}")
            print(f"signature parameters -- {sig.parameters}")
            if all(param.default != inspect.Parameter.empty for param in sig.parameters.values()):
                if attr == "shutdown":
                    print(f"Cannot call {attr} as it is literally SHUTDOWN")
                else:
                    print(f"calling method () -- {attr}")
                    print(f"return value == {value()}")
            else:
                print(f"Cannot call {attr} as it requires arguments: {sig.parameters}")
        # ---------------------------------------------------------------------------- #
        elif isinstance(value, property):
            print(f"this is Property -- {attr} : {value}")
        # ---------------------------------------------------------------------------- #
        else:
            print(f"this is Attribute -- {attr} : {value}")
        # ---------------------------------------------------------------------------- #
    print("=" * 79)


# ---------------------------------------------------------------------------- #
if __name__ == "__main__":
    pass
