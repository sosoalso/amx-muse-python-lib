# ---------------------------------------------------------------------------- #
import functools
import inspect
import threading

# ---------------------------------------------------------------------------- #
from mojo import context

get_device = context.devices.get
get_service = context.services.get


# ---------------------------------------------------------------------------- #
def simple_exception_handler(*exceptions):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                print(f"Exception occurred in {func.__name__}: {e}")
                return None
            except Exception as e:
                print(f"Exception occurred in {func.__name__}: {e}")
                return None

        return wrapper

    return decorator


# ---------------------------------------------------------------------------- #
@simple_exception_handler
def debounce(timeout_ms: float):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if hasattr(wrapper, "func_timer") and wrapper.func_timer.is_alive():
                wrapper.func_timer.cancel()  # 이미 실행 중인 타이머가 있다면 취소
            wrapper.func_timer = threading.Timer(timeout_ms / 1000, func, args, kwargs)
            wrapper.func_timer.start()  # 새로운 타이머 시작

        return wrapper

    return decorator


# ---------------------------------------------------------------------------- #
@simple_exception_handler
def print_with_name(msg):
    current_method = inspect.currentframe().f_back.f_code.co_name
    print(f"{current_method}() >> {msg}")


@simple_exception_handler
def info_with_name(msg):
    current_method = inspect.currentframe().f_back.f_code.co_name
    uni_log_info(f"{current_method}() >> {msg}")


@simple_exception_handler
def warn_with_name(msg):
    current_method = inspect.currentframe().f_back.f_code.co_name
    uni_log_warn(f"{current_method}() >> {msg}")


@simple_exception_handler
def err_with_name(err, msg):
    current_method = inspect.currentframe().f_back.f_code.co_name
    raise err(f"{current_method}() {msg}")


# ---------------------------------------------------------------------------- #
@simple_exception_handler
def uni_log_info(msg):
    print(("info " + msg).encode("utf-16").decode("utf-16"))


@simple_exception_handler
def uni_log_warn(msg):
    print(("warn " + msg).encode("utf-16").decode("utf-16"))


@simple_exception_handler
def uni_log_error(msg):
    print(("error " + msg).encode("utf-16").decode("utf-16"))


# ---------------------------------------------------------------------------- #
@simple_exception_handler
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
            # 인자가 없는 경우에만 호출하거나, 모든 인자가 기본값을 가진 경우 호출
            if all(param.default != inspect.Parameter.empty for param in sig.parameters.values()):
                if attr == "shutdown":
                    print("Cannot call {attr} as it is literally SHUTDOWN")
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
