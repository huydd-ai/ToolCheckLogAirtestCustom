from pixon.common.wrappers import log_info

from airtest.core.api import *

from pixon.common import wrappers as wrapper
from pixon.pages.home_page import HomePage
from pixon.pages.magic_bean_page import MagicBeanPage
from pixon.common.test_flow import run_step, go_home_clean, close_all_popups, teardown_app
from pixon.common.adb_utils import (
    cold_start_with_combined,
    set_param,
    wait_for_app_ready,
)


home_page = HomePage()
magic_bean = MagicBeanPage()

UNLOCK_LEVEL = MagicBeanPage.MAGICBEAN_UNLOCK_LEVEL
# Boundary matrix: threshold is fixed at MAGICBEAN_UNLOCK_LEVEL regardless of
# remote-config changes (Excel note: "du thay doi cau hinh, nguong 33 luon ap dung").
BOUNDARY_LEVELS = [UNLOCK_LEVEL - 1, UNLOCK_LEVEL, UNLOCK_LEVEL + 1]


def check_level(level: int) -> None:
    log_info(f"Start: boundary check at level {level}")

    run_step(
        f"cold start at level {level}",
        cold_start_with_combined,
        level=level,
        **MagicBeanPage.DEFAULT_PROFILE,
    )
    sleep(15)
    wait_for_app_ready()
    for _ in range(15):
        try:
            if home_page.is_at_home():
                break
        except Exception:
            pass
        sleep(2)
    run_step("Go back homepage", go_home_clean, home_page)
    run_step(
        "verify unlock flow if storm auto-shown", magic_bean.verify_unlock_flow, home_page
    )

    # lv32 (threshold-1) is a 2-phase level that auto-chains in-level -- both
    # phases must be won to complete it (same as tc01). Other levels win once.
    phases = 2 if level == UNLOCK_LEVEL - 1 else 1
    run_step("enter level by clicking play", home_page.click_play)
    for phase in range(phases):
        sleep(3)
        run_step(f"win level phase {phase + 1}/{phases}", set_param, "set_level_win", True)
        sleep(2)
    run_step("tap next to back home", home_page.click_btn_next)
    sleep(1)
    run_step("Go back homepage", go_home_clean, home_page)
    run_step(
        "verify unlock flow (tutorial -> board -> popups -> icon)",
        magic_bean.verify_unlock_flow,
        home_page,
    )

    popup_visible = magic_bean.wait_for_element(magic_bean.popup_start_event, timeout=5)
    icon_visible = magic_bean.is_event_icon_visible(timeout=5)
    event_opened = popup_visible or icon_visible

    if level < UNLOCK_LEVEL:
        if event_opened:
            raise AssertionError(
                f"Result: Expected: event locked below threshold (lv{level}) | "
                f"Actual: event opened (popup={bool(popup_visible)}, icon={bool(icon_visible)})"
            )
        log_info(
            f"Result: Expected: event locked below threshold (lv{level}) | Actual: event locked"
        )
    else:
        if not event_opened:
            raise AssertionError(
                f"Result: Expected: event unlocked at/above threshold (lv{level}) | "
                f"Actual: event still locked"
            )
        log_info(
            f"Result: Expected: event unlocked at/above threshold (lv{level}) | Actual: event unlocked"
        )

    log_info(f"End: boundary check at level {level}")


def main():
    # TC03 -- Boundary-value test across MAGICBEAN_UNLOCK_LEVEL - 1, exactly
    # at, and + 1: only lv < threshold stays locked, threshold and above unlock.

    try:
        log_info(f"Start: tc03_unlock_threshold_boundary (levels {BOUNDARY_LEVELS})")

        for level in BOUNDARY_LEVELS:
            check_level(level)
            sleep(2)

        sleep(5)
        log_info("End: tc03_unlock_threshold_boundary")
    except Exception as e:
        wrapper.log_error(f"TC03_error: {str(e)}")
        snapshot(filename="tc03_error.png")
    finally:
        teardown_app()


if __name__ == "__main__":
    main()
