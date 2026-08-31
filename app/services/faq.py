"""Business logic for public FAQs APIs."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.core.config import settings
from app.core.exceptions import AppException
from app.services.account_settings import get_help_articles, get_support_contact_info

logger = logging.getLogger(__name__)

FAQ_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")

DEFAULT_PLAYER_FAQ_ARTICLES: list[dict[str, str]] = [
    {
        "question": "How do I join a training session?",
        "answer": (
            "Open the Sessions tab, select an upcoming practice, and tap Join Session. "
            "Enter the session code from your coach if prompted."
        ),
    },
    {
        "question": "How do I view my assigned drills?",
        "answer": (
            "Go to My Drills from the home screen to see drills assigned by your coach, "
            "including focus areas and instructions."
        ),
    },
    {
        "question": "How do I track my performance stats?",
        "answer": (
            "Open My Progress to review shooting percentages, session history, and "
            "drill performance trends over time."
        ),
    },
    {
        "question": "How do I message my coach?",
        "answer": (
            "Use the team messaging feature from your profile or session details to "
            "send a message directly to your coach."
        ),
    },
    {
        "question": "How do I update my player profile?",
        "answer": (
            "Open Profile Settings to update your name, email, and other account details "
            "visible to your team."
        ),
    },
    {
        "question": "How do I leave or switch teams?",
        "answer": (
            "Contact your coach or organization admin to request a team change. "
            "They can update your roster assignment from the coach portal."
        ),
    },
]


def _faq_id_for_question(question: str) -> uuid.UUID:
    """Return a stable UUID for a FAQ question."""
    return uuid.uuid5(FAQ_NAMESPACE, question.strip().lower())


def _build_faq_items(articles: list[dict[str, str]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for article in articles:
        question = (article.get("question") or "").strip()
        answer = (article.get("answer") or "").strip()
        if not question or not answer:
            continue
        items.append(
            {
                "id": _faq_id_for_question(question),
                "question": question,
                "answer": answer,
            }
        )
    return items


def get_player_faq_articles() -> list[dict[str, str]]:
    """Return configured player FAQ articles with defaults."""
    articles = settings.PLAYER_FAQ_ARTICLES or DEFAULT_PLAYER_FAQ_ARTICLES
    return [
        {"question": item["question"], "answer": item["answer"]}
        for item in articles
        if item.get("question") and item.get("answer")
    ]


def _build_faqs_payload_from_articles(
    *,
    articles: list[dict[str, str]],
    title: str,
    intro_description: str,
    support_link: str,
) -> dict[str, Any]:
    faqs = _build_faq_items(articles)
    contact = get_support_contact_info()

    if faqs:
        message = "FAQs loaded successfully"
        status = "ready"
        description = intro_description
    else:
        message = "No FAQs are available at this time"
        status = "empty"
        description = "Check back later or contact support for assistance."

    return {
        "success": True,
        "message": message,
        "status": status,
        "title": title,
        "description": description,
        "link": support_link,
        "error": None,
        "id": None,
        "phone": contact["phone"],
        "faqs": faqs,
    }


def build_faqs_payload() -> dict[str, Any]:
    """Build the coach FAQs screen payload."""
    return _build_faqs_payload_from_articles(
        articles=get_help_articles(),
        title=settings.FAQ_INTRO_TITLE,
        intro_description=settings.FAQ_INTRO_DESCRIPTION,
        support_link=f"{settings.API_V1_PREFIX}/support/contact",
    )


def build_player_faqs_payload() -> dict[str, Any]:
    """Build the player FAQs screen payload."""
    return _build_faqs_payload_from_articles(
        articles=get_player_faq_articles(),
        title=settings.PLAYER_FAQ_INTRO_TITLE,
        intro_description=settings.PLAYER_FAQ_INTRO_DESCRIPTION,
        support_link=f"{settings.API_V1_PREFIX}/support/contact",
    )


def get_faq_by_id(faq_id: uuid.UUID, *, profile: str = "player") -> dict[str, Any]:
    """Return one FAQ item by stable identifier or raise 404."""
    if profile == "coach":
        articles = get_help_articles()
        title = settings.FAQ_INTRO_TITLE
        intro_description = settings.FAQ_INTRO_DESCRIPTION
    else:
        articles = get_player_faq_articles()
        title = settings.PLAYER_FAQ_INTRO_TITLE
        intro_description = settings.PLAYER_FAQ_INTRO_DESCRIPTION

    faqs = _build_faq_items(articles)
    for item in faqs:
        if item["id"] == faq_id:
            contact = get_support_contact_info()
            return {
                "success": True,
                "message": "FAQ loaded successfully",
                "status": "ready",
                "title": title,
                "description": intro_description,
                "link": f"{settings.API_V1_PREFIX}/support/contact",
                "error": None,
                "id": item["id"],
                "phone": contact["phone"],
                "question": item["question"],
                "answer": item["answer"],
            }

    raise AppException(
        code="FAQ_NOT_FOUND",
        message="FAQ not found",
        status_code=404,
        details=[{"field": "id", "message": "FAQ not found"}],
    )
