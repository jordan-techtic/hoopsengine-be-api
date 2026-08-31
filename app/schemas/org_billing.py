"""Pydantic schemas for organization admin billing API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

BILLING_HISTORY_ITEM_EXAMPLE = {
    "date": "2026-08-01",
    "amount": 99.0,
    "status": "paid",
}

PAYMENT_METHOD_REQUEST_EXAMPLE = {
    "card_number": "4242424242424242",
    "expiry_date": "12/28",
    "cvv": "123",
}

PAYMENT_METHOD_RESPONSE_EXAMPLE = {
    "card_last4": "4242",
    "expiry_date": "12/28",
    "brand": "visa",
}

BillingStatus = Literal["paid", "pending", "failed"]


class PaymentMethodUpdateRequest(BaseModel):
    """Payload for updating the organization payment method."""

    model_config = ConfigDict(json_schema_extra={"example": PAYMENT_METHOD_REQUEST_EXAMPLE})

    card_number: str = Field(
        description="Card number (digits only, 13–19 characters)",
        examples=["4242424242424242"],
    )
    expiry_date: str = Field(
        description="Card expiry date in MM/YY format",
        examples=["12/28"],
    )
    cvv: str = Field(
        description="Card security code (3 or 4 digits)",
        examples=["123"],
    )


class BillingHistoryItem(BaseModel):
    """Single billing history row."""

    date: str = Field(description="Billing date in YYYY-MM-DD format", examples=["2026-08-01"])
    amount: float = Field(description="Charge amount in major currency units", examples=[99.0])
    status: BillingStatus = Field(description="Payment status", examples=["paid"])


class PaymentMethodSummary(BaseModel):
    """Masked payment method details safe for API responses."""

    card_last4: str = Field(description="Last four digits of the card", examples=["4242"])
    expiry_date: str = Field(description="Card expiry in MM/YY format", examples=["12/28"])
    brand: str | None = Field(default=None, description="Card brand when available", examples=["visa"])


class UpcomingPaymentNotification(BaseModel):
    """Notification about an upcoming organization payment."""

    type: Literal["upcoming_payment"] = Field(default="upcoming_payment")
    message: str = Field(description="Human-readable notification message")
    due_date: str = Field(description="Due date in YYYY-MM-DD format")


class BillingHistoryData(BaseModel):
    """Billing history payload returned by GET billing history endpoints."""

    billing_history: list[BillingHistoryItem] = Field(description="Past billing transactions")
    upcoming_payments: list[BillingHistoryItem] = Field(
        default_factory=list,
        description="Upcoming pending charges",
    )
    payment_method: PaymentMethodSummary | None = Field(
        default=None,
        description="Current masked payment method on file",
    )
    notifications: list[UpcomingPaymentNotification] = Field(
        default_factory=list,
        description="Payment reminders for upcoming charges",
    )


class BillingHistoryResponse(BaseModel):
    """Successful billing history response."""

    success: bool = Field(default=True)
    message: str = Field(description="Human-readable outcome message")
    data: BillingHistoryData = Field(description="Billing history and payment notifications")
    error: None = Field(default=None)


class PaymentMethodUpdateResponse(BaseModel):
    """Successful payment method update response."""

    success: bool = Field(default=True)
    message: str = Field(description="Human-readable confirmation message")
    data: PaymentMethodSummary = Field(description="Updated masked payment method")
    error: None = Field(default=None)
