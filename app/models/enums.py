from enum import Enum


class BillingCycle(str, Enum):
    MONTHLY = 'MONTHLY'
    YEARLY = 'YEARLY'


class SubscriptionStatus(str, Enum):
    TRIALING = 'TRIALING'
    ACTIVE = 'ACTIVE'
    PAST_DUE = 'PAST_DUE'
    CANCELED = 'CANCELED'
    EXPIRED = 'EXPIRED'


class AddOnStatus(str, Enum):
    ACTIVE = 'ACTIVE'
    CANCELED = 'CANCELED'


class UserRole(str, Enum):
    ADMIN = 'ADMIN'
    CONTRACTOR = 'CONTRACTOR'
    SUPERVISOR = 'SUPERVISOR'


class SiteStatus(str, Enum):
    ACTIVE = 'active'
    COMPLETED = 'completed'
    PAUSED = 'paused'


class TaskStatus(str, Enum):
    PENDING = 'pending'
    IN_PROGRESS = 'in_progress'
    COMPLETED = 'completed'


class SalaryType(str, Enum):
    DAILY = 'daily'
    MONTHLY = 'monthly'


class AttendanceStatus(str, Enum):
    PRESENT = 'present'
    ABSENT = 'absent'
    PAID_LEAVE = 'paid_leave'
    HALF_DAY = 'half_day'


class PlanName(str, Enum):
    STARTER = 'STARTER'
    GROWTH = 'GROWTH'
    PRO = 'PRO'
