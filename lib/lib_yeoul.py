import functools
import inspect
import threading

from mojo import context

# ---------------------------------------------------------------------------- #
VERSION = "2026.04.10"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
get_device = context.devices.get
# ---------------------------------------------------------------------------- #
get_service = context.services.get


def get_timeline():
    context.log.error("타임라인은 정상적인 동작을 확인하기 전까지 개인적으로 사용을 매우 매우 비권장...")
    return context.services.get("timeline")


# ---------------------------------------------------------------------------- #
log_info = context.log.info
log_error = context.log.error
log_warn = context.log.warn
log_debug = context.log.debug


def set_log_level(level):
    valid_levels = ["DEBUG", "INFO", "WARN", "ERROR", "debug", "info", "warn", "error"]
    if level not in valid_levels:
        raise ValueError(f"잘못된 로그 레벨: {level}. 선택 가능한 로그 레벨: {valid_levels}")
    context.log.level = level.upper()


# ---------------------------------------------------------------------------- #
def handle_exception(func):
    # 예외 발생 시 에러 로그를 출력하고 None을 반환하는 데코레이터
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            context.log.error(f"{func.__name__}() 에러: {e}")
            return None

    return wrapper


# ---------------------------------------------------------------------------- #
@handle_exception
def pulse(duration_seconds, off_method, *off_args, **off_kwargs):
    # 함수 실행 후 지정된 시간 후에 off_method를 자동으로 호출하는 데코레이터
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            # Threading.Timer를 사용하여 비동기로 off_method 실행
            threading.Timer(duration_seconds, off_method, args=off_args, kwargs=off_kwargs).start()
            return result

        return wrapper

    return decorator


# ---------------------------------------------------------------------------- #
@handle_exception
def debounce(timeout_ms: float):
    # 마지막 호출로부터 지정된 시간 동안 동일한 함수 호출을 무시하는 데코레이터
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
    # 문자열을 정수로 변환 (숫자가 아닌 문자는 무시, 부호는 유지)
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


# ---------------------------------------------------------------------------- #
@handle_exception
def _debug(max_depth=3):
    # 호출 스택을 깊이별로 출력하여 함수 체인과 파라미터 확인
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
    context.log.debug("_debug\n" + log_message)


# ---------------------------------------------------------------------------- #
@handle_exception
def _hello(device):
    # 객체의 모든 속성과 메서드를 탐색하여 상세 정보 출력
    context.log.debug("=" * 79)
    context.log.debug(device)
    context.log.debug("type : ", type(device))
    context.log.debug("-" * 34)
    attributes = dir(device)
    context.log.debug("-" * 34)
    # 매직 메서드(__xxx__)를 제외한 속성만 필터링
    filtered_attributes = [attr for attr in attributes if not attr.startswith("__") and not attr.endswith("__")]
    for attr in filtered_attributes:
        context.log.debug("-" * 34)
        value = getattr(device, attr)
        # ---------------------------------------------------------------------------- #
        if callable(value):
            # 호출 가능한 메서드인 경우
            context.log.debug(f"함수() -- {attr}")
            sig = inspect.signature(value)
            context.log.debug(f"시그니처 -- {sig}")
            context.log.debug(f"시그니처 파라메터 -- {sig.parameters}")
            # 모든 파라미터가 기본값을 가지면 안전하게 호출 가능
            if all(param.default != inspect.Parameter.empty for param in sig.parameters.values()):
                if attr == "shutdown":
                    context.log.debug("말그대로 SHUTDOWN 이라 안댐ㅋ")
                else:
                    context.log.debug(f"메소드 호출 () -- {attr}")
                    context.log.debug(f"리턴 값 == {value()}")
            else:
                context.log.debug(f"{attr} 메소드는 인자가 필요해서 호출할 수 없음 {sig.parameters=}")
        # ---------------------------------------------------------------------------- #
        elif isinstance(value, property):
            # 프로퍼티인 경우
            context.log.debug(f"프로퍼티 -- {attr} : {value}")
        # ---------------------------------------------------------------------------- #
        else:
            # 일반 속성인 경우
            context.log.debug(f"어트리뷰트 -- {attr} : {value}")
        # ---------------------------------------------------------------------------- #
    context.log.debug("=" * 79)
