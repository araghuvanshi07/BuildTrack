import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from jose import jwt
from sqlalchemy.exc import IntegrityError

from app.api.v1 import auth as auth_api
from app.api.v1 import contractor as contractor_api
from app.api.v1 import supervisor as supervisor_api
from app.api.v1.schemas import (
    EmailLoginRequest,
    InviteContractorRequest,
    ResendSetPasswordLinkRequest,
    SetPasswordRequest,
    SubscriptionCreateRequest,
    SupervisorCreateRequest,
    SupervisorPermissionUpdateRequest,
    TenantContext,
    UserContext,
    UserRole,
    WorkerCreateRequest,
)
from app.core import dependencies
from app.core.config import get_settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    create_set_password_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.repositories import auth as auth_repo
from app.repositories import access_control as access_repo
from app.services import auth_service, access_control_service, tenants_service
from app.models.enums import BillingCycle, SubscriptionStatus
from app.utils import email as email_utils


def _run(coro):
    return asyncio.run(coro)


def test_security_helpers_roundtrip() -> None:
    access = create_access_token('u@example.com', claims={'tenant_id': 't1', 'role': 'CONTRACTOR'})
    refresh = create_refresh_token('u@example.com', claims={'tenant_id': 't1'})
    set_pw = create_set_password_token(tenant_id='t1', user_id='u1', email='u@example.com')
    assert decode_token(access)['sub'] == 'u@example.com'
    assert decode_token(refresh)['type'] == 'refresh'
    assert decode_token(set_pw)['type'] == 'set_password'

    pw_hash = hash_password('Password123')
    assert verify_password('Password123', pw_hash) is True
    assert verify_password('BadPassword', pw_hash) is False


