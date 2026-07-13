# 마지막 수정일 : 20260713
"""AMX MUSE 런타임(context) 접근용 헬퍼 모음.

mojo 의 context 는 MUSE 컨트롤러가 주입하는 런타임 객체로,
장치(context.devices)·서비스(context.services)·로그(context.log)에 접근하는 진입점이다.
프로그램 어디서든 로그를 남기거나 장치/서비스 핸들을 얻을 때 이 모듈의 함수를 쓴다.
"""

from mojo import context


# context.log 래퍼들 : MUSE 컨트롤러 내장 로거로 출력한다
def muse_log_info(msg):
    context.log.info(msg)


def muse_log_error(msg):
    context.log.error(msg)


def muse_log_warn(msg):
    context.log.warn(msg)


def muse_log_debug(msg):
    context.log.debug(msg)


def muse_set_log_level(level: str):
    """로그 레벨을 검증 후 적용한다. 유효값: debug / info / warn / error (대소문자 무관)."""
    lvl = level.lower()
    valid_levels = ["debug", "info", "warn", "error"]
    if lvl not in valid_levels:
        raise ValueError(f"wrong log {level=}. Available log levels: {valid_levels}")
    context.log.level = lvl.upper()


def get_device(device_name):
    """MUSE 에 등록된 장치(터치패널, 시리얼 포트 등) 핸들을 이름으로 조회한다. 없으면 None."""
    return context.devices.get(device_name)


def get_service(service_name):
    """MUSE 내장 서비스(timeline, smtp 등) 핸들을 이름으로 조회한다."""
    return context.services.get(service_name)


def get_timeline():
    # timeline : 주기 실행/지연 실행에 쓰는 MUSE 내장 타이머 서비스
    return get_service("timeline")
