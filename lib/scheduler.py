import atexit
import concurrent.futures
import time

from mojo import context

# ---------------------------------------------------------------------------- #
VERSION = "2025.09.27"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class Scheduler:
    def __init__(self, max_workers=4, name="Scheduler"):
        self.name = name
        self.max_workers = max_workers
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
        self.scheduled_tasks = []
        self.task_executor = concurrent.futures.ThreadPoolExecutor()
        atexit.register(self.shutdown)

    def set_interval(self, func, interval):
        try:

            def wrapper():
                while True:
                    time.sleep(interval)
                    self.task_executor.submit(func)

            future = self.executor.submit(wrapper)
            self.scheduled_tasks.append(future)

        except Exception as e:
            context.log.error(f"{self.name} set_interval() 에러: {e}")
        finally:
            self.clean()

    def set_timeout(self, func, delay):
        try:

            def wrapper():
                time.sleep(delay)
                self.task_executor.submit(func)

            future = self.executor.submit(wrapper)
            self.scheduled_tasks.append(future)
        except Exception as e:
            context.log.error(f"{self.name} set_timeout() 에러: {e}")
        finally:
            self.clean()

    def clean(self):
        try:
            for future in self.scheduled_tasks:
                if future.done():
                    self.scheduled_tasks.remove(future)
        except Exception as e:
            context.log.error(f"{self.name} clean() 에러: {e}")

    def shutdown(self):
        try:
            for task in self.scheduled_tasks:
                task.cancel()
            self.executor.shutdown()
            self.task_executor.shutdown()
        except Exception as e:
            context.log.error(f"{self.name} shutdown() 에러: {e}")


# ---------------------------------------------------------------------------- #
# 사용 예제
# def interval_task():
#     context.log.debug("Interval task executed")
# def timeout_task():
#     context.log.debug("Timeout task executed")
# scheduler = Scheduler()
# scheduler.set_interval(interval_task, 1)  # 1초마다 실행
# scheduler.set_timeout(timeout_task, 5)  # 5초 후에 실행
# # 10초 후에 스케줄러 종료
# time.sleep(10)
# scheduler.shutdown()
# ---------------------------------------------------------------------------- #
