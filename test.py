import threading
import time

from lib.networkmanager import TcpClient

my_tcp_client = TcpClient(name="client", ip="127.0.0.1", port=12345)

my_tcp_client.connect()


def handle_client(*args):
    while True:
        if my_tcp_client.is_connected():
            time.sleep(3)
            my_tcp_client.send("Hello, World!")


def handle_client_response(*args):
    print("Received: ", args[0].arguments["data"].decode())


my_tcp_client.receive.listen(handle_client_response)


client_thread = threading.Thread(
    target=handle_client,
)
client_thread.start()
