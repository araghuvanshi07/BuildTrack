import asyncio
import runpy
import sys
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1 import expenses as expenses_api
from app.api.v1 import materials as materials_api
from app.api.v1 import projects as projects_api
from app.api.v1 import sites as sites_api
from app.api.v1 import tasks as tasks_api
from app.api.v1 import tenants as tenants_api
from app.api.v1.schemas import (
    ExpenseCreateRequest,
    MaterialCreateRequest,
    MaterialTransactionCreateRequest,
    ProjectCreateRequest,
    ProjectUpdateRequest,
    SiteCreateRequest,
    SiteUpdateRequest,
    SubscriptionCreateRequest,
    TaskCreateRequest,
    TaskUpdateRequest,
    TenantContext,
    TenantCreateRequest,
)
from app.core import exceptions as core_exceptions
from app.core.logging import configure_logging, get_logger
from app.models.enums import BillingCycle, SiteStatus, SubscriptionStatus, TaskStatus
from app.repositories import dashboard as dashboard_repo
from app.repositories import expenses as expenses_repo
from app.repositories import materials as materials_repo
from app.repositories import projects as projects_repo
from app.repositories import sites as sites_repo
from app.repositories import tasks as tasks_repo
from app.repositories import tenants as tenants_repo
from app.services import dashboard_service, projects_service, sites_service, tasks_service, tenants_service
from app.services import expenses_service, materials_service
from app.utils.payloads import to_db_payload


def _run(coro):
    return asyncio.run(coro)


def test_logging_configure_and_get_logger(monkeypatch) -> None:
    captured = {}

    def _fake_dict_config(cfg: dict) -> None:
        captured["cfg"] = cfg

    monkeypatch.setattr("app.core.logging.dictConfig", _fake_dict_config)
    configure_logging("debug")
    assert captured["cfg"]["root"]["level"] == "DEBUG"
    assert captured["cfg"]["handlers"]["console"]["class"] == "logging.StreamHandler"

    logger = get_logger("buildtrack.tests")
    assert logger.name == "buildtrack.tests"


def test_exception_handlers_all_branches(monkeypatch) -> None:
    app = FastAPI()
    core_exceptions.register_exception_handlers(app)

    @app.get("/app-error")
    async def _app_error():
        raise core_exceptions.AppError("BAD", "bad input", status_code=409)

    @app.get("/db-error")
    async def _db_error():
        raise SQLAlchemyError("db down")

    @app.get("/fallback")
    async def _fallback():
        raise RuntimeError("boom")

    @app.get("/http")
    async def _http():
        raise HTTPException(status_code=418, detail="teapot")

    @app.get("/validate/{item_id}")
    async def _validate(item_id: int):
        return {"id": item_id}

    logged = []
    monkeypatch.setattr(core_exceptions.logger, "exception", lambda *args, **kwargs: logged.append((args, kwargs)))
    client = TestClient(app, raise_server_exceptions=False)

    app_error = client.get("/app-error")
    assert app_error.status_code == 409
    assert app_error.json()["error"]["code"] == "BAD"

    validate = client.get("/validate/not-an-int")
    assert validate.status_code == 422
    assert validate.json()["error"]["code"] == "VALIDATION_ERROR"

    db_error = client.get("/db-error")
    assert db_error.status_code == 500
    assert db_error.json()["error"]["code"] == "DB_ERROR"

    fallback = client.get("/fallback")
    assert fallback.status_code == 500
    assert fallback.json()["error"]["code"] == "INTERNAL_ERROR"

    http_error = client.get("/http")
    assert http_error.status_code == 418
    assert http_error.json()["detail"] == "teapot"

    assert len(logged) == 2


def test_exception_fallback_reraises_http_exception() -> None:
    app = FastAPI()
    core_exceptions.register_exception_handlers(app)
    fallback = app.exception_handlers[Exception]
    with pytest.raises(HTTPException):
        _run(fallback(MagicMock(), HTTPException(status_code=401, detail="unauthorized")))


def test_bootstrap_main_executes_run(monkeypatch) -> None:
    called = {}

    def _fake_asyncio_run(coro):
        called["coro"] = coro
        coro.close()

    monkeypatch.setattr("asyncio.run", _fake_asyncio_run)
    sys.modules.pop("app.db.bootstrap", None)
    runpy.run_module("app.db.bootstrap", run_name="__main__")
    assert "coro" in called


