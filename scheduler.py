# ---------------------------------------------------------------------------- #
import concurrent.futures
import time


# ---------------------------------------------------------------------------- #
def simple_exception_handler(*exceptions):
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                print(f"Exception occurred in {func.__name__}: {e}")
                return None
            except Exception as e:
                print(f"Exception occurred in {func.__name__}: {e}")
                return None

        return wrapper

    return decorator


# ---------------------------------------------------------------------------- #
class Scheduler:
    def __init__(self, name=None):
        self.name = name
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.scheduled_tasks = []

    @simple_exception_handler
    def set_interval(self, func, interval):
        def wrapper():
            while True:
                time.sleep(interval)
                func()

        future = self.executor.submit(wrapper)
        self.scheduled_tasks.append(future)

    @simple_exception_handler
    def set_timeout(self, func, delay):
        def wrapper():
            time.sleep(delay)
            func()

        future = self.executor.submit(wrapper)
        self.scheduled_tasks.append(future)

    @simple_exception_handler
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
