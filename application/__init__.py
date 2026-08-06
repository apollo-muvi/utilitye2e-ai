"""Application workflows shared by CLI and web entry points."""

from .workflows import (
    DiscoveryResult,
    RunResult,
    analyze_test_spec,
    build_selectable_elements,
    create_posture_finding_record,
    derive_login_url,
    discover_page,
    list_posture_finding_records,
    promote_posture_finding_record,
    render_posture_pack,
    run_test_spec,
)

__all__ = [
    "DiscoveryResult",
    "RunResult",
    "analyze_test_spec",
    "build_selectable_elements",
    "create_posture_finding_record",
    "derive_login_url",
    "discover_page",
    "list_posture_finding_records",
    "promote_posture_finding_record",
    "render_posture_pack",
    "run_test_spec",
]