def test_utils_to_db_payload_branches() -> None:
    payload = {"id": uuid4(), "status": TaskStatus.PENDING, "nullable": None}
    out = to_db_payload(payload, exclude_none=True, uuid_fields={"id"}, enum_fields={"status"})
    assert isinstance(out["id"], str)
    assert out["status"] == "pending"
    assert "nullable" not in out

    with pytest.raises(TypeError):
        to_db_payload(object())


def test_dashboard_repository_get_summary() -> None:
    db = MagicMock()
    site_counts = MagicMock()
    site_counts.mappings.return_value.one.return_value = {"total_sites": 3, "active_sites": 2}
    expense = MagicMock()
    expense.scalar_one.return_value = Decimal("100.5")
    material = MagicMock()
    material.scalar_one.return_value = Decimal("40")
    progress = MagicMock()
    progress.scalar_one.return_value = Decimal("66.666")
    db.execute = AsyncMock(side_effect=[site_counts, expense, material, progress])

    summary = _run(dashboard_repo.get_summary(db))
    assert summary == {
        "total_sites": 3,
        "active_sites": 2,
        "total_expense": 100.5,
        "total_material_cost": 40.0,
        "overall_progress_percentage": 66.67,
    }


def test_repositories_project_site_task_material_expense_paths() -> None:
    db = MagicMock()

    project_list = MagicMock()
    project_list.mappings.return_value.all.return_value = [{"id": "p1"}]
    db.execute = AsyncMock(return_value=project_list)
    assert _run(projects_repo.list_projects(db)) == [{"id": "p1"}]

    project_one = MagicMock()
    project_one.mappings.return_value.one_or_none.return_value = {"id": "p2"}
    db.execute = AsyncMock(return_value=project_one)
    assert _run(projects_repo.get_project(db, uuid4())) == {"id": "p2"}

    project_none = MagicMock()
    project_none.mappings.return_value.one_or_none.return_value = None
    db.execute = AsyncMock(return_value=project_none)
    assert _run(projects_repo.get_project(db, uuid4())) is None

    site_list = MagicMock()
    site_list.mappings.return_value.all.return_value = [{"id": "s1"}]
    db.execute = AsyncMock(return_value=site_list)
    assert _run(sites_repo.list_sites(db)) == [{"id": "s1"}]

    update_data = {"status": "paused"}
    db.execute = AsyncMock()
    _run(sites_repo.update_site(db, uuid4(), update_data))
    assert "site_id" in update_data
    assert "update sites set status=:status" in str(db.execute.call_args.args[0]).lower()

    task_list = MagicMock()
    task_list.mappings.return_value.all.return_value = [{"id": "t1"}]
    db.execute = AsyncMock(return_value=task_list)
    assert _run(tasks_repo.list_tasks(db, uuid4())) == [{"id": "t1"}]

    task_update = {"progress_percent": 25}
    db.execute = AsyncMock()
    _run(tasks_repo.update_task(db, uuid4(), task_update))
    assert "task_id" in task_update
    assert "update tasks set progress_percent=:progress_percent" in str(db.execute.call_args.args[0]).lower()

    material_list = MagicMock()
    material_list.mappings.return_value.all.return_value = [{"name": "cement"}]
    db.execute = AsyncMock(return_value=material_list)
    assert _run(materials_repo.materials_summary(db, "site-1")) == [{"name": "cement"}]

    expense_list = MagicMock()
    expense_list.mappings.return_value.all.return_value = [{"category": "labor"}]
    db.execute = AsyncMock(return_value=expense_list)
    assert _run(expenses_repo.list_expenses(db, uuid4())) == [{"category": "labor"}]


def test_repositories_get_site_and_get_task_paths() -> None:
    db = MagicMock()

    site_row = MagicMock()
    site_row.mappings.return_value.one_or_none.return_value = {"id": "s1"}
    db.execute = AsyncMock(return_value=site_row)
    assert _run(sites_repo.get_site(db, uuid4())) == {"id": "s1"}

    site_none = MagicMock()
    site_none.mappings.return_value.one_or_none.return_value = None
    db.execute = AsyncMock(return_value=site_none)
    assert _run(sites_repo.get_site(db, uuid4())) is None

    task_row = MagicMock()
    task_row.mappings.return_value.one_or_none.return_value = {"id": "t1"}
    db.execute = AsyncMock(return_value=task_row)
    assert _run(tasks_repo.get_task(db, uuid4())) == {"id": "t1"}

    task_none = MagicMock()
    task_none.mappings.return_value.one_or_none.return_value = None
    db.execute = AsyncMock(return_value=task_none)
    assert _run(tasks_repo.get_task(db, uuid4())) is None


