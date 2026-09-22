# 마지막 수정일 : 20260713
"""표준 라이브러리(urllib)만으로 만든 간단한 비동기 HTTP 클라이언트.
모든 요청은 백그라운드 스레드에서 실행되어 제어 로직을 블로킹하지 않으며,
결과/실패는 callback / error_callback 으로 전달된다.
MUSE 컨트롤러도 pip 설치 자체는 가능하지만 번거로워서, requests 같은 외부 패키지 없이
내장 라이브러리만으로 REST API 기반 장비 제어를 처리하고 싶을 때 사용한다.
"""

import json
import urllib.error
import urllib.request
from typing import Callable

from lib.utility import CommonLogger, start_thread

DEFAULT_TIMEOUT = 1.0
DEFAULT_JSON_HEADER = {"Content-Type": "application/json; charset=UTF-8"}
# ---------------------------------------------------------------------------- #
simple_url_requests_logger = CommonLogger()


# ---------------------------------------------------------------------------- #
def log_error(message):
    simple_url_requests_logger.log_error(message)


def log_debug(message):
    simple_url_requests_logger.log_debug(message)


# ---------------------------------------------------------------------------- #
def _run_callback(callback: Callable | None, *args):
    """콜백이 있으면 실행. 콜백 내부 예외는 로그만 남기고 전파하지 않는다."""
    if not callback:
        return
    try:
        callback(*args)
    except Exception as e:
        log_error(f"callback failed {e=}")


def _make_headers(header: dict | None = None, json_body=False):
    """json_body=True 면 JSON Content-Type 을 기본으로 깔고, 사용자 헤더로 덮어쓴다."""
    headers = dict(DEFAULT_JSON_HEADER) if json_body else {}
    if header:
        headers.update(header)
    return headers


def url_request(
    method: str,
    url: str,
    header: dict | None = None,
    body=None,
    callback: Callable | None = None,
    error_callback: Callable | None = None,
    timeout: float = DEFAULT_TIMEOUT,
):
    """HTTP 요청을 백그라운드 스레드로 실행하고 그 스레드 객체를 반환.
    POST/PUT/PATCH 이고 body 가 있으면 JSON 으로 직렬화해 전송한다.
    응답 Content-Type 이 JSON 이면 파싱된 객체를, 아니면 raw bytes 를
    callback 에 전달한다. 네트워크 오류/타임아웃/직렬화 실패 시
    error_callback(예외) 를 호출한다.
    """
    method = method.upper()
    log_debug(f"url_request() {method=} {url=} {header=} {body=} {callback=} {timeout=}")

    def task():
        data = None
        json_body = method in ("POST", "PUT", "PATCH") and body is not None
        if json_body:
            try:
                data = json.dumps(body).encode()
            except (TypeError, ValueError) as e:
                log_error(f"url_request() json serialization failed {method=} {url=} {e=}")
                _run_callback(error_callback, e)
                return
        req = urllib.request.Request(
            url=url,
            data=data,
            headers=_make_headers(header, json_body=json_body),
            method=method,
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
                content_type = response.headers.get("Content-Type", "")
                if "application/json" in content_type:
                    try:
                        _run_callback(callback, json.loads(raw.decode()))
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        _run_callback(callback, raw)
                else:
                    _run_callback(callback, raw)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            log_error(f"url_request() {method=} {url=} {e=}")
            _run_callback(error_callback, e)

    return start_thread(task)


def url_get(
    url: str,
    header: dict | None = None,
    callback: Callable | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    error_callback: Callable | None = None,
):
    """GET 요청 편의 함수. url_request("GET", ...) 래퍼."""
    return url_request(
        "GET",
        url,
        header=header,
        callback=callback,
        error_callback=error_callback,
        timeout=timeout,
    )


def url_post(
    url: str,
    header: dict | None = None,
    callback: Callable | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    error_callback: Callable | None = None,
    body=None,
):
    """POST 요청 편의 함수. body 는 JSON 으로 직렬화되어 전송된다."""
    return url_request(
        "POST",
        url,
        header=header,
        body=body,
        callback=callback,
        error_callback=error_callback,
        timeout=timeout,
    )


# 사용 예시
# GET_URL = "https://jsonplaceholder.typicode.com/posts/1"
# header_get = {"Content-type": "application/json; charset=UTF-8"}
# url_get(GET_URL, header_get, result_callback)
# POST_URL = "https://jsonplaceholder.typicode.com/posts"
# body_post = {"title": "foo", "body": "bar", "userId": 1}
# url_post(POST_URL, body=body_post, callback=result_callback)
