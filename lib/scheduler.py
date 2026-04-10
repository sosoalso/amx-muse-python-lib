import atexit
import concurrent.futures
import time

from mojo import context

# ---------------------------------------------------------------------------- #
VERSION = "2026.04.10"


def get_version():
    return VERSION


# ---------------------------------------------------------------------------- #
class Scheduler:
    def __init__(self, max_workers=4, name="Scheduler"):
        """
        스케줄러 초기화
        max_workers: 스레드 풀의 최대 워커 스레드 개수
        """
        self.name = name
        self.max_workers = max_workers
        # 주기적/지연 작업의 래퍼를 실행할 스레드 풀
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=self.max_workers)
        # 실제 작업들을 추적하기 위한 Future 객체 리스트
        self.scheduled_tasks = []
        # 사용자가 제공한 실제 함수를 실행할 스레드 풀 (무제한)
        self.task_executor = concurrent.futures.ThreadPoolExecutor()
        # 프로그램 종료 시 자동으로 shutdown() 호출
        atexit.register(self.shutdown)

    def set_interval(self, func, interval):
        """
        주어진 함수를 지정된 시간 간격으로 반복 실행
        interval: 실행 간격(초)
        """
        try:

            def wrapper():
                # 무한 루프에서 지정된 간격으로 함수 실행
                while True:
                    time.sleep(interval)
                    # task_executor에서 비동기로 함수 실행
                    self.task_executor.submit(func)

            future = self.executor.submit(wrapper)
            self.scheduled_tasks.append(future)
        except Exception as e:
            context.log.error(f"{self.name} set_interval() 에러: {e}")
        finally:
            self.clean()

    def set_timeout(self, func, delay):
        """
        주어진 함수를 지정된 시간 후에 한 번 실행
        delay: 지연 시간(초)
        """
        try:

            def wrapper():
                # 지정된 시간 대기 후 함수 실행
                time.sleep(delay)
                # task_executor에서 비동기로 함수 실행
                self.task_executor.submit(func)

            future = self.executor.submit(wrapper)
            self.scheduled_tasks.append(future)
        except Exception as e:
            context.log.error(f"{self.name} set_timeout() 에러: {e}")
        finally:
            self.clean()

    def clean(self):
        """
        완료된 작업들을 scheduled_tasks 리스트에서 제거하여 메모리 관리
        """
        try:
            for future in self.scheduled_tasks:
                # done() 메서드로 작업 완료 여부 확인
                if future.done():
                    self.scheduled_tasks.remove(future)
        except Exception as e:
            context.log.error(f"{self.name} clean() 에러: {e}")

    def shutdown(self):
        """
        모든 스케줄된 작업을 취소하고 스레드 풀 종료
        """
        try:
            # 진행 중인 모든 작업 취소 시도
            for task in self.scheduled_tasks:
                task.cancel()
            # 래퍼 실행 스레드 풀 종료
            self.executor.shutdown()
            # 실제 작업 실행 스레드 풀 종료
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
