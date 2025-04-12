# ---------------------------------------------------------------------------- #
import json
import urllib.error
import urllib.request


# ---------------------------------------------------------------------------- #
def url_get(url: str, header: dict = None) -> str:
    req = urllib.request.Request(url, headers=header)
    try:
        with urllib.request.urlopen(req) as response:
            return response.read()
    except urllib.error.HTTPError as e:
        print(f"{e.code}")


def url_post(url: str, header: dict = None, body=None) -> str:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=header, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            return response.read()
    except urllib.error.HTTPError as e:
        print(f"{e.code}")


# ---------------------------------------------------------------------------- #
# 사용 예시
# GET_URL = "https://jsonplaceholder.typicode.com/posts/1"
# header_get = {"Content-type": "application/json; charset=UTF-8"}
# result = url_get(GET_URL, header_get)
# print(result)
# POST_URL = "https://jsonplaceholder.typicode.com/posts"
# header_post = {"Content-type": "application/json; charset=UTF-8"}
# body_post = {"title": "foo", "body": "bar", "userId": 1}
# result = url_post(POST_URL, header_post, body_post)
# print(result)
# ---------------------------------------------------------------------------- #
