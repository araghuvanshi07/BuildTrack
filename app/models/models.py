from datetime import date, datetime
from decimal import Decimal
import uuid

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class User(Base):
    __tablename__ = 'users'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), unique=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text)
    password_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))


class Project(Base):
    __tablename__ = 'projects'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    location: Mapped[str | None] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date)
    estimated_budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    contractor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))


class Site(Base):
    __tablename__ = 'sites'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('projects.id'), nullable=False)
    supervisor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))


class Material(Base):
    __tablename__ = 'materials'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    unit: Mapped[str] = mapped_column(String(30), nullable=False)
    default_unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))


class MaterialTransaction(Base):
    __tablename__ = 'material_transactions'
    __table_args__ = (
        CheckConstraint('quantity_received >= 0 and quantity_used >= 0', name='material_tx_non_negative_check'),
        CheckConstraint('quantity_received > 0 or quantity_used > 0', name='material_tx_non_zero_check'),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sites.id'), nullable=False)
    material_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('materials.id'), nullable=False)
    quantity_received: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, server_default=text('0'))
    quantity_used: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False, server_default=text('0'))
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    photo_url: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))


class Task(Base):
    __tablename__ = 'tasks'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sites.id'), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('0'))
    media_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))


class Expense(Base):
    __tablename__ = 'expenses'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sites.id'), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    receipt_url: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))


class Worker(Base):
    __tablename__ = 'workers'
    __table_args__ = (
        CheckConstraint(
            "(salary_type='daily' and daily_wage is not null and monthly_salary is null) "
            "or (salary_type='monthly' and monthly_salary is not null and daily_wage is null)",
            name='worker_salary_type_check',
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sites.id'), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    salary_type: Mapped[str] = mapped_column(String(20), nullable=False)
    daily_wage: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    monthly_salary: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    is_attendance_based: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('true'))
    phone: Mapped[str | None] = mapped_column(String(20))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text('1'))
    is_deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))

    attendances: Mapped[list['Attendance']] = relationship(back_populates='worker')
    bonuses: Mapped[list['Bonus']] = relationship(back_populates='worker')
    settlements: Mapped[list['SalarySettlement']] = relationship(back_populates='worker')


class Attendance(Base):
    __tablename__ = 'attendance'
    __table_args__ = (
        UniqueConstraint('worker_id', 'date', name='uq_attendance_worker_date'),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('workers.id'), nullable=False)
    site_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('sites.id'), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    marked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))

    worker: Mapped['Worker'] = relationship(back_populates='attendances')


class Bonus(Base):
    __tablename__ = 'bonuses'

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('workers.id'), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date: Mapped[date] = mapped_column(Date, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))

    worker: Mapped['Worker'] = relationship(back_populates='bonuses')


class SalarySettlement(Base):
    __tablename__ = 'salary_settlements'
    __table_args__ = (
        UniqueConstraint('worker_id', 'from_date', 'to_date', name='uq_salary_settlement_worker_period'),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, server_default=text('gen_random_uuid()'))
    worker_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey('workers.id'), nullable=False)
    from_date: Mapped[date] = mapped_column(Date, nullable=False)
    to_date: Mapped[date] = mapped_column(Date, nullable=False)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text('false'))
    paid_on: Mapped[date | None] = mapped_column(Date)
    marked_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=text('now()'))

    worker: Mapped['Worker'] = relationship(back_populates='settlements')
