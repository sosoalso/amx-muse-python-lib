# ---------------------------------------------------------------------------- #
import concurrent.futures
import threading

from mojo import context


# ---------------------------------------------------------------------------- #
class Scheduler:
    def __init__(self, name=None):
        self.name = name
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.scheduled_tasks = []
        self.task_executor = concurrent.futures.ThreadPoolExecutor()

    def set_interval(self, func, interval):
        try:

            def wrapper():
                while True:
                    threading.Event().wait(interval)
                    self.task_executor.submit(func)

            future = self.executor.submit(wrapper)
            self.scheduled_tasks.append(future)
        except Exception as e:
            context.log.debug(f"Error in set_interval: {e}")

    def set_timeout(self, func, delay):
        try:

            def wrapper():
                threading.Event().wait(delay)
                self.task_executor.submit(func)

            future = self.executor.submit(wrapper)
            self.scheduled_tasks.append(future)
        except Exception as e:
            context.log.debug(f"Error in set_timeout: {e}")

    def shutdown(self):
        try:
            for task in self.scheduled_tasks:
                task.cancel()
            self.executor.shutdown()
            self.task_executor.shutdown()
        except Exception as e:
            context.log.debug(f"Error in shutdown: {e}")


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
