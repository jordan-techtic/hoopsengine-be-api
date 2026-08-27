"""Business logic for public FAQs APIs."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from app.core.config import settings
from app.services.account_settings import get_help_articles, get_support_contact_info

logger = logging.getLogger(__name__)

FAQ_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


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


def build_faqs_payload() -> dict[str, Any]:
    """Build the public FAQs screen payload."""
    faqs = _build_faq_items(get_help_articles())
    contact = get_support_contact_info()

    if faqs:
        message = "FAQs loaded successfully"
        status = "ready"
        description = settings.FAQ_INTRO_DESCRIPTION
    else:
        message = "No FAQs are available at this time"
        status = "empty"
        description = "Check back later or contact support for assistance."

    return {
        "success": True,
        "message": message,
        "status": status,
        "title": settings.FAQ_INTRO_TITLE,
        "description": description,
        "link": f"{settings.API_V1_PREFIX}/support/contact",
        "error": None,
        "id": None,
        "phone": contact["phone"],
        "faqs": faqs,
    }
