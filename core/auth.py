"""Shared browser authentication helpers."""

from core.spec import TargetSpec


def resolve_login_url(target: TargetSpec) -> str:
    """Resolve a target login URL while preserving relative URL compatibility."""
    if not target.login_url:
        return ""
    if target.login_url.startswith("http"):
        return target.login_url
    return f"{target.url.rstrip('/')}/{target.login_url.lstrip('/')}"


async def login_page(page, target: TargetSpec, tenant_id: str = "") -> bool:
    """Authenticate a Playwright page using the project's canonical login flow."""
    login_url = resolve_login_url(target)
    if not login_url or not target.username:
        return False

    # Compatibility bridge: the robust login implementation currently lives with
    # the crawler. Keep all callers behind this public helper while the browser
    # automation package boundary is extracted.
    from ai.page_crawler import _try_login

    print(f"  → Login: {login_url}")
    return await _try_login(
        page, login_url, target.username, target.password, tenant_id
    )
