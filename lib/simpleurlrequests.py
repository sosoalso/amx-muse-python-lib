# 마지막 수정일 : 20260505
import json
import threading
import urllib.error
import urllib.request


class SimpleUrlRequestsDebugFlag:
    debug = False


def simple_url_requests_log_error(message):
    print(f"simpleurlrequests (ERROR) -- {message}")


def simple_url_requests_log_debug(message):
    if SimpleUrlRequestsDebugFlag.debug:
        print(f"simpleurlrequests (DEBUG) -- {message}")


def url_get(url: str, header: dict, callback=None, timeout: float = 0.5):
    # 데몬 스레드로 비동기 GET 요청 실행
    _thread_url_get: threading.Thread
    simple_url_requests_log_debug(f"url_get() {url=} {header=} {callback=} {timeout=}")

    def task():
        req = urllib.request.Request(url=url, headers=header, method="GET")
        try:
            # URL 연결 후 응답 데이터 수신
            with urllib.request.urlopen(req, timeout=timeout) as response:
                result = response.read()
                # 응답 처리 콜백 실행
                if callback:
                    callback(result)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            simple_url_requests_log_error(f"url_get() {e=}")

    # 백그라운드에서 실행되는 스레드 생성 및 시작
    _thread_url_get = threading.Thread(target=task, daemon=True)
    _thread_url_get.start()


def url_post(url: str, header: dict, body=None, callback=None, timeout: float = 0.5):
    # 데몬 스레드로 비동기 POST 요청 실행
    _thread_url_post: threading.Thread
    simple_url_requests_log_debug(f"url_post() {url=} {header=} {body=} {callback=} {timeout=}")

    def task():
        # body를 JSON 문자열로 인코딩하여 바이트로 변환
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url=url, data=data, headers=header, method="POST")
        try:
            # URL 연결 후 응답 데이터 수신
            with urllib.request.urlopen(req, timeout=timeout) as response:
                result = response.read()
                # 응답 처리 콜백 실행
                if callback:
                    callback(result)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            simple_url_requests_log_error(f"url_post() {e=}")

    # 백그라운드에서 실행되는 스레드 생성 및 시작
    _thread_url_post = threading.Thread(target=task, daemon=True)
    _thread_url_post.start()


# 사용 예시
# GET_URL = "https://jsonplaceholder.typicode.com/posts/1"
# header_get = {"Content-type": "application/json; charset=UTF-8"}
# url_get(GET_URL, header_get, result_callback)
# POST_URL = "https://jsonplaceholder.typicode.com/posts"
# header_post = {"Content-type": "application/json; charset=UTF-8"}
# body_post = {"title": "foo", "body": "bar", "userId": 1}
# url_post(POST_URL, header_post, body_post, result_callback)
