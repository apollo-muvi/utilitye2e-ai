"""Application workflows shared by CLI and web entry points."""

from .workflows import (
    DiscoveryResult,
    RunResult,
    analyze_test_spec,
    build_selectable_elements,
    derive_login_url,
    discover_page,
    run_test_spec,
)

__all__ = [
    "DiscoveryResult",
    "RunResult",
    "analyze_test_spec",
    "build_selectable_elements",
    "derive_login_url",
    "discover_page",
    "run_test_spec",
]