def test_repositories_create_paths() -> None:
    db = MagicMock()
    obj_id = uuid4()

    scalar = MagicMock()
    scalar.scalar_one.return_value = obj_id
    db.execute = AsyncMock(return_value=scalar)
    assert _run(projects_repo.create_project(db, {"name": "P"})) == obj_id

    scalar = MagicMock()
    scalar.scalar_one.return_value = obj_id
    db.execute = AsyncMock(return_value=scalar)
    assert _run(sites_repo.create_site(db, {"project_id": str(uuid4()), "status": "active"})) == obj_id

    scalar = MagicMock()
    scalar.scalar_one.return_value = obj_id
    db.execute = AsyncMock(return_value=scalar)
    assert _run(tasks_repo.create_task(db, {"site_id": str(uuid4()), "title": "T", "status": "pending", "progress_percent": 0, "media_url": None})) == obj_id

    scalar = MagicMock()
    scalar.scalar_one.return_value = obj_id
    db.execute = AsyncMock(return_value=scalar)
    assert _run(materials_repo.create_material(db, {"name": "cement", "unit": "bag", "default_unit_cost": None})) == obj_id

    scalar = MagicMock()
    scalar.scalar_one.return_value = obj_id
    db.execute = AsyncMock(return_value=scalar)
    assert _run(
        materials_repo.create_material_transaction(
            db,
            {
                "site_id": str(uuid4()),
                "material_id": str(uuid4()),
                "quantity_received": Decimal("1"),
                "quantity_used": Decimal("0"),
                "unit_cost": None,
                "photo_url": None,
                "notes": None,
            },
        )
    ) == obj_id

    scalar = MagicMock()
    scalar.scalar_one.return_value = obj_id
    db.execute = AsyncMock(return_value=scalar)
    assert _run(expenses_repo.create_expense(db, {"site_id": str(uuid4()), "category": "labor", "amount": Decimal("1")})) == obj_id


def test_tenants_repository_paths() -> None:
    db = MagicMock()

    tenant_row = MagicMock()
    tenant_row.mappings.return_value.one.return_value = {"id": "t1", "name": "ACME", "schema_name": "t_acme"}
    db.execute = AsyncMock(return_value=tenant_row)
    assert _run(tenants_repo.insert_tenant(db, "ACME", "t_acme")) == {"id": "t1", "name": "ACME", "schema_name": "t_acme"}

    scalar_none = MagicMock()
    scalar_none.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=scalar_none)
    assert _run(tenants_repo.fetch_active_core_plan_id(db)) is None

    scalar_plan = MagicMock()
    plan_id = uuid4()
    scalar_plan.scalar_one_or_none.return_value = plan_id
    db.execute = AsyncMock(return_value=scalar_plan)
    assert _run(tenants_repo.fetch_active_core_plan_id(db)) == plan_id

    mapping_none = MagicMock()
    mapping_none.mappings.return_value.one_or_none.return_value = None
    db.execute = AsyncMock(return_value=mapping_none)
    assert _run(tenants_repo.fetch_tenant_context(db, uuid4())) is None

    mapping_row = MagicMock()
    mapping_row.mappings.return_value.one_or_none.return_value = {"id": "x", "schema_name": "t_x"}
    db.execute = AsyncMock(return_value=mapping_row)
    assert _run(tenants_repo.fetch_tenant_context(db, uuid4())) == {"id": "x", "schema_name": "t_x"}

    valid_result = MagicMock()
    valid_result.scalar_one.return_value = 0
    db.execute = AsyncMock(return_value=valid_result)
    assert _run(tenants_repo.is_subscription_valid(db, uuid4())) is False

    db.execute = AsyncMock()
    _run(tenants_repo.insert_default_active_subscription(db, uuid4(), uuid4(), BillingCycle.YEARLY))
    assert "1 year" in str(db.execute.call_args.args[0])

    scalar_sub = MagicMock()
    sub_id = uuid4()
    scalar_sub.scalar_one.return_value = sub_id
    db.execute = AsyncMock(return_value=scalar_sub)
    assert _run(
        tenants_repo.insert_subscription(
            db,
            uuid4(),
            uuid4(),
            BillingCycle.MONTHLY,
            SubscriptionStatus.ACTIVE,
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
            None,
        )
    ) == sub_id


