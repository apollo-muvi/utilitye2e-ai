import asyncio
import os
import time

import pytest

from application.workflows import discover_page
from core.auth import login_page
from core.runner import Runner
from core.spec import TargetSpec, TestSpec as SpecModel, TestStep as StepModel
from core.waiting import wait_for_ui_settle


def _classhub_env():
    if os.getenv("TUTORBOT_CLASSHUB_E2E") != "1":
        pytest.skip(
            "set TUTORBOT_CLASSHUB_E2E=1 to run local ClassHub integration tests"
        )

    url = os.getenv("TUTORBOT_CLASSHUB_URL", "http://127.0.0.1:3002")
    tenant_id = os.getenv("TUTORBOT_CLASSHUB_TENANT_ID", "")
    password = os.getenv("TUTORBOT_CLASSHUB_PASSWORD", "")
    if not tenant_id or not password:
        pytest.skip("set TUTORBOT_CLASSHUB_TENANT_ID and TUTORBOT_CLASSHUB_PASSWORD")
    return url, tenant_id, password


def test_classhub_discover_works_against_inline_spa_login():
    url, tenant_id, password = _classhub_env()

    result = discover_page(url, username=tenant_id, password=password)

    labels = {element["label"] for element in result.elements}
    assert "發布" in labels
    assert "新增" in labels
    assert any(
        element.get("frame_url", "").startswith(url) for element in result.elements
    )


def test_classhub_core_auth_supports_inline_spa_login():
    url, tenant_id, password = _classhub_env()

    async def run():
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 900},
                locale="zh-TW",
            )
            page = await context.new_page()
            try:
                logged_in = await login_page(
                    page,
                    TargetSpec(url=url, username=tenant_id, password=password),
                )
                assert logged_in is True
                await page.wait_for_timeout(1000)
                session_json = await page.evaluate(
                    """(tenantId) => localStorage.getItem(`classhubTeacherSession:${tenantId}`)""",
                    tenant_id,
                )
                assert session_json
            finally:
                await browser.close()

    asyncio.run(run())


def test_classhub_runner_can_login_and_exercise_spa_tab():
    url, tenant_id, password = _classhub_env()
    spec = SpecModel(
        name="ClassHub inline login smoke",
        target=TargetSpec(url=url, username=tenant_id, password=password),
        steps=[StepModel(button="家長", desc="Switch to parent workspace")],
    )

    runner = Runner(
        spec,
        headless=True,
        screenshot_dir="/tmp/utilitye2e-classhub-screenshots",
    )
    summary = asyncio.run(runner.run())

    assert summary["failed"] == 0
    assert summary["passed"] >= 1


def test_classhub_publish_flow_survives_spa_settle_waits():
    url, tenant_id, password = _classhub_env()
    unique = str(int(time.time() * 1000))

    async def run():
        from playwright.async_api import async_playwright

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"],
            )
            context = await browser.new_context(
                viewport={"width": 1280, "height": 1000},
                locale="zh-TW",
            )
            page = await context.new_page()
            try:
                assert await login_page(
                    page,
                    TargetSpec(url=url, username=tenant_id, password=password),
                )
                await wait_for_ui_settle(page)

                class_name = f"E2E班級{unique}"
                await page.get_by_placeholder("班級名稱").fill(class_name)
                await page.get_by_role("button", name="新增", exact=True).click()
                await wait_for_ui_settle(page)
                await page.get_by_text(f"班級已建立：{class_name}").wait_for(
                    state="visible", timeout=5000
                )

                student_name = f"E2E學生{unique}"
                parent_name = f"E2E家長{unique}"
                await page.get_by_placeholder("新學生姓名").fill(student_name)
                await page.get_by_placeholder("家長姓名").fill(parent_name)
                await page.get_by_placeholder("家長電話(option)").fill("0900000000")
                await page.get_by_role(
                    "button", name="建立家長並產生邀請碼", exact=True
                ).click()
                await wait_for_ui_settle(page)
                await page.get_by_text("家長已連結，邀請碼已產生").wait_for(
                    state="visible", timeout=5000
                )

                title = f"E2E聯絡簿{unique}"
                await page.get_by_placeholder("標題").fill(title)
                await page.get_by_placeholder("訊息內容").fill(
                    "ClassHub SPA settle smoke"
                )
                await page.get_by_role("button", name="發布", exact=True).click()
                await wait_for_ui_settle(page, timeout_ms=5000)
                await page.get_by_text("已發布給").wait_for(
                    state="visible", timeout=5000
                )
                await page.get_by_text(title).wait_for(state="visible", timeout=5000)
            finally:
                await browser.close()

    asyncio.run(run())
