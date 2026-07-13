# 마지막 수정일 : 20260713
"""터치패널 메뉴 내비게이션 모듈.

터치패널 포트 1의 버튼으로 페이지 전환(버튼 1~9 → 페이지 "01"~"09")과
메뉴 팝업 전환(버튼 11~30 → 팝업 "001"~"020")을 처리한다.
선택된 메뉴 버튼의 피드백(채널 점등)도 함께 갱신한다.
터치패널 디자인이 이 페이지/팝업 이름 규칙을 따를 때 사용한다.
"""

from lib.button import add_button
from lib.tp import (
    tp_hide_all_popup,
    tp_set_button_in_range,
    tp_set_page,
    tp_show_popup,
)
from lib.utility import CommonLogger, handle_exception

# ---------------------------------------------------------------------------- #
ui_menu_logger = CommonLogger()
# ---------------------------------------------------------------------------- #


def log_error(message):
    ui_menu_logger.log_error(message)


def log_debug(message):
    ui_menu_logger.log_debug(message)


# ---------------------------------------------------------------------------- #


class UiMenu:
    """터치패널 하나의 메뉴(페이지/팝업) 전환을 담당한다.

    - tp : context.devices 로 얻은 터치패널 장치
    - selected_menu : 현재 선택된 메뉴 팝업 번호 (0 이면 선택 없음)
    - 생성 시 init() 에서 버튼 이벤트를 자동 등록하므로 인스턴스만 만들면 동작한다.
    """

    def __init__(self, tp):
        self.tp = tp
        self.selected_menu = 0
        self.init()

    @handle_exception
    def init(self):
        """메뉴 관련 버튼 이벤트를 터치패널에 등록하고 버튼 피드백을 초기화한다."""
        # 모든 팝업 닫기 버튼 (버튼 번호 100)
        add_button(self.tp, 1, 100, "push", self.hide_all_menu_popup)

        # 페이지 1 ~ 9 전환 버튼 (버튼 번호 1 ~ 9)
        for ndx in range(1, 10):
            add_button(self.tp, 1, ndx, "push", lambda ndx=ndx: self.show_page(ndx))

        # 팝업 1 ~ 20 전환 버튼 (버튼 번호 11 ~ 30)
        for ndx in range(1, 21):
            add_button(self.tp, 1, ndx + 10, "push", lambda ndx=ndx: self.show_menu_popup(ndx))
        self.selected_menu = 0
        self.refresh_menu_popup_button()

    @handle_exception
    def show_page(self, index_page):
        """페이지 전환. 열려 있던 메뉴 팝업을 모두 닫고 "01"~"09" 페이지로 이동한다."""
        # 페이지 인덱스는 정수여야 함
        if not isinstance(index_page, int):
            log_error("show_page() -- index_page must be an integer.")
            raise ValueError
        # 페이지 인덱스는 1 ~ 9 범위 내여야 함
        if not 1 <= index_page <= 9:
            log_error("show_page() -- index_page must be an integer between 1 - 9.")
            raise ValueError
        self.hide_all_menu_popup()
        tp_set_page(self.tp, f"{index_page:02d}")

    @handle_exception
    def show_menu_popup(self, index_popup):
        """메뉴 팝업 표시. selected_menu 를 갱신하고 "001"~"020" 팝업을 띄운 뒤 버튼 피드백 갱신."""
        # 팝업 인덱스는 정수여야 함
        if not isinstance(index_popup, int):
            log_error("show_menu_popup() -- index_popup must be an integer.")
            raise ValueError
        # 팝업 인덱스는 1 ~ 20 범위 내여야 함
        if not 1 <= index_popup <= 20:
            log_error("show_menu_popup() -- index_popup must be an integer between 1 - 20.")
            raise ValueError
        self.selected_menu = index_popup
        self.refresh_menu_popup_button()
        tp_show_popup(self.tp, f"{index_popup:03d}")

    @handle_exception
    def hide_all_menu_popup(self):
        """모든 팝업을 닫고 메뉴 선택 상태를 해제(0)한다."""
        tp_hide_all_popup(self.tp)
        self.selected_menu = 0
        self.refresh_menu_popup_button()

    @handle_exception
    def refresh_menu_popup_button(self):
        """메뉴 버튼 피드백 갱신. selected_menu 가 0 이면 전부 소등된다."""
        # 팝업 버튼 범위(11 ~ 30)에서 선택된 메뉴 버튼만 활성화
        tp_set_button_in_range(self.tp, 1, 11, 20, self.selected_menu)
