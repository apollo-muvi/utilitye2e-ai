from ai.page_crawler import _flatten_frames
from application.workflows import build_selectable_elements
from core.runner import Runner
from core.spec import TestSpec as SpecModel


class FakeFrame:
    def __init__(self, url, name=""):
        self.url = url
        self.name = name


class FakePage:
    def __init__(self, frames):
        self.frames = frames


def test_flatten_frames_preserves_frame_metadata_on_elements():
    result = {
        "frames": [
            {
                "frameUrl": "https://example.test/frame-a",
                "frameName": "content",
                "buttons": [{"text": "新增"}],
                "inputs": [{"name": "title"}],
            }
        ]
    }

    flattened = _flatten_frames(result)

    assert flattened["buttons"] == [
        {
            "text": "新增",
            "frameUrl": "https://example.test/frame-a",
            "frameName": "content",
        }
    ]
    assert flattened["inputs"] == [
        {
            "name": "title",
            "frameUrl": "https://example.test/frame-a",
            "frameName": "content",
        }
    ]


def test_build_selectable_elements_exposes_frame_context():
    dom = {
        "buttons": [
            {
                "text": "新增",
                "frameUrl": "https://example.test/frame-a",
                "frameName": "content",
            }
        ],
        "inputs": [
            {
                "label": "名稱",
                "tag": "input",
                "frameUrl": "https://example.test/frame-a",
                "frameName": "content",
            }
        ],
    }

    assert build_selectable_elements(dom) == [
        {
            "type": "button",
            "label": "新增",
            "text": "新增",
            "frame_url": "https://example.test/frame-a",
            "frame_name": "content",
        },
        {
            "type": "input",
            "label": "名稱",
            "text": "input: 名稱",
            "frame_url": "https://example.test/frame-a",
            "frame_name": "content",
        },
    ]


def test_build_selectable_elements_keeps_same_label_across_frames():
    dom = {
        "buttons": [
            {
                "text": "編輯",
                "frameUrl": "https://example.test/frame-a",
                "frameName": "left",
            },
            {
                "text": "編輯",
                "frameUrl": "https://example.test/frame-b",
                "frameName": "right",
            },
        ]
    }

    elements = build_selectable_elements(dom)

    assert len(elements) == 2
    assert {element["frame_name"] for element in elements} == {"left", "right"}


def test_test_spec_round_trips_frame_context():
    data = {
        "name": "Frame test",
        "target": {"url": "https://example.test"},
        "steps": [
            {
                "button": "新增",
                "frame_url": "https://example.test/frame-a",
                "frame_name": "content",
            }
        ],
    }

    spec = SpecModel.from_dict(data)

    assert spec.to_dict()["steps"][0]["frame_url"] == "https://example.test/frame-a"
    assert spec.to_dict()["steps"][0]["frame_name"] == "content"


def test_runner_candidate_frames_prioritizes_matching_frame():
    frames = [
        FakeFrame("https://example.test/main", ""),
        FakeFrame("https://example.test/frame-a", "content"),
        FakeFrame("https://example.test/frame-b", "menu"),
    ]

    ordered = Runner._candidate_frames(FakePage(frames), frame_url="frame-b")

    assert [frame.url for frame in ordered] == [
        "https://example.test/frame-b",
        "https://example.test/main",
        "https://example.test/frame-a",
    ]


def test_runner_summarize_snapshot_aggregates_all_frames():
    snapshot = [
        {"dom": {"count": 10, "inputs": 1, "btns": "新增", "cells": "Alice"}},
        {"dom": {"count": 20, "inputs": 2, "btns": "編輯", "cells": "Bob"}},
    ]

    assert Runner._summarize_snapshot(snapshot) == {
        "count": 30,
        "inputs": 3,
        "btns": "新增|編輯",
        "cells": "Alice|Bob",
    }
