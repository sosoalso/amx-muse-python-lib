# 마지막 수정일 : 20260629
import functools
import inspect
import threading
from typing import Callable


def handler_loc(handler, path_parts: int = 3) -> str:
    """핸들러 함수의 qualname과 소스 위치(파일:줄번호)를 반환. path_parts: 경로 끝에서 남길 세그먼트 수"""
    try:
        src = inspect.getsourcefile(handler) or ""
        line = inspect.getsourcelines(handler)[1]
        name = getattr(handler, "__qualname__", repr(handler))
        parts = src.replace("\\", "/").split("/")
        src = "/".join(parts[-path_parts:])
        return f"{name} ({src}:{line})"
    except Exception:
        return repr(handler)


try:
    from mojo import context as _mojo_context
except ImportError:
    _mojo_context = None


def start_thread(target, *args, **kwargs):
    """일회성 전송 스레드 시작"""
    try:
        thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
        thread.start()
        return thread
    except Exception as e:
        print(f"(ERROR) : start_thread() {e=}", end="\n", flush=True)
        return None


def run_thread(thread: threading.Thread | None, target: Callable, *args, **kwargs):
    """스레드가 None이거나 실행 중이 아니면 새 스레드를 시작 (스레드를 외부에서 관리)"""
    if not thread or not thread.is_alive():
        thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
        thread.start()
    return thread


class CommonLogger:
    debug: bool = False
    name: str = ""

    def _log_message(self, level: str, message):
        cls_name = self.__class__.__name__
        name = getattr(self, "name", None)
        if _mojo_context is not None:
            log_fn = getattr(_mojo_context.log, level.strip().lower(), None)
            if log_fn:
                if name:
                    log_fn(f"{cls_name} - {name} : {message}")
                else:
                    log_fn(f"{cls_name} : {message}")
                return
        if name:
            full_msg = f"({level}) - {cls_name} - {name} : {message}"
        else:
            full_msg = f"({level}) - {cls_name} : {message}"
        print(full_msg, end="\n", flush=True)

    def log_debug(self, message):
        if self.debug:
            self._log_message("DEBUG", message)

    def log_error(self, message):
        self._log_message("ERROR", message)

    def log_warn(self, message):
        self._log_message("WARN", message)

    def log_info(self, message):
        self._log_message("INFO", message)


def handle_exception(func):
    """예외 발생 시 에러 로그를 출력하고 re-raise하는 데코레이터"""

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"(ERROR) : {func.__name__}() {e=}", end="\n", flush=True)
            raise

    return wrapper


def pulse(duration_seconds, off_method, *off_args, **off_kwargs):
    """함수 실행 후 지정된 시간 후에 off_method를 자동으로 호출하는 데코레이터"""

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            # Threading.Timer를 사용하여 비동기로 off_method 실행
            threading.Timer(duration_seconds, off_method, args=off_args, kwargs=off_kwargs).start()
            return result

        return wrapper

    return decorator


def debounce(timeout_ms: float):
    """마지막 호출로부터 지정된 시간 동안 동일한 함수 호출을 무시하는 데코레이터"""

    def decorator(func):
        lock = threading.Lock()
        func_timer = None

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            nonlocal func_timer
            with lock:
                # 이전 타이머가 실행 중이면 취소
                if func_timer and func_timer.is_alive():
                    func_timer.cancel()
                # 새로운 타이머 설정 (밀리초를 초로 변환)
                func_timer = threading.Timer(timeout_ms / 1000, func, args=args, kwargs=kwargs)
                func_timer.start()

        return wrapper

    return decorator


def atoi(s: str) -> int:
    """문자열을 정수로 변환 (숫자가 아닌 문자는 무시, 부호는 유지)"""
    s = s.strip()
    if not s:
        return 0
    # 부호 처리
    sign = 1
    if s[0] == "-":
        sign = -1
    elif s[0] == "+":
        sign = 1
    # 숫자만 추출
    digits = [ch for ch in s if ch.isdigit()]
    if not digits:
        return 0
    return sign * int("".join(digits))


def safe_index(lst, value, default=-1):
    try:
        return lst.index(value)
    except ValueError:
        return default
