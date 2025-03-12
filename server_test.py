import threading
import time
from concurrent.futures import ThreadPoolExecutor

from lib.networkmanager import TcpServer

s = TcpServer(23456)
s.start()
print(s.running)
s.receive.listen(lambda *args: print(args[0].arguments["data"].decode()))


def dummy():
    while True:
        print("dummy")
        time.sleep(10)


result = ThreadPoolExecutor().submit(dummy)

# threading.Thread(target=dummy).start()
