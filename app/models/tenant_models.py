from datetime import date, datetime
from decimal import Decimal
import uuid

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Tenant(Base):
    __tablename__ = 'tenants'
    __table_args__ = {'schema': 'public'}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(String(140), nullable=False)
    schema_name: Mapped[str] = mapped_column(String(63), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))


class Plan(Base):
    __tablename__ = 'plans'
    __table_args__ = {'schema': 'public'}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    price_usd_monthly: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    max_sites: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))


class TenantSubscription(Base):
    __tablename__ = 'tenant_subscriptions'
    __table_args__ = (
        CheckConstraint('extra_sites_count >= 0', name='tenant_subscription_extra_sites_check'),
        CheckConstraint('trial_end_date >= trial_start_date', name='tenant_subscription_trial_period_check'),
        {
            'schema': 'public',
        },
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    tenant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('public.tenants.id', ondelete='CASCADE'), nullable=False, unique=True)
    plan_name: Mapped[str | None] = mapped_column(String(20))
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    extra_sites_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    trial_start_date: Mapped[date] = mapped_column(Date, nullable=False)
    trial_end_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_trial_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