def test_email_send_success_and_oserror(monkeypatch) -> None:
    sent = {}

    class _SMTP:
        def __init__(self, *_a, **_k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def starttls(self):
            sent['tls'] = True

        def login(self, *_a):
            sent['login'] = True

        def send_message(self, _msg):
            sent['ok'] = True

    monkeypatch.setattr('smtplib.SMTP', _SMTP)
    email_utils.send_email('to@example.com', 's', 'b')
    assert sent['ok'] is True

    class _SMTPFail:
        def __init__(self, *_a, **_k):
            raise OSError('no smtp')

    monkeypatch.setattr('smtplib.SMTP', _SMTPFail)
    email_utils.send_email('to@example.com', 's', 'b')


def test_auth_repository_methods() -> None:
    db = MagicMock()
    row = MagicMock()
    row.mappings.return_value.one_or_none.return_value = {'id': 'u1', 'email': 'a@a.com'}
    db.execute = AsyncMock(return_value=row)
    assert _run(auth_repo.get_user_by_email(db, 'a@a.com')) == {'id': 'u1', 'email': 'a@a.com'}

    none_row = MagicMock()
    none_row.mappings.return_value.one_or_none.return_value = None
    db.execute = AsyncMock(return_value=none_row)
    assert _run(auth_repo.get_user_by_id(db, uuid4())) is None

    db.execute = AsyncMock()
    _run(auth_repo.update_password_hash(db, uuid4(), 'h'))
    assert db.execute.await_count == 1

    scalar = MagicMock()
    uid = uuid4()
    scalar.scalar_one.return_value = uid
    db.execute = AsyncMock(return_value=scalar)
    assert _run(auth_repo.create_contractor_user(db, {'name': 'n', 'email': 'e', 'phone': 'p'})) == uid


def test_access_control_repository_methods() -> None:
    db = MagicMock()
    uid = uuid4()

    row = MagicMock()
    row.scalar_one.return_value = uid
    db.execute = AsyncMock(return_value=row)
    assert _run(access_repo.create_supervisor(db, {'name': 'n', 'email': 'e@e.com', 'phone': 'p'})) == uid

    db.execute = AsyncMock()
    _run(access_repo.upsert_supervisor_permission(db, uid, 'add_worker', True))
    _run(access_repo.assign_supervisor_to_site(db, uid, uuid4()))
    scalar_worker = MagicMock()
    scalar_worker.scalar_one.return_value = uuid4()
    db.execute = AsyncMock(return_value=scalar_worker)
    _run(access_repo.create_worker(db, {'site_id': str(uuid4()), 'name': 'w', 'phone': '1', 'created_by': str(uid)}))

    list_rows = MagicMock()
    list_rows.mappings.return_value.all.return_value = [{'permission_code': 'add_worker', 'is_enabled': True}]
    db.execute = AsyncMock(return_value=list_rows)
    assert _run(access_repo.list_supervisor_permissions(db, uid))[0]['permission_code'] == 'add_worker'

    scalar_bool = MagicMock()
    scalar_bool.scalar_one.return_value = 1
    db.execute = AsyncMock(return_value=scalar_bool)
    assert _run(access_repo.has_permission(db, uid, 'add_worker')) is True
    assert _run(access_repo.is_supervisor_assigned_to_site(db, uid, uuid4())) is True

    sup_list = MagicMock()
    sup_list.mappings.return_value.all.return_value = [{'id': uid, 'name': 's'}]
    db.execute = AsyncMock(return_value=sup_list)
    assert len(_run(access_repo.list_supervisors(db))) == 1

    sup_detail = MagicMock()
    sup_detail.mappings.return_value.one_or_none.return_value = {'id': uid, 'name': 's'}
    db.execute = AsyncMock(return_value=sup_detail)
    assert _run(access_repo.get_supervisor_detail(db, uid))['id'] == uid

    site_list = MagicMock()
    site_list.mappings.return_value.all.return_value = [{'site_id': uuid4()}]
    db.execute = AsyncMock(return_value=site_list)
    assert len(_run(access_repo.list_assigned_site_ids(db, uid))) == 1


def test_access_control_repository_user_not_found() -> None:
    db = MagicMock()
    none_row = MagicMock()
    none_row.mappings.return_value.one_or_none.return_value = None
    db.execute = AsyncMock(return_value=none_row)
    assert _run(access_repo.get_user_by_id(db, uuid4())) is None


def test_auth_service_email_password_flows(monkeypatch) -> None:
    db = MagicMock()
    tenant = TenantContext(tenant_id=uuid4(), schema_name='t1')
    user_id = uuid4()
    user = {'id': user_id, 'name': 'U', 'email': 'u@example.com', 'role': 'CONTRACTOR', 'password_hash': hash_password('Password123')}

    monkeypatch.setattr(auth_service, 'set_tenant_search_path', AsyncMock())
    monkeypatch.setattr(auth_service.auth_repo, 'get_user_by_email', AsyncMock(return_value=None))
    monkeypatch.setattr(auth_service.auth_repo, 'create_contractor_user', AsyncMock(return_value=user_id))
    monkeypatch.setattr(auth_service.auth_repo, 'get_user_by_id', AsyncMock(return_value=user))
    monkeypatch.setattr(auth_service, 'send_email', lambda *_a, **_k: None)
    out = _run(auth_service.invite_contractor(db, tenant, InviteContractorRequest(name='CC', email='u@example.com', phone='99999999')))
    assert out['id'] == str(user_id)

    monkeypatch.setattr(auth_service.auth_repo, 'get_user_by_email', AsyncMock(return_value=user))
    out2 = _run(auth_service.resend_set_password_link(db, tenant, ResendSetPasswordLinkRequest(email='u@example.com')))
    assert 'message' in out2

    tok = create_set_password_token(tenant_id=str(tenant.tenant_id), user_id=str(user_id), email='u@example.com')
    monkeypatch.setattr(tenants_service, 'get_tenant_context', AsyncMock(return_value=tenant))
    monkeypatch.setattr(auth_service.auth_repo, 'get_user_by_id', AsyncMock(return_value=user))
    monkeypatch.setattr(auth_service.auth_repo, 'update_password_hash', AsyncMock())
    assert _run(auth_service.set_password(db, SetPasswordRequest(token=tok, new_password='Password123')))['message'] == 'Password set successfully'

    login = _run(auth_service.login_with_password(db, tenant, EmailLoginRequest(email='u@example.com', password='Password123')))
    assert login['token_type'] == 'bearer'

    bad_user = {'id': user_id, 'email': 'u@example.com', 'password_hash': hash_password('Password123')}
    monkeypatch.setattr(auth_service.auth_repo, 'get_user_by_email', AsyncMock(return_value=bad_user))
    with pytest.raises(HTTPException):
        _run(auth_service.login_with_password(db, tenant, EmailLoginRequest(email='u@example.com', password='WrongPass123')))

    monkeypatch.setattr(auth_service.auth_repo, 'get_user_by_email', AsyncMock(return_value={'id': user_id, 'email': 'u@example.com', 'password_hash': None}))
    with pytest.raises(HTTPException):
        _run(auth_service.login_with_password(db, tenant, EmailLoginRequest(email='u@example.com', password='Password123')))

    with pytest.raises(HTTPException):
        _run(auth_service.set_password(db, SetPasswordRequest(token='bad.token', new_password='Password123')))


def test_auth_service_additional_error_branches(monkeypatch) -> None:
    db = MagicMock()
    tenant = TenantContext(tenant_id=uuid4(), schema_name='t1')
    user_id = uuid4()
    monkeypatch.setattr(auth_service, 'set_tenant_search_path', AsyncMock())
    monkeypatch.setattr(auth_service.auth_repo, 'get_user_by_email', AsyncMock(return_value=None))
    monkeypatch.setattr(auth_service.auth_repo, 'create_contractor_user', AsyncMock(return_value=user_id))
    monkeypatch.setattr(auth_service.auth_repo, 'get_user_by_id', AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        _run(auth_service.invite_contractor(db, tenant, InviteContractorRequest(name='CC', email='u2@example.com', phone='99999999')))

    monkeypatch.setattr(auth_service.auth_repo, 'get_user_by_email', AsyncMock(return_value=None))
    out = _run(auth_service.resend_set_password_link(db, tenant, ResendSetPasswordLinkRequest(email='missing@example.com')))
    assert 'message' in out

    tok = create_set_password_token(tenant_id=str(tenant.tenant_id), user_id=str(user_id), email='u2@example.com')
    monkeypatch.setattr(tenants_service, 'get_tenant_context', AsyncMock(return_value=tenant))
    monkeypatch.setattr(auth_service.auth_repo, 'get_user_by_id', AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        _run(auth_service.set_password(db, SetPasswordRequest(token=tok, new_password='Password123')))


def test_auth_service_error_paths(monkeypatch) -> None:
    db = MagicMock()
    tenant = TenantContext(tenant_id=uuid4(), schema_name='t1')
    monkeypatch.setattr(auth_service, 'set_tenant_search_path', AsyncMock())
    monkeypatch.setattr(auth_service.auth_repo, 'get_user_by_email', AsyncMock(return_value={'id': uuid4()}))
    with pytest.raises(HTTPException):
        _run(auth_service.invite_contractor(db, tenant, InviteContractorRequest(name='CC', email='u@example.com', phone='99999999')))

    monkeypatch.setattr(auth_service, 'decode_token', lambda _t: {'type': 'access'})
    with pytest.raises(HTTPException):
        _run(auth_service.set_password(db, SetPasswordRequest(token='x', new_password='Password123')))

    monkeypatch.setattr(auth_service, 'decode_token', lambda _t: {'type': 'set_password', 'tenant_id': None, 'user_id': None})
    with pytest.raises(HTTPException):
        _run(auth_service.set_password(db, SetPasswordRequest(token='x', new_password='Password123')))


def test_access_control_service_flows(monkeypatch) -> None:
    db = MagicMock()
    tenant_id = uuid4()
    actor = UserContext(tenant_id=tenant_id, schema_name='t1', user_id=uuid4(), role=UserRole.CONTRACTOR)
    sup_id = uuid4()

    monkeypatch.setattr(access_control_service, 'set_tenant_search_path', AsyncMock())
    monkeypatch.setattr(access_control_service.repo, 'create_supervisor', AsyncMock(return_value=sup_id))
    monkeypatch.setattr(access_control_service.repo, 'get_user_by_id', AsyncMock(return_value={'id': sup_id, 'email': 's@example.com', 'name': 'S', 'role': 'SUPERVISOR'}))
    monkeypatch.setattr(access_control_service.repo, 'upsert_supervisor_permission', AsyncMock())
    monkeypatch.setattr(access_control_service, 'send_set_password_for_user', AsyncMock())
    out = _run(access_control_service.create_supervisor(db, actor, SupervisorCreateRequest(name='SS', email='s@example.com', phone='99999999')))
    assert out == sup_id

    monkeypatch.setattr(access_control_service.repo, 'get_user_by_id', AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        _run(access_control_service.create_supervisor(db, actor, SupervisorCreateRequest(name='SS', email='s@example.com', phone='99999999')))

    monkeypatch.setattr(access_control_service.repo, 'get_user_by_id', AsyncMock(return_value={'id': sup_id, 'role': 'SUPERVISOR'}))
    monkeypatch.setattr(access_control_service.repo, 'upsert_supervisor_permission', AsyncMock())
    _run(access_control_service.set_supervisor_permission(db, actor, sup_id, 'create_task', True))
    with pytest.raises(HTTPException):
        _run(access_control_service.set_supervisor_permission(db, actor, sup_id, 'unknown', True))
    with pytest.raises(HTTPException):
        _run(access_control_service.set_supervisor_permission(db, actor, sup_id, 'add_worker', False))

    monkeypatch.setattr(access_control_service.repo, 'list_supervisor_permissions', AsyncMock(return_value=[{'permission_code': 'create_task', 'is_enabled': True}]))
    perms = _run(access_control_service.list_permissions(db, actor, sup_id))
    assert any(p['permission_code'] == 'add_worker' for p in perms)

    monkeypatch.setattr(access_control_service.repo, 'assign_supervisor_to_site', AsyncMock())
    _run(access_control_service.assign_supervisor_site(db, actor, sup_id, uuid4()))

    monkeypatch.setattr(access_control_service.repo, 'get_user_by_id', AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        _run(access_control_service.assign_supervisor_site(db, actor, sup_id, uuid4()))

    sup_actor = UserContext(tenant_id=tenant_id, schema_name='t1', user_id=sup_id, role=UserRole.SUPERVISOR)
    monkeypatch.setattr(access_control_service.repo, 'has_permission', AsyncMock(return_value=True))
    monkeypatch.setattr(access_control_service.repo, 'is_supervisor_assigned_to_site', AsyncMock(return_value=True))
    _run(access_control_service.require_permission(db, sup_actor, 'add_worker', uuid4()))

    monkeypatch.setattr(access_control_service.repo, 'has_permission', AsyncMock(return_value=False))
    with pytest.raises(HTTPException):
        _run(access_control_service.require_permission(db, sup_actor, 'add_worker', uuid4()))

    monkeypatch.setattr(access_control_service.repo, 'has_permission', AsyncMock(return_value=True))
    monkeypatch.setattr(access_control_service.repo, 'is_supervisor_assigned_to_site', AsyncMock(return_value=False))
    with pytest.raises(HTTPException):
        _run(access_control_service.require_permission(db, sup_actor, 'add_worker', uuid4()))

    monkeypatch.setattr(access_control_service.repo, 'create_worker', AsyncMock(return_value=uuid4()))
    monkeypatch.setattr(access_control_service, 'require_permission', AsyncMock())
    worker_id = _run(
        access_control_service.create_worker(
            db,
            sup_actor,
            WorkerCreateRequest(site_id=uuid4(), name='WW', salary_type='daily', daily_wage='500', phone='99999999'),
        )
    )
    assert isinstance(worker_id, UUID)

    monkeypatch.setattr(access_control_service.repo, 'list_supervisors', AsyncMock(return_value=[{'id': uuid4(), 'name': 'S'}]))
    assert len(_run(access_control_service.list_supervisors(db, actor))) == 1

    monkeypatch.setattr(access_control_service.repo, 'get_supervisor_detail', AsyncMock(return_value={'id': sup_id, 'name': 'S'}))
    monkeypatch.setattr(access_control_service.repo, 'list_assigned_site_ids', AsyncMock(return_value=['a']))
    assert _run(access_control_service.get_supervisor_detail(db, actor, sup_id))['assigned_site_ids'] == ['a']

    monkeypatch.setattr(access_control_service.repo, 'get_supervisor_detail', AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        _run(access_control_service.get_supervisor_detail(db, actor, sup_id))

    non_contractor = UserContext(tenant_id=tenant_id, schema_name='t1', user_id=uuid4(), role=UserRole.SUPERVISOR)
    with pytest.raises(HTTPException):
        _run(access_control_service.list_supervisors(db, non_contractor))

    monkeypatch.setattr(access_control_service.repo, 'get_user_by_id', AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        _run(access_control_service.set_supervisor_permission(db, actor, sup_id, 'create_task', True))
    with pytest.raises(HTTPException):
        _run(access_control_service.list_permissions(db, actor, sup_id))


def test_access_control_service_get_user_context_and_role_not_allowed(monkeypatch) -> None:
    db = MagicMock()
    tenant_id = uuid4()
    tenant_user = UserContext(tenant_id=tenant_id, schema_name='t1', user_id=uuid4(), role=UserRole.CONTRACTOR)
    supervisor_id = uuid4()
    monkeypatch.setattr(access_control_service, 'set_tenant_search_path', AsyncMock())
    monkeypatch.setattr(access_control_service.repo, 'get_user_by_id', AsyncMock(return_value={'id': supervisor_id, 'role': 'SUPERVISOR'}))
    ctx = _run(access_control_service.get_user_context(db, tenant_user, supervisor_id))
    assert ctx.role == UserRole.SUPERVISOR

    monkeypatch.setattr(access_control_service.repo, 'get_user_by_id', AsyncMock(return_value=None))
    with pytest.raises(HTTPException):
        _run(access_control_service.get_user_context(db, tenant_user, supervisor_id))

    bad_actor = UserContext(tenant_id=tenant_id, schema_name='t1', user_id=uuid4(), role=UserRole.ADMIN)
    with pytest.raises(HTTPException):
        _run(access_control_service.require_permission(db, bad_actor, 'add_worker', uuid4()))


def test_sites_service_supervisor_filter_and_get_permission(monkeypatch) -> None:
    from app.services import sites_service

    db = MagicMock()
    sup_id = uuid4()
    actor = UserContext(tenant_id=uuid4(), schema_name='t1', user_id=sup_id, role=UserRole.SUPERVISOR)
    site_a = {'id': uuid4(), 'status': 'active'}
    site_b = {'id': uuid4(), 'status': 'active'}

    monkeypatch.setattr(sites_service, 'set_tenant_search_path', AsyncMock())
    monkeypatch.setattr(sites_service.repo, 'list_sites', AsyncMock(return_value=[site_a, site_b]))
    monkeypatch.setattr(sites_service.access_repo, 'is_supervisor_assigned_to_site', AsyncMock(side_effect=[True, False]))
    rows = _run(sites_service.list_sites(db, actor))
    assert len(rows) == 1

    monkeypatch.setattr(sites_service.repo, 'get_site', AsyncMock(return_value=site_a))
    monkeypatch.setattr(sites_service, 'require_permission', AsyncMock())
    _run(sites_service.get_site(db, actor, UUID(str(site_a['id']))))
    assert sites_service.require_permission.await_count == 1


def test_email_send_with_tls_and_login(monkeypatch) -> None:
    sent = {}

    class _Settings:
        smtp_host = 'localhost'
        smtp_port = 1025
        smtp_use_tls = True
        smtp_username = 'user'
        smtp_password = 'pass'
        smtp_from_email = 'no-reply@buildtrack.local'

    class _SMTP:
        def __init__(self, *_a, **_k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def starttls(self):
            sent['tls'] = True

        def login(self, *_a):
            sent['login'] = True

        def send_message(self, _msg):
            sent['sent'] = True

    monkeypatch.setattr(email_utils, 'get_settings', lambda: _Settings())
    monkeypatch.setattr('smtplib.SMTP', _SMTP)
    email_utils.send_email('to@example.com', 'Subject', 'Body')
    assert sent == {'tls': True, 'login': True, 'sent': True}


def test_dependencies_user_from_bearer_and_header(monkeypatch) -> None:
    tenant = TenantContext(tenant_id=uuid4(), schema_name='t1')
    db = object()
    claims = {'tenant_id': str(tenant.tenant_id), 'user_id': str(uuid4()), 'role': 'SUPERVISOR'}
    token = jwt.encode(claims, get_settings().jwt_secret_key, algorithm=get_settings().jwt_algorithm)
    user = _run(dependencies.get_current_user(tenant=tenant, db=db, authorization=f'Bearer {token}', x_user_id=None))
    assert user.role == UserRole.SUPERVISOR

    bad_claims = {'tenant_id': str(uuid4()), 'user_id': str(uuid4()), 'role': 'SUPERVISOR'}
    bad_token = jwt.encode(bad_claims, get_settings().jwt_secret_key, algorithm=get_settings().jwt_algorithm)
    with pytest.raises(HTTPException):
        _run(dependencies.get_current_user(tenant=tenant, db=db, authorization=f'Bearer {bad_token}', x_user_id=None))

    with pytest.raises(HTTPException):
        _run(dependencies.get_current_user(tenant=tenant, db=db, authorization='Bearer bad', x_user_id=None))

    monkeypatch.setattr(dependencies, 'get_user_context', AsyncMock(return_value=UserContext(tenant_id=tenant.tenant_id, schema_name='t1', user_id=uuid4(), role=UserRole.SUPERVISOR)))
    hdr_user = _run(dependencies.get_current_user(tenant=tenant, db=db, authorization=None, x_user_id=str(uuid4())))
    assert hdr_user.role == UserRole.SUPERVISOR

    with pytest.raises(HTTPException):
        _run(dependencies.get_current_user(tenant=tenant, db=db, authorization=None, x_user_id='bad-uuid'))


def test_api_endpoints_direct_for_new_auth_and_role_modules(monkeypatch) -> None:
    db = object()
    tenant = TenantContext(tenant_id=uuid4(), schema_name='t1')
    actor = UserContext(tenant_id=tenant.tenant_id, schema_name=tenant.schema_name, user_id=uuid4(), role=UserRole.CONTRACTOR)
    uid = uuid4()

    monkeypatch.setattr(auth_api, 'invite_contractor', AsyncMock(return_value={'id': str(uid)}))
    assert _run(auth_api.invite_contractor_endpoint(InviteContractorRequest(name='CC', email='c@example.com', phone='99999999'), tenant, db))['id'] == str(uid)
    monkeypatch.setattr(auth_api, 'resend_set_password_link', AsyncMock(return_value={'message': 'ok'}))
    assert _run(auth_api.resend_set_password_link_endpoint(ResendSetPasswordLinkRequest(email='c@example.com'), tenant, db))['message'] == 'ok'
    monkeypatch.setattr(auth_api, 'set_password', AsyncMock(return_value={'message': 'ok'}))
    assert _run(auth_api.set_password_endpoint(SetPasswordRequest(token='t', new_password='Password123'), db))['message'] == 'ok'
    monkeypatch.setattr(auth_api, 'login_with_password', AsyncMock(return_value={'token_type': 'bearer'}))
    assert _run(auth_api.login_endpoint(EmailLoginRequest(email='c@example.com', password='Password123'), tenant, db))['token_type'] == 'bearer'

    monkeypatch.setattr(contractor_api, 'create_supervisor', AsyncMock(return_value=uid))
    assert _run(contractor_api.create_supervisor_endpoint(SupervisorCreateRequest(name='SS', email='s@example.com', phone='99999999'), actor, db)) == {'id': str(uid)}
    monkeypatch.setattr(contractor_api, 'list_supervisors', AsyncMock(return_value=[{'id': str(uid)}]))
    assert _run(contractor_api.list_supervisors_endpoint(actor, db))[0]['id'] == str(uid)
    monkeypatch.setattr(contractor_api, 'get_supervisor_detail', AsyncMock(return_value={'id': str(uid)}))
    assert _run(contractor_api.get_supervisor_detail_endpoint(uid, actor, db))['id'] == str(uid)
    monkeypatch.setattr(contractor_api, 'list_permissions', AsyncMock(return_value=[{'permission_code': 'add_worker', 'is_enabled': True}]))
    assert _run(contractor_api.list_supervisor_permissions_endpoint(uid, actor, db))[0]['permission_code'] == 'add_worker'
    monkeypatch.setattr(contractor_api, 'set_supervisor_permission', AsyncMock(return_value=None))
    assert _run(
        contractor_api.update_supervisor_permissions_endpoint(uid, SupervisorPermissionUpdateRequest(permission_code='create_task', is_enabled=True), actor, db)
    ) == {'message': 'Updated'}
    monkeypatch.setattr(contractor_api, 'assign_supervisor_site', AsyncMock(return_value=None))
    assert _run(contractor_api.assign_supervisor_site_endpoint(uid, uuid4(), actor, db)) == {'message': 'Assigned'}

    monkeypatch.setattr(supervisor_api, 'create_worker', AsyncMock(return_value=uid))
    assert (
        _run(
            supervisor_api.create_worker_endpoint(
                WorkerCreateRequest(site_id=uuid4(), name='WW', salary_type='daily', daily_wage='500', phone='99999999'),
                actor,
                db,
            )
        )
        == {'id': str(uid)}
    )


def test_tenants_service_integrity_error_reraise(monkeypatch) -> None:
    db = object()
    payload = SubscriptionCreateRequest(
        tenant_id=uuid4(),
        plan_name='STARTER',
        start_date=datetime.now(timezone.utc).date(),
        end_date=(datetime.now(timezone.utc) + timedelta(days=1)).date(),
        is_active=True,
        extra_sites_count=0,
    )
    monkeypatch.setattr(tenants_service.repo, 'plan_exists', AsyncMock(return_value=True))
    err = IntegrityError('stmt', {}, Exception('other_constraint'))
    monkeypatch.setattr(tenants_service.repo, 'upsert_subscription', AsyncMock(side_effect=err))
    with pytest.raises(IntegrityError):
        _run(tenants_service.create_subscription(db, payload))
