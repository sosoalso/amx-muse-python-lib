# ---------------------------------------------------------------------------- #
import concurrent.futures
import threading
import time


# ---------------------------------------------------------------------------- #
def handle_exception(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            print(f"Exception occurred in {func.__name__}: {e}")
            return None

    return wrapper


# ---------------------------------------------------------------------------- #
class Scheduler:
    def __init__(self, name=None):
        self.name = name
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.scheduled_tasks = []

    @handle_exception
    def set_interval(self, func, interval):
        def wrapper():
            while True:
                # time.sleep(interval)
                threading.Event().wait(interval)
                func()

        future = self.executor.submit(wrapper)
        self.scheduled_tasks.append(future)

    @handle_exception
    def set_timeout(self, func, delay):
        def wrapper():
            threading.Event().wait(delay)
            # time.sleep(delay)
            func()

        future = self.executor.submit(wrapper)
        self.scheduled_tasks.append(future)

    @handle_exception
    def shutdown(self):
        for task in self.scheduled_tasks:
            task.cancel()
        self.executor.shutdown()


# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #
# ---------------------------------------------------------------------------- #

# # 사용 예제
# def interval_task():
#     print("Interval task executed")


# def timeout_task():
#     print("Timeout task executed")


# scheduler = Scheduler()
# scheduler.set_interval(interval_task, 1)  # 1초마다 실행
# scheduler.set_timeout(timeout_task, 5)  # 5초 후에 실행

# # 10초 후에 스케줄러 종료
# time.sleep(10)
# scheduler.shutdown()
