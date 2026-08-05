from core.auth import resolve_login_url
from core.spec import TargetSpec


def test_resolve_login_url_returns_absolute_login_url():
    target = TargetSpec(
        url="https://example.test/app", login_url="https://auth.test/login"
    )

    assert resolve_login_url(target) == "https://auth.test/login"


def test_resolve_login_url_expands_relative_login_url():
    target = TargetSpec(url="https://example.test/app/", login_url="/login")

    assert resolve_login_url(target) == "https://example.test/app/login"


def test_resolve_login_url_returns_empty_without_login_url():
    target = TargetSpec(url="https://example.test/app")

    assert resolve_login_url(target) == ""
