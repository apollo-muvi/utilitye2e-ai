import json

import pytest

from core.waiting import (
    collect_settle_state,
    summarize_settle_state,
    wait_for_ui_settle,
)


class FakeFrame:
    def __init__(self, url, states):
        self.url = url
        self._states = list(states)

    async def evaluate(self, script, arg=None):
        state = (
            self._states.pop(0)
            if self._states
            else {"elements": 1, "text_length": 1, "pending": 0}
        )
        return json.dumps(state)


class FakePage:
    def __init__(self, frame_states):
        self.frames = [FakeFrame(url, states) for url, states in frame_states]
        self.waits = []

    async def wait_for_load_state(self, state, timeout=None):
        self.waits.append(("load_state", state, timeout))

    async def wait_for_timeout(self, timeout):
        self.waits.append(("timeout", timeout))


def test_summarize_settle_state_aggregates_frames():
    assert summarize_settle_state(
        [
            {"elements": 3, "text_length": 10, "pending": 1},
            {"elements": 7, "text_length": 15, "pending": 0},
        ]
    ) == {"elements": 10, "text_length": 25, "pending": 1}


@pytest.mark.asyncio
async def test_collect_settle_state_skips_blank_frames():
    page = FakePage(
        [
            ("about:blank", [{"elements": 100, "text_length": 100, "pending": 5}]),
            ("https://example.test", [{"elements": 2, "text_length": 8, "pending": 0}]),
        ]
    )

    assert await collect_settle_state(page) == [
        {"elements": 2, "text_length": 8, "pending": 0}
    ]


@pytest.mark.asyncio
async def test_wait_for_ui_settle_waits_for_stable_non_pending_state():
    page = FakePage(
        [
            (
                "https://example.test",
                [
                    {"elements": 1, "text_length": 5, "pending": 1},
                    {"elements": 2, "text_length": 8, "pending": 0},
                    {"elements": 2, "text_length": 8, "pending": 0},
                    {"elements": 2, "text_length": 8, "pending": 0},
                ],
            )
        ]
    )

    summary = await wait_for_ui_settle(
        page,
        timeout_ms=1000,
        poll_ms=1,
        stable_polls=2,
    )

    assert summary == {"elements": 2, "text_length": 8, "pending": 0}
    assert ("load_state", "networkidle", 1000) in page.waits
