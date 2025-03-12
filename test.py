import threading
import time

from lib.networkmanager import TcpServer

my_server = TcpServer(port=12345)


def handle_receive(*args):
    data = args[0].arguments["data"].decode()
    print(f"handle_receive {data}")


my_server.receive.listen(handle_receive)
my_server.connect(lambda a, b: print("connected"))
my_server.disconnect(lambda: print("disconnected"))
my_server.start()


def dummy():
    while True:
        print("dummy")
        my_server.send_clients("hello".encode())
        time.sleep(5)


threading.Thread(
    target=dummy,
).start()
