# 마지막 수정일 : 20260514
import json
import urllib.error
import urllib.request
from typing import Callable

from lib.utility import start_thread

DEFAULT_TIMEOUT = 1.0
DEFAULT_JSON_HEADER = {"Content-Type": "application/json; charset=UTF-8"}


class SimpleUrlRequestsDebugFlag:
    debug = False


def simple_url_requests_log_error(message):
    print(f"(ERROR) - simpleurlrequests : {message}")


def simple_url_requests_log_debug(message):
    if SimpleUrlRequestsDebugFlag.debug:
        print(f"(DEBUG) - simpleurlrequests : {message}")


def _run_callback(callback: Callable | None, *args):
    if not callback:
        return
    try:
        callback(*args)
    except Exception as e:
        simple_url_requests_log_error(f"callback failed {e=}")


def _make_headers(header: dict | None = None, json_body=False):
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
    method = method.upper()
    simple_url_requests_log_debug(f"url_request() {method=} {url=} {header=} {body=} {callback=} {timeout=}")

    def task():
        data = None
        json_body = method in ("POST", "PUT", "PATCH") and body is not None
        if json_body:
            data = json.dumps(body).encode()

        req = urllib.request.Request(
            url=url,
            data=data,
            headers=_make_headers(header, json_body=json_body),
            method=method,
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                _run_callback(callback, response.read())
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
            simple_url_requests_log_error(f"url_request() {method=} {url=} {e=}")
            _run_callback(error_callback, e)

    return start_thread(task)


def url_get(
    url: str,
    header: dict | None = None,
    callback: Callable | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    error_callback: Callable | None = None,
):
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
    body=None,
    callback: Callable | None = None,
    timeout: float = DEFAULT_TIMEOUT,
    error_callback: Callable | None = None,
):
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
