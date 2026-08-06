import pytest

from ai.page_crawler import (
    _already_at_crawl_entry_after_login,
    _login_for_crawl,
)


@pytest.mark.asyncio
async def test_login_for_crawl_uses_target_url_when_login_url_missing(monkeypatch):
    calls = []

    async def fake_login_page(page, target, tenant_id=""):
        calls.append((page, target, tenant_id))
        return True

    monkeypatch.setattr("core.auth.login_page", fake_login_page)

    page = object()
    logged_in = await _login_for_crawl(
        page,
        url="http://router.test",
        login_url="",
        username="root",
        password="secret",
        tenant_id="",
    )

    assert logged_in is True
    assert calls[0][0] is page
    assert calls[0][1].url == "http://router.test"
    assert calls[0][1].login_url == ""
    assert calls[0][1].username == "root"
    assert calls[0][1].password == "secret"


@pytest.mark.asyncio
async def test_login_for_crawl_skips_without_username(monkeypatch):
    async def fake_login_page(page, target, tenant_id=""):
        raise AssertionError("login_page should not be called")

    monkeypatch.setattr("core.auth.login_page", fake_login_page)

    logged_in = await _login_for_crawl(
        object(),
        url="http://router.test",
        login_url="",
        username="",
        password="secret",
    )

    assert logged_in is False


def test_already_at_crawl_entry_after_inline_login():
    assert _already_at_crawl_entry_after_login(
        logged_in=True,
        login_url="",
        url="http://router.test",
    )


def test_already_at_crawl_entry_after_same_login_url():
    assert _already_at_crawl_entry_after_login(
        logged_in=True,
        login_url="http://app.test/login",
        url="http://app.test/login/",
    )


def test_not_at_crawl_entry_when_login_url_differs():
    assert not _already_at_crawl_entry_after_login(
        logged_in=True,
        login_url="http://app.test/login",
        url="http://app.test/dashboard",
    )
