import threading
import time

from lib.networkmanager import TcpClient

tcp_client = TcpClient(name="test", ip="127.0.0.1", port=12345)


def on_receive(evt):
    print(f"on_receive {evt}")
    print("Received:", evt.arguments["data"].decode("utf-8"))


tcp_client.receive.listen(on_receive)
tcp_client.connect()


def sleep_me():
    while True:
        time.sleep(2)
        tcp_client.send("Hello, World!")


threading.Thread(target=sleep_me).start()

while True:
    time.sleep(2)
    print("working...")
