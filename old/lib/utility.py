# 마지막 수정일 : 20260505
import threading
import functools
import inspect
import threading
from typing import Callable


def start_thread(target, *args, **kwargs):
    """일회성 전송 스레드 시작"""
    try:
        thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
        thread.start()
        return thread
    except Exception as e:
        print(f"(ERROR) : start_thread() {e=}")
        return None


def run_thread(thread: threading.Thread | None, target: Callable, *args, **kwargs):
    """스레드가 None이거나 실행 중이 아니면 새 스레드를 시작 (스레드를 외부에서 관리)"""
    if not thread or not thread.is_alive():
        thread = threading.Thread(target=target, args=args, kwargs=kwargs, daemon=True)
        thread.start()
    return thread


def join_thread(thread: threading.Thread | None):
    """주어진 스레드의 완료를 대기 (데드락 방지: 현재 스레드가 자신을 기다리지 않도록 확인)"""
    if thread and thread.is_alive() and threading.current_thread() != thread:
        try:
            thread.join(timeout=1.0)
        except RuntimeError as e:
            print(f"(ERROR) : join_thread() {thread.name} failed {e=}")


class CommonLogger:
    debug: bool = False
    name: str = ""

    def _log_message(self, level: str, message):
        prefix = f"({level}) - {self.__class__.__name__}"
        if getattr(self, "name", None):
            print(f"{prefix} - {self.name} : {message}")
            return
        print(f"{prefix} : {message}")

    def log_debug(self, message):
        if self.debug:
            self._log_message("DEBUG", message)

    def log_error(self, message):
        self._log_message("ERROR", message)

    def log_warn(self, message):
        self._log_message(" WARN", message)

    def log_info(self, message):
        self._log_message(" INFO", message)


def handle_exception(func):
    """예외 발생 시 에러 로그를 출력하고 None을 반환하는 데코레이터"""

    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"(ERROR) - {func.__name__}() {e=}")
            return None

    return wrapper


@handle_exception
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


@handle_exception
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


@handle_exception
def _debug(max_depth=3):
    """호출 스택을 깊이별로 출력하여 함수 체인과 파라미터 확인"""
    log_message = ""
    current_frame = inspect.currentframe()
    depth = 0
    while current_frame and (depth < max_depth + 2):
        if depth > 1:
            func_name = current_frame.f_code.co_name if current_frame else "Unknown"
            # getargvalues를 사용하여 함수의 모든 지역 변수 추출
            args, _, _, values = inspect.getargvalues(current_frame)
            args_str = "*args: " + ", ".join(f"{arg}={values[arg]}" for arg in args) if args else ""
            # kwargs라는 이름의 딕셔너리 변수가 있으면 출력
            kwargs_str = ", ".join(f"{key}={value}" for key, value in values.get("kwargs", {}).items())
            if kwargs_str:
                args_str += f" **kwargs: {kwargs_str}"
            log_message += f"  $c{depth}f: {func_name}({args_str})\n"
        # 이전 프레임(호출한 함수)으로 이동
        current_frame = current_frame.f_back
        depth += 1
    log_message = log_message.removesuffix("\n")
    print("_debug\n" + log_message)
