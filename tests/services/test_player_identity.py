"""Unit tests for player identity helpers."""

from __future__ import annotations

from uuid import UUID

from app.services.player_identity import _player_context_from_row


def test_player_context_from_row_includes_subteam_id() -> None:
    context = _player_context_from_row(
        {
            "id": "00000000-0000-4000-8000-000000000039",
            "org_id": "00000000-0000-4000-8000-000000000010",
            "subteam_id": "00000000-0000-4000-8000-000000000040",
            "first_name": "Viewer",
            "last_name": "Player",
        }
    )
    assert context.player_id == UUID("00000000-0000-4000-8000-000000000039")
    assert context.org_id == UUID("00000000-0000-4000-8000-000000000010")
    assert context.subteam_id == UUID("00000000-0000-4000-8000-000000000040")


def test_player_context_from_row_handles_missing_subteam() -> None:
    context = _player_context_from_row(
        {
            "id": "00000000-0000-4000-8000-000000000039",
            "org_id": "00000000-0000-4000-8000-000000000010",
            "subteam_id": None,
            "first_name": "Viewer",
            "last_name": "Player",
        }
    )
    assert context.subteam_id is None
