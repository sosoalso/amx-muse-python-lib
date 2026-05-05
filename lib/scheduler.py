# 마지막 수정일 : 20260505
import atexit
import threading
from lib.utility import CommonLogger


class Scheduler(CommonLogger):
    """
    멀티스레드 기반의 작업 스케줄러
    set_interval, set_timeout 등으로 작업을 예약하고 관리
    주요 특징:
    - 반복 실행(set_interval)과 지연 실행(set_timeout) 지원
    - 중첩된 스케줄(자식 스케줄) 관리 기능
    - 스레드 안전성을 위한 RLock 사용
    - 프로그램 종료 시 자동 정리
    """

    def __init__(self, name="Scheduler"):
        """
        스케줄러 초기화
        Args:
            name (str): 스케줄러 이름 (로그 출력용)
        Attributes:
            name: 스케줄러 이름
            schedules: 현재 실행 중인 모든 스케줄 리스트
            _lock: 스레드 안전성을 위한 재진입 가능 뮤텍스
            _local: 스레드 로컬 저장소 (현재 실행 중인 스케줄 추적용)
        """
        self.name = name
        # 최상위 레벨 스케줄만 저장 (자식은 부모의 children에 저장)
        self.schedules = []
        # 동시성 제어용 재진입 가능 뮤텍스
        self._lock = threading.RLock()
        # 스레드별 독립적인 current_schedule 추적
        self._local = threading.local()
        # 프로그램 종료 시 자동으로 shutdown() 호출
        atexit.register(self.shutdown)

    def _get_current_schedule(self):
        return getattr(self._local, "current_schedule", None)

    def _set_current_schedule(self, schedule):
        self._local.current_schedule = schedule

    def _run_schedule_in_context(self, schedule, func):
        """
        주어진 스케줄 컨텍스트 내에서 함수 실행
        스레드 로컬 저장소를 이용하여 현재 실행 중인 스케줄을 추적
        동작 구조:
        1. 이전 스케줄 컨텍스트 저장 (중첩된 호출 시 복원용)
        2. 현재 스케줄 컨텍스트 설정
        3. 제공된 함수 실행
        4. 예외 발생 여부와 관계없이 이전 컨텍스트 복원 (finally 블록)
        이를 통해 자식 스케줄이 생성될 때 부모-자식 관계를 올바르게 추적 가능
        """
        # 현재 스레드의 이전 스케줄 컨텍스트 조회
        previous_schedule = self._get_current_schedule()
        # 현재 스레드의 스케줄 컨텍스트를 새로운 스케줄로 설정
        self._set_current_schedule(schedule)
        try:
            # 함수 실행 (이 함수 내에서 생성된 자식 스케줄은 schedule을 parent로 갖게됨)
            func()
        finally:
            # 예외 발생 여부와 관계없이 이전 컨텍스트로 복원
            # (중첩된 스케줄 콜의 경우 올바른 스택 구조 유지)
            self._set_current_schedule(previous_schedule)

    def _create(self, kind, stop_evt):
        """
        새로운 스케줄 객체 생성 및 계층 구조 설정
        동작 구조:
        1. 현재 스레드 로컬 컨텍스트에서 부모 스케줄 조회
        2. 스케줄 딕셔너리 초기화 (종류, 스레드, 정지 신호, 부모-자식 관계 등)
        3. 스케줄 종료 함수(stop) 정의 및 등록
        4. 뮤텍스 보호 하에서 스케줄을 전역 리스트에 추가
        5. 부모 스케줄이 존재하면 부모의 자식 목록에 현재 스케줄 등록
        이를 통해 새로운 스케줄이 생성 시점의 컨텍스트 기반으로 부모-자식 관계 형성
        """
        # 현재 스레드의 스케줄 컨텍스트에서 부모 스케줄 조회
        parent = self._get_current_schedule()
        # 새로운 스케줄 딕셔너리 생성
        # - kind: 스케줄의 종류 (periodic, once 등)
        # - thread: 이 스케줄을 실행할 워커 스레드 (초기값 None)
        # - stop_event: 스케줄 종료 신호를 전달할 이벤트 객체
        # - stop: 스케줄 종료 함수 (후에 등록됨)
        # - parent: 부모 스케줄 (현재 컨텍스트에서 획득)
        # - children: 자식 스케줄 목록
        # - done: 스케줄 완료 여부 플래그
        schedule = {"kind": kind, "thread": None, "stop_event": stop_evt, "stop": None, "parent": parent, "children": [], "done": False}

        def stop(stop_children=True):
            # 스케줄 종료 함수 정의 (클로저로 현재 schedule 참조)  이 스케줄과 필요시 자식 스케줄까지 종료
            self._stop(schedule, stop_children=stop_children)

        # 스케줄 객체에 종료 함수 등록
        schedule["stop"] = stop
        # 뮤텍스 획득하여 스레드 안전성 보장
        with self._lock:
            # 생성된 스케줄을 전역 스케줄 리스트에 추가
            self.schedules.append(schedule)
            if parent is not None:
                # (부모-자식 계층 구조 형성)
                # 부모 스케줄이 존재하면 부모의 자식 목록에 현재 스케줄 등록
                parent["children"].append(schedule)
        # 생성된 스케줄 객체 반환
        return schedule

    def _stop(self, schedule, stop_children=True):
        """
        스케줄 종료 및 자식 스케줄 처리
        동작 구조:
        1. 입력으로 받은 스케줄이 None이거나 유효하지 않으면 즉시 반환
        2. stop_event를 설정하여 해당 스케줄의 워커 스레드에 종료 신호 전송
        3. stop_children이 True이면 현재 스케줄의 모든 자식 스케줄 목록을 복사
           (락을 짧게 유지하기 위해 리스트 복사 수행)
        4. 각 자식 스케줄에 대해 _stop()을 재귀적으로 호출하여 중첩된 자식까지 모두 종료
        이를 통해 계층 구조상 종료되는 스케줄 아래의 모든 자식이 안전하게 정리됨
        """
        if not schedule:
            # 유효하지 않은 스케줄은 처리하지 않고 반환
            return
        # 자식 스케줄 목록 (락을 해제한 후 재귀 호출에서 사용)
        children = []
        # 스레드 안전성을 보장하기 위해 뮤텍스 획득
        with self._lock:
            # 현재 스케줄의 워커 스레드에 정지 신호 전송
            schedule["stop_event"].set()
            if stop_children:
                # stop_children이 True이면 현재 스케줄의 자식 목록을 복사
                # (보유 중인 락에서 자식 리스트의 얕은 복사본 생성)
                children = list(schedule["children"])
        # 재귀가 안에 있으면 이중 락 안돼서 바깥에서 처리
        # (깊이 우선 탐색으로 모든 하위 스케줄을 정지)
        for child in children:
            self._stop(child, stop_children=True)
            # 락을 해제한 후 각 자식 스케줄을 재귀적으로 정지

    def _finalize(self, schedule):
        """
        스케줄 정리 및 부모-자식 관계 제거
        동작 구조:
        1. 스케줄을 완료(done=True)로 표시
        2. 아직 실행 중인 자식 스케줄이 있으면 함수 종료 (부모는 모든 자식이 끝날 때까지 유지)
        3. 현재 스케줄이 최상위 레벨이면 schedules 리스트에서 제거
        4. 부모가 있으면 부모의 children 리스트에서 현재 스케줄 제거
        5. 부모도 완료 상태이고 자식이 모두 없으면 부모를 재귀적으로 정리
        이를 통해 부모-자식 계층 구조가 안전하게 해제되고 필요 없는 스케줄만 제거됨
        """
        parent_to_check = None
        with self._lock:
            # 스케줄을 완료 상태로 표시
            schedule["done"] = True
            if schedule["children"]:
                # 아직 실행 중인 자식 스케줄이 있으면 부모는 유지하고 함수 종료
                return
            if schedule in self.schedules:
                # 현재 스케줄이 최상위 레벨 스케줄 리스트에 있으면 제거
                self.schedules.remove(schedule)
            # 부모 스케줄 조회
            parent = schedule.get("parent")
            if parent is not None and schedule in parent["children"]:
                # 부모가 있으면 부모의 자식 목록에서 현재 스케줄 제거
                parent["children"].remove(schedule)
                # 부모 정리 필요 여부를 확인하기 위해 부모를 저장
                parent_to_check = parent
        if parent_to_check is not None and parent_to_check.get("done"):
            # 잠금 해제 후, 부모도 정리 조건을 만족하면 재귀적으로 정리
            self._finalize(parent_to_check)

    def cancel(self, schedule, stop_children=True):
        """
        특정 스케줄만 종료
        stop_children=True 이면 자식 스케줄도 함께 종료
        """
        try:
            self._stop(schedule, stop_children=stop_children)
        except Exception as e:
            self.log_error(f"cancel() {e=}")

    def set_interval(self, func, interval):
        """
        주어진 함수를 지정된 시간 간격으로 반복 실행
        interval: 실행 간격(초)
        """
        try:
            self.log_debug(f"set_interval() interval={interval}")
            stop_event = threading.Event()
            # 스케줄 중단 신호를 전달할 Event 객체 생성
            schedule = self._create("interval", stop_event)

            # 새로운 "interval" 타입의 스케줄 생성 및 stop_event 등록
            def wrapper():
                try:
                    # stop_event가 발생할 때까지 interval 초마다 반복 실행
                    # stop_event.wait(interval)는 interval초 대기 후 신호 확인
                    # 신호 미발생 시 False 반환하여 while 루프 계속 실행
                    while not stop_event.wait(interval):
                        try:
                            # 스케줄 컨텍스트 내에서 사용자 함수 실행
                            self._run_schedule_in_context(schedule, func)
                        except Exception as e:
                            self.log_error(f"set_interval() func error {e=}")
                finally:
                    # 반복 종료 후 스케줄 정리 (부모-자식 관계 처리, 리스트에서 제거 등)
                    self._finalize(schedule)

            # wrapper 함수를 데몬 스레드로 백그라운드 실행 - 데몬 스레드는 메인 프로그램 종료 시 자동 종료됨
            thread = threading.Thread(target=wrapper, daemon=True)
            # 생성된 스레드 객체를 스케줄에 저장 (나중에 중단 시 참조 가능)
            schedule["thread"] = thread
            # 스레드 실행 시작
            thread.start()
            # 스케줄 객체 반환 (호출자가 언제든 cancel() 메서드로 중단 가능)
            return schedule
        except Exception as e:
            self.log_error(f"set_interval() {e=}")
            return None

    def set_timeout(self, func, delay):
        """
        주어진 함수를 지정된 시간 후에 한 번 실행
        delay: 지연 시간(초)
        """
        try:
            self.log_debug(f"set_timeout() {delay=}")
            # 타임아웃 작업을 외부에서 중단하기 위한 신호 객체
            stop_event = threading.Event()
            # 작업 메타데이터 딕셔너리 생성 (type="timeout", stop_event 저장)
            schedule = self._create("timeout", stop_event)

            def wrapper():
                # 래퍼 함수: 데몬 스레드에서 실행될 실제 동작 정의
                try:
                    # stop_event.wait(delay)는 delay초 대기 후 신호 확인
                    # 신호 발생 시(cancel 호출) True 반환하여 return으로 종료
                    # 신호 미발생 시 False 반환하여 사용자 함수 실행
                    if stop_event.wait(delay):
                        # cancel() 호출로 중단 신호 받으면 여기서 조기 종료
                        return
                    try:
                        # delay초 경과 후 스케줄 컨텍스트 내에서 사용자 함수 한 번 실행
                        self._run_schedule_in_context(schedule, func)
                    except Exception as e:
                        self.log_error(f"set_timeout() {e=}")
                finally:
                    # 함수 실행 완료 또는 에러 발생 후 반드시 스케줄 정리 (부모-자식 관계 처리, 리스트 제거 등)
                    self._finalize(schedule)

            # 래퍼 함수를 데몬 스레드로 백그라운드 실행 (메인 프로그램 종료 시 자동 종료됨)
            thread = threading.Thread(target=wrapper, daemon=True)
            # 생성된 스레드 객체를 스케줄에 저장 (나중에 cancel() 메서드로 중단 시 참조 가능)
            schedule["thread"] = thread
            # 스레드 실행 시작 - delay초 후 func 함수가 한 번 실행됨
            thread.start()
            # 스케줄 객체 반환 (호출자가 언제든 cancel() 메서드로 중단 가능)
            return schedule
        except Exception as e:
            self.log_error(f"set_timeout() {e=}")
            return None

    def shutdown(self):
        """
        모든 스케줄된 작업 종료
        """
        try:
            self.log_debug("shutdown()")
            # 스레드 안전성을 위해 락을 획득하고 현재 모든 스케줄 목록을 복사
            with self._lock:
                # (반복 중에 schedules 리스트가 수정되는 것을 방지하기 위해 list()로 복사)
                schedules = list(self.schedules)
                # 복사된 모든 스케줄에 대해 순회하면서 각 스케줄 종료
            for schedule in schedules:
                # _stop() 호출 시 stop_children=True로 설정하여 해당 스케줄뿐만 아니라 그 하위의 모든 자식 스케줄도 함께 종료
                self._stop(schedule, stop_children=True)
        except Exception as e:
            self.log_error(f"{self.name} shutdown() {e=}")


# 사용 예제
# def interval_task():
#     print("Interval task executed")
# def timeout_task():
#     print("Timeout task executed")
# scheduler = Scheduler(name="MyScheduler")
# # 1초마다 실행
# scheduler.set_interval(interval_task, 1)
# # 5초 후에 실행
# scheduler.set_timeout(timeout_task, 5)
# scheduler.shutdown()
