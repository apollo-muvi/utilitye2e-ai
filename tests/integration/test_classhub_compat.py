import asyncio
import os

import pytest

from application.workflows import discover_page
from core.auth import login_page
from core.runner import Runner
from core.spec import TargetSpec, TestSpec as SpecModel, TestStep as StepModel


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