def test_services_projects_sites_tasks_dashboard(monkeypatch) -> None:
    db = object()
    tenant = "t_unit"
    pid = uuid4()

    search_path = AsyncMock()
    monkeypatch.setattr(projects_service, "set_tenant_search_path", search_path)
    monkeypatch.setattr(projects_service.repo, "create_project", AsyncMock(return_value=pid))
    project_payload = ProjectCreateRequest(name="P1")
    assert _run(projects_service.create_project(db, tenant, project_payload)) == pid
    assert search_path.await_count == 1

    monkeypatch.setattr(projects_service.repo, "list_projects", AsyncMock(return_value=[{"id": "p"}]))
    assert _run(projects_service.list_projects(db, tenant)) == [{"id": "p"}]

    monkeypatch.setattr(projects_service.repo, "get_project", AsyncMock(return_value={"id": "p2"}))
    assert _run(projects_service.get_project(db, tenant, uuid4())) == {"id": "p2"}
    monkeypatch.setattr(projects_service.repo, "get_project", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        _run(projects_service.get_project(db, tenant, uuid4()))

    monkeypatch.setattr(projects_service.repo, "get_project", AsyncMock(return_value={"id": "p3"}))
    update_project_mock = AsyncMock()
    monkeypatch.setattr(projects_service.repo, "update_project", update_project_mock)
    _run(projects_service.update_project(db, tenant, uuid4(), ProjectUpdateRequest()))
    update_project_mock.assert_not_awaited()

    monkeypatch.setattr(projects_service.repo, "get_project", AsyncMock(return_value={"id": "p4"}))
    update_project_called = AsyncMock()
    monkeypatch.setattr(projects_service.repo, "update_project", update_project_called)
    _run(projects_service.update_project(db, tenant, uuid4(), ProjectUpdateRequest(name="X")))
    update_project_called.assert_awaited_once()

    monkeypatch.setattr(projects_service.repo, "get_project", AsyncMock(return_value={"id": "p5"}))
    delete_project_called = AsyncMock()
    monkeypatch.setattr(projects_service.repo, "delete_project", delete_project_called)
    _run(projects_service.delete_project(db, tenant, uuid4()))
    delete_project_called.assert_awaited_once()

    monkeypatch.setattr(sites_service, "set_tenant_search_path", AsyncMock())
    monkeypatch.setattr(sites_service.repo, "create_site", AsyncMock(return_value=pid))
    site_payload = SiteCreateRequest(project_id=uuid4(), status=SiteStatus.ACTIVE)
    assert _run(sites_service.create_site(db, tenant, site_payload)) == pid

    monkeypatch.setattr(sites_service.repo, "list_sites", AsyncMock(return_value=[{"id": "s"}]))
    assert _run(sites_service.list_sites(db, tenant)) == [{"id": "s"}]

    update_site_mock = AsyncMock()
    monkeypatch.setattr(sites_service.repo, "get_site", AsyncMock(return_value={"id": "s"}))
    monkeypatch.setattr(sites_service.repo, "update_site", update_site_mock)
    _run(sites_service.update_site(db, tenant, uuid4(), SiteUpdateRequest()))
    update_site_mock.assert_not_awaited()

    monkeypatch.setattr(tasks_service, "set_tenant_search_path", AsyncMock())
    monkeypatch.setattr(tasks_service.repo, "create_task", AsyncMock(return_value=pid))
    task_payload = TaskCreateRequest(site_id=uuid4(), title="T1", status=TaskStatus.PENDING, progress_percent=1)
    assert _run(tasks_service.create_task(db, tenant, task_payload)) == pid

    update_task_mock = AsyncMock()
    monkeypatch.setattr(tasks_service.repo, "get_task", AsyncMock(return_value={"id": "t"}))
    monkeypatch.setattr(tasks_service.repo, "update_task", update_task_mock)
    _run(tasks_service.update_task(db, tenant, uuid4(), TaskUpdateRequest()))
    update_task_mock.assert_not_awaited()

    monkeypatch.setattr(tasks_service.repo, "list_tasks", AsyncMock(return_value=[{"id": "t"}]))
    assert _run(tasks_service.list_tasks(db, tenant, uuid4())) == [{"id": "t"}]

    update_site_called = AsyncMock()
    monkeypatch.setattr(sites_service.repo, "update_site", update_site_called)
    _run(sites_service.update_site(db, tenant, uuid4(), SiteUpdateRequest(status=SiteStatus.ACTIVE)))
    update_site_called.assert_awaited_once()

    update_task_called = AsyncMock()
    monkeypatch.setattr(tasks_service.repo, "update_task", update_task_called)
    _run(tasks_service.update_task(db, tenant, uuid4(), TaskUpdateRequest(progress_percent=10)))
    update_task_called.assert_awaited_once()

    monkeypatch.setattr(dashboard_service, "set_tenant_search_path", AsyncMock())
    monkeypatch.setattr(dashboard_service.repo, "get_summary", AsyncMock(return_value={"total_sites": 0}))
    assert _run(dashboard_service.get_summary(db, tenant)) == {"total_sites": 0}

    monkeypatch.setattr(sites_service.repo, "get_site", AsyncMock(return_value={"id": "s2"}))
    assert _run(sites_service.get_site(db, tenant, uuid4())) == {"id": "s2"}
    delete_site_called = AsyncMock()
    monkeypatch.setattr(sites_service.repo, "delete_site", delete_site_called)
    _run(sites_service.delete_site(db, tenant, uuid4()))
    delete_site_called.assert_awaited_once()

    monkeypatch.setattr(tasks_service.repo, "get_task", AsyncMock(return_value={"id": "t2"}))
    assert _run(tasks_service.get_task(db, tenant, uuid4())) == {"id": "t2"}
    delete_task_called = AsyncMock()
    monkeypatch.setattr(tasks_service.repo, "delete_task", delete_task_called)
    _run(tasks_service.delete_task(db, tenant, uuid4()))
    delete_task_called.assert_awaited_once()


def test_services_project_site_task_not_found_paths(monkeypatch) -> None:
    db = object()
    tenant = "t_nf"

    monkeypatch.setattr(projects_service, "set_tenant_search_path", AsyncMock())
    monkeypatch.setattr(projects_service.repo, "get_project", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        _run(projects_service.update_project(db, tenant, uuid4(), ProjectUpdateRequest(name="N")))
    with pytest.raises(HTTPException):
        _run(projects_service.delete_project(db, tenant, uuid4()))

    monkeypatch.setattr(sites_service, "set_tenant_search_path", AsyncMock())
    monkeypatch.setattr(sites_service.repo, "get_site", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        _run(sites_service.get_site(db, tenant, uuid4()))
    with pytest.raises(HTTPException):
        _run(sites_service.update_site(db, tenant, uuid4(), SiteUpdateRequest(status=SiteStatus.PAUSED)))
    with pytest.raises(HTTPException):
        _run(sites_service.delete_site(db, tenant, uuid4()))

    monkeypatch.setattr(tasks_service, "set_tenant_search_path", AsyncMock())
    monkeypatch.setattr(tasks_service.repo, "get_task", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        _run(tasks_service.get_task(db, tenant, uuid4()))
    with pytest.raises(HTTPException):
        _run(tasks_service.update_task(db, tenant, uuid4(), TaskUpdateRequest(progress_percent=10)))
    with pytest.raises(HTTPException):
        _run(tasks_service.delete_task(db, tenant, uuid4()))


def test_tenants_service_error_paths(monkeypatch) -> None:
    db = MagicMock()
    payload = TenantCreateRequest(name="Tenant", schema_name="tenant_schema", billing_cycle=BillingCycle.MONTHLY)
    monkeypatch.setattr(tenants_service.repo, "fetch_active_core_plan_id", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        _run(tenants_service.create_tenant(db, payload))

    sub_payload = SubscriptionCreateRequest(
        tenant_id=uuid4(),
        billing_cycle=BillingCycle.MONTHLY,
        status=SubscriptionStatus.ACTIVE,
        period_start=datetime.now(timezone.utc),
        period_end=datetime.now(timezone.utc),
        trial_end=None,
    )
    monkeypatch.setattr(tenants_service.repo, "fetch_active_core_plan_id", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        _run(tenants_service.create_subscription(db, sub_payload))

    monkeypatch.setattr(tenants_service.repo, "fetch_tenant_context", AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        _run(tenants_service.get_tenant_context(db, uuid4()))

    tenant_ctx = TenantContext(tenant_id=uuid4(), schema_name="t1")
    monkeypatch.setattr(tenants_service.repo, "is_subscription_valid", AsyncMock(return_value=False))
    with pytest.raises(HTTPException):
        _run(tenants_service.require_active_subscription(db, tenant_ctx))


def test_tenants_service_create_tenant_success(monkeypatch) -> None:
    db = MagicMock()
    db.execute = AsyncMock()
    tenant_id = uuid4()

    monkeypatch.setattr(tenants_service, "validate_schema_name", lambda v: v)
    monkeypatch.setattr(tenants_service.repo, "fetch_active_core_plan_id", AsyncMock(return_value=uuid4()))
    monkeypatch.setattr(
        tenants_service.repo,
        "insert_tenant",
        AsyncMock(return_value={"id": tenant_id, "name": "ACME", "schema_name": "t_acme"}),
    )
    monkeypatch.setattr(tenants_service, "tenant_schema_statements", lambda _s: ["create schema x", "create table y"])
    default_sub = AsyncMock()
    monkeypatch.setattr(tenants_service.repo, "insert_default_active_subscription", default_sub)

    out = _run(
        tenants_service.create_tenant(
            db,
            TenantCreateRequest(name="ACME", schema_name="t_acme", billing_cycle=BillingCycle.MONTHLY),
        )
    )
    assert out["tenant_id"] == tenant_id
    assert db.execute.await_count == 2
    default_sub.assert_awaited_once()


def test_services_expenses_materials_and_tenants_success(monkeypatch) -> None:
    db = object()
    tenant = "t_success"
    uid = uuid4()

    monkeypatch.setattr(expenses_service, "set_tenant_search_path", AsyncMock())
    monkeypatch.setattr(expenses_service.repo, "create_expense", AsyncMock(return_value=uid))
    ep = ExpenseCreateRequest(site_id=uuid4(), category="fuel", amount=Decimal("20"))
    assert _run(expenses_service.create_expense(db, tenant, ep)) == uid

    monkeypatch.setattr(expenses_service.repo, "list_expenses", AsyncMock(return_value=[{"id": "e1"}]))
    assert _run(expenses_service.list_expenses(db, tenant, uuid4())) == [{"id": "e1"}]

    monkeypatch.setattr(materials_service, "set_tenant_search_path", AsyncMock())
    monkeypatch.setattr(materials_service.repo, "create_material", AsyncMock(return_value=uid))
    assert _run(materials_service.create_material(db, tenant, MaterialCreateRequest(name="sand", unit="kg"))) == uid

    monkeypatch.setattr(materials_service.repo, "create_material_transaction", AsyncMock(return_value=uid))
    mt = MaterialTransactionCreateRequest(
        site_id=uuid4(),
        material_id=uuid4(),
        quantity_received=Decimal("2"),
        quantity_used=Decimal("0"),
    )
    assert _run(materials_service.create_material_transaction(db, tenant, mt)) == uid

    monkeypatch.setattr(materials_service.repo, "materials_summary", AsyncMock(return_value=[{"name": "sand"}]))
    assert _run(materials_service.materials_summary(db, tenant, uuid4())) == [{"name": "sand"}]

    tenant_id = uuid4()
    monkeypatch.setattr(tenants_service.repo, "fetch_active_core_plan_id", AsyncMock(return_value=uuid4()))
    monkeypatch.setattr(tenants_service.repo, "insert_subscription", AsyncMock(return_value=uid))
    sub = SubscriptionCreateRequest(
        tenant_id=tenant_id,
        billing_cycle=BillingCycle.MONTHLY,
        status=SubscriptionStatus.ACTIVE,
        period_start=datetime.now(timezone.utc),
        period_end=datetime.now(timezone.utc),
    )
    assert _run(tenants_service.create_subscription(MagicMock(), sub)) == uid

    monkeypatch.setattr(tenants_service.repo, "fetch_tenant_context", AsyncMock(return_value={"id": tenant_id, "schema_name": "t1"}))
    tenant_ctx = _run(tenants_service.get_tenant_context(MagicMock(), tenant_id))
    assert tenant_ctx.schema_name == "t1"

    ctx = TenantContext(tenant_id=tenant_id, schema_name="t1")
    monkeypatch.setattr(tenants_service.repo, "is_subscription_valid", AsyncMock(return_value=True))
    assert _run(tenants_service.require_active_subscription(MagicMock(), ctx)) == ctx


def test_api_endpoint_direct_returns(monkeypatch) -> None:
    tenant = TenantContext(tenant_id=uuid4(), schema_name="t_direct")
    db = object()
    uid = uuid4()

    monkeypatch.setattr(expenses_api, "create_expense", AsyncMock(return_value=uid))
    expense_payload = ExpenseCreateRequest(site_id=uuid4(), category="fuel", amount=Decimal("10"))
    assert _run(expenses_api.create_expense_endpoint(expense_payload, tenant, db)) == {"id": str(uid)}

    monkeypatch.setattr(materials_api, "create_material", AsyncMock(return_value=uid))
    assert _run(materials_api.create_material_endpoint(MaterialCreateRequest(name="c", unit="bag"), tenant, db)) == {
        "id": str(uid)
    }

    monkeypatch.setattr(materials_api, "create_material_transaction", AsyncMock(return_value=uid))
    tx_payload = MaterialTransactionCreateRequest(
        site_id=uuid4(),
        material_id=uuid4(),
        quantity_received=Decimal("1"),
        quantity_used=Decimal("0"),
    )
    assert _run(materials_api.create_material_transaction_endpoint(tx_payload, tenant, db)) == {"id": str(uid)}

    monkeypatch.setattr(projects_api, "create_project", AsyncMock(return_value=uid))
    assert _run(projects_api.create_project_endpoint(ProjectCreateRequest(name="P1"), tenant, db)) == {"id": str(uid)}
    monkeypatch.setattr(projects_api, "update_project", AsyncMock(return_value=None))
    assert _run(projects_api.update_project_endpoint(uuid4(), ProjectUpdateRequest(name="U"), tenant, db)) == {
        "message": "Updated"
    }
    monkeypatch.setattr(projects_api, "delete_project", AsyncMock(return_value=None))
    assert _run(projects_api.delete_project_endpoint(uuid4(), tenant, db)) == {"message": "Deleted"}

    monkeypatch.setattr(sites_api, "create_site", AsyncMock(return_value=uid))
    assert _run(sites_api.create_site_endpoint(SiteCreateRequest(project_id=uuid4()), tenant, db)) == {"id": str(uid)}

    monkeypatch.setattr(tasks_api, "create_task", AsyncMock(return_value=uid))
    assert _run(tasks_api.create_task_endpoint(TaskCreateRequest(site_id=uuid4(), title="T", progress_percent=1), tenant, db)) == {
        "id": str(uid)
    }

    monkeypatch.setattr(tasks_api, "update_task", AsyncMock(return_value=None))
    assert _run(tasks_api.update_task_endpoint(uuid4(), TaskUpdateRequest(progress_percent=10), tenant, db)) == {
        "message": "Updated"
    }

    monkeypatch.setattr(sites_api, "update_site", AsyncMock(return_value=None))
    assert _run(sites_api.update_site_endpoint(uuid4(), SiteUpdateRequest(status=SiteStatus.PAUSED), tenant, db)) == {
        "message": "Updated"
    }
    monkeypatch.setattr(sites_api, "delete_site", AsyncMock(return_value=None))
    assert _run(sites_api.delete_site_endpoint(uuid4(), tenant, db)) == {"message": "Deleted"}

    monkeypatch.setattr(tenants_api, "create_subscription", AsyncMock(return_value=uid))
    sub_payload = SubscriptionCreateRequest(
        tenant_id=uuid4(),
        billing_cycle=BillingCycle.MONTHLY,
        status=SubscriptionStatus.ACTIVE,
        period_start=datetime.now(timezone.utc),
        period_end=datetime.now(timezone.utc),
    )
    assert _run(tenants_api.create_subscription_endpoint(sub_payload, db)) == {"subscription_id": str(uid)}
    monkeypatch.setattr(tasks_api, "delete_task", AsyncMock(return_value=None))
    assert _run(tasks_api.delete_task_endpoint(uuid4(), tenant, db)) == {"message": "Deleted"}
