import json
import threading
import urllib.error
import urllib.request

from mojo import context

# ---------------------------------------------------------------------------- #
VERSION = "2025.07.04"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
def url_get(url: str, header: dict = {}, callback=None, timeout: float = 0.5):
    context.log.debug(f"url_get() {url=} {header=} {callback=} {timeout=}")

    def task():
        req = urllib.request.Request(url=url, headers=header, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                result = response.read()
                if callback:
                    callback(result)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            context.log.error(f"url_get() 에러 : {e}")

    threading.Thread(target=task, daemon=True).start()


def url_post(url: str, header: dict = {}, body=None, callback=None, timeout: float = 0.5):
    context.log.debug(f"url_post() {url=} {header=} {body=} {callback=} {timeout=}")

    def task():
        data = json.dumps(body).encode() if body else None
        req = urllib.request.Request(url=url, data=data, headers=header, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                result = response.read()
                if callback:
                    callback(result)
        except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
            context.log.error(f"url_post() 에러 : {e}")

    threading.Thread(target=task, daemon=True).start()


# ---------------------------------------------------------------------------- #
# 사용 예시
# GET_URL = "https://jsonplaceholder.typicode.com/posts/1"
# header_get = {"Content-type": "application/json; charset=UTF-8"}
# url_get(GET_URL, header_get, result_callback)
# POST_URL = "https://jsonplaceholder.typicode.com/posts"
# header_post = {"Content-type": "application/json; charset=UTF-8"}
# body_post = {"title": "foo", "body": "bar", "userId": 1}
# url_post(POST_URL, header_post, body_post, result_callback)
# ---------------------------------------------------------------------------- #
