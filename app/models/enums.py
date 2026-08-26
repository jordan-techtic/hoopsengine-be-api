from enum import StrEnum


class UserRole(StrEnum):
    SUPER_ADMIN = "super_admin"
    ORG_ADMIN = "org_admin"
    COACH = "coach"
    PLAYER = "player"


class SubscriptionPlanRole(StrEnum):
    ORG_ADMIN = "org_admin"
    COACH = "coach"


class PlanStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class BillingFrequency(StrEnum):
    MONTHLY = "monthly"
    YEARLY = "yearly"


class LimitType(StrEnum):
    LIMITED = "limited"
    UNLIMITED = "unlimited"


class HistoricalRecordsDuration(StrEnum):
    ONE_MONTH = "1_month"
    THREE_MONTHS = "3_months"
    SIX_MONTHS = "6_months"
    ONE_YEAR = "1_year"
    UNLIMITED = "unlimited"


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    CANCELED = "canceled"
    PAST_DUE = "past_due"
    UNPAID = "unpaid"
    TRIALING = "trialing"
    INCOMPLETE = "incomplete"
    INCOMPLETE_EXPIRED = "incomplete_expired"
    PAUSED = "paused"
