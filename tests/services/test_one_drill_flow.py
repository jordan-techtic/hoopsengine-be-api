"""Unit tests for One Drill flow state helpers."""

from __future__ import annotations

from app.services.one_drill_flow import ONE_DRILL_FLOW_KEY, _merge_flow_details


def test_merge_flow_details_preserves_existing_keys() -> None:
    existing = {
        ONE_DRILL_FLOW_KEY: {
            "step": 2,
            "selected_player_id": "11111111-2222-3333-4444-555555555555",
        }
    }
    merged = _merge_flow_details(existing, {"step": 3, "selected_drill_id": "22222222-2222-3333-4444-555555555555"})
    flow = merged[ONE_DRILL_FLOW_KEY]
    assert flow["step"] == 3
    assert flow["selected_player_id"] == "11111111-2222-3333-4444-555555555555"
    assert flow["selected_drill_id"] == "22222222-2222-3333-4444-555555555555"
