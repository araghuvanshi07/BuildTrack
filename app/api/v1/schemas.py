from datetime import datetime, date
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.models.enums import AttendanceStatus, PlanName, SalaryType, SiteStatus, TaskStatus, UserRole


class TenantContext(BaseModel):
    tenant_id: UUID
    schema_name: str


class UserContext(TenantContext):
    user_id: UUID | None = None
    role: UserRole = UserRole.CONTRACTOR


class OTPRequest(BaseModel):
    phone: str


class OTPVerify(BaseModel):
    phone: str
    otp: str


class RefreshTokenRequest(BaseModel):
    subject: str | None = None


class EmailLoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)


class SetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=8, max_length=128)


class InviteContractorRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str
    phone: str = Field(min_length=8, max_length=20)


class ResendSetPasswordLinkRequest(BaseModel):
    email: str


class TenantCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=140)
    schema_name: str = Field(min_length=3, max_length=63)


class TenantCreateResponse(BaseModel):
    tenant_id: UUID
    name: str
    schema_name: str


class SubscriptionCreateRequest(BaseModel):
    tenant_id: UUID
    plan_name: PlanName
    start_date: date
    end_date: date
    is_active: bool = True
    extra_sites_count: int = Field(default=0, ge=0)


class AddExtraSitesRequest(BaseModel):
    tenant_id: UUID
    additional_sites: int = Field(ge=1)


class ProjectCreateRequest(BaseModel):
    name: str
    location: str | None = None
    start_date: date | None = None
    estimated_budget: Decimal | None = None
    contractor_id: UUID | None = None


class ProjectUpdateRequest(BaseModel):
    name: str | None = None
    location: str | None = None
    start_date: date | None = None
    estimated_budget: Decimal | None = None
    contractor_id: UUID | None = None


class SiteCreateRequest(BaseModel):
    project_id: UUID
    supervisor_id: UUID | None = None
    status: SiteStatus = SiteStatus.ACTIVE


class SiteUpdateRequest(BaseModel):
    supervisor_id: UUID | None = None
    status: SiteStatus | None = None


class MaterialCreateRequest(BaseModel):
    name: str
    unit: str
    default_unit_cost: Decimal | None = None


class MaterialTransactionCreateRequest(BaseModel):
    site_id: UUID
    material_id: UUID
    quantity_received: Decimal = Decimal('0')
    quantity_used: Decimal = Decimal('0')
    unit_cost: Decimal | None = None
    photo_url: str | None = None
    notes: str | None = None

    @model_validator(mode='after')
    def validate_quantities(self):
        if self.quantity_received < 0 or self.quantity_used < 0:
            raise ValueError('Quantities cannot be negative')
        if self.quantity_received == 0 and self.quantity_used == 0:
            raise ValueError('Either quantity_received or quantity_used must be > 0')
        return self


class TaskCreateRequest(BaseModel):
    site_id: UUID
    title: str
    status: TaskStatus = TaskStatus.PENDING
    progress_percent: int = Field(default=0, ge=0, le=100)
    media_url: str | None = None


class TaskUpdateRequest(BaseModel):
    title: str | None = None
    status: TaskStatus | None = None
    progress_percent: int | None = Field(default=None, ge=0, le=100)
    media_url: str | None = None


class ExpenseCreateRequest(BaseModel):
    site_id: UUID
    category: str
    amount: Decimal = Field(ge=0)
    description: str | None = None
    receipt_url: str | None = None


class UserCreateRequest(BaseModel):
    name: str
    phone: str
    role: UserRole
    is_active: bool = True


class SupervisorCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    email: str
    phone: str = Field(min_length=8, max_length=20)


class SupervisorPermissionUpdateRequest(BaseModel):
    permission_code: str
    is_enabled: bool


class AssignSupervisorSiteRequest(BaseModel):
    site_id: UUID


class WorkerCreateRequest(BaseModel):
    site_id: UUID
    name: str = Field(min_length=2, max_length=120)
    salary_type: SalaryType
    daily_wage: Decimal | None = Field(default=None, ge=0)
    monthly_salary: Decimal | None = Field(default=None, ge=0)
    is_attendance_based: bool = True
    phone: str | None = Field(default=None, min_length=8, max_length=20)

    @model_validator(mode='after')
    def validate_salary_shape(self):
        if self.salary_type == SalaryType.DAILY:
            if self.daily_wage is None:
                raise ValueError('daily_wage is required when salary_type is daily')
            if self.monthly_salary is not None:
                raise ValueError('monthly_salary must be null when salary_type is daily')
            self.is_attendance_based = True
        if self.salary_type == SalaryType.MONTHLY:
            if self.monthly_salary is None:
                raise ValueError('monthly_salary is required when salary_type is monthly')
            if self.daily_wage is not None:
                raise ValueError('daily_wage must be null when salary_type is monthly')
        return self


class AttendanceCreateRequest(BaseModel):
    worker_id: UUID
    site_id: UUID
    date: date
    status: AttendanceStatus


class BonusCreateRequest(BaseModel):
    worker_id: UUID
    amount: Decimal = Field(ge=0)
    date: date
    note: str | None = None


class SalarySettlementUpsertRequest(BaseModel):
    worker_id: UUID
    from_date: date
    to_date: date
    is_paid: bool = True
    paid_on: date | None = None

    @model_validator(mode='after')
    def validate_period(self):
        if self.to_date < self.from_date:
            raise ValueError('to_date must be on or after from_date')
        if self.is_paid and self.paid_on is None:
            self.paid_on = date.today()
        if not self.is_paid:
            self.paid_on = None
        return self
