from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient

RAZORPAY_HEADERS = {'X-Razorpay-Webhook-Secret': 'razorpay_test_secret'}


def _create_project(client: TestClient, headers: dict[str, str], name: str = 'Project X') -> str:
    response = client.post(
        '/api/v1/projects',
        headers=headers,
        json={'name': name, 'location': 'Pune', 'estimated_budget': '250000.00'},
    )
    assert response.status_code == 200
    return response.json()['id']


def _create_site(client: TestClient, headers: dict[str, str], project_id: str, status: str = 'active') -> str:
    response = client.post('/api/v1/sites', headers=headers, json={'project_id': project_id, 'status': status})
    assert response.status_code == 200
    return response.json()['id']


def _create_material(client: TestClient, headers: dict[str, str], name: str = 'Cement') -> str:
    response = client.post('/api/v1/materials', headers=headers, json={'name': name, 'unit': 'bag', 'default_unit_cost': '350'})
    assert response.status_code == 200
    return response.json()['id']


def _create_task(client: TestClient, headers: dict[str, str], site_id: str) -> str:
    response = client.post(
        '/api/v1/tasks',
        headers=headers,
        json={'site_id': site_id, 'title': 'Task One', 'status': 'in_progress', 'progress_percent': 40},
    )
    assert response.status_code == 200
    return response.json()['id']


def test_auth_send_otp_success(client: TestClient) -> None:
    response = client.post('/api/v1/auth/send-otp', json={'phone': '9000000001'})
    assert response.status_code == 200
    assert response.json()['message'] == 'OTP sent'


def test_auth_verify_otp_invalid(client: TestClient) -> None:
    client.post('/api/v1/auth/send-otp', json={'phone': '9000000002'})
    response = client.post('/api/v1/auth/verify-otp', json={'phone': '9000000002', 'otp': '000000'})
    assert response.status_code == 401


def test_auth_refresh_without_subject_uses_default(client: TestClient) -> None:
    response = client.post('/api/v1/auth/refresh-token', json={})
    assert response.status_code == 200
    assert response.json()['token_type'] == 'bearer'


def test_tenant_create_invalid_schema_name(client: TestClient) -> None:
    response = client.post(
        '/api/v1/tenants',
        json={'name': 'Bad Schema Tenant', 'schema_name': 'Invalid-Schema'},
    )
    assert response.status_code == 400


def test_tenant_subscription_create_success(client: TestClient) -> None:
    tenant_resp = client.post(
        '/api/v1/tenants',
        json={'name': 'Subscription Tenant', 'schema_name': f'tsub{uuid4().hex[:8]}'},
    )
    assert tenant_resp.status_code == 200
    tenant_id = tenant_resp.json()['tenant_id']

    start = date.today()
    end = date.today() + timedelta(days=30)
    response = client.post(
        '/api/v1/tenants/subscription',
        headers=RAZORPAY_HEADERS,
        json={
            'tenant_id': tenant_id,
            'plan_name': 'STARTER',
            'start_date': start.isoformat(),
            'end_date': end.isoformat(),
            'is_active': True,
            'extra_sites_count': 0,
        },
    )
    assert response.status_code == 200
    assert 'subscription_id' in response.json()


def test_tenant_subscription_upsert_is_allowed(client: TestClient) -> None:
    tenant_resp = client.post(
        '/api/v1/tenants',
        json={'name': 'Duplicate Sub Tenant', 'schema_name': f'tsubdup{uuid4().hex[:8]}'},
    )
    assert tenant_resp.status_code == 200
    tenant_id = tenant_resp.json()['tenant_id']

    now = date.today()
    future = now + timedelta(days=30)
    first = client.post(
        '/api/v1/tenants/subscription',
        headers=RAZORPAY_HEADERS,
        json={
            'tenant_id': tenant_id,
            'plan_name': 'STARTER',
            'start_date': now.isoformat(),
            'end_date': future.isoformat(),
            'is_active': True,
            'extra_sites_count': 0,
        },
    )
    assert first.status_code == 200
    second = client.post(
        '/api/v1/tenants/subscription',
        headers=RAZORPAY_HEADERS,
        json={
            'tenant_id': tenant_id,
            'plan_name': 'PRO',
            'start_date': now.isoformat(),
            'end_date': future.isoformat(),
            'is_active': True,
            'extra_sites_count': 2,
        },
    )
    assert second.status_code == 200


def test_contractor_supervisor_list_and_detail(client: TestClient, tenant_headers: dict[str, str]) -> None:
    created = client.post(
        '/api/v1/contractor/supervisors',
        headers=tenant_headers,
        json={'name': 'Sup One', 'email': f'sup-{uuid4().hex[:8]}@example.com', 'phone': f'91{uuid4().hex[:8]}'},
    )
    assert created.status_code == 200
    supervisor_id = created.json()['id']

    listing = client.get('/api/v1/contractor/supervisors', headers=tenant_headers)
    assert listing.status_code == 200
    assert any(row['id'] == supervisor_id for row in listing.json())

    detail = client.get(f'/api/v1/contractor/supervisors/{supervisor_id}', headers=tenant_headers)
    assert detail.status_code == 200
    assert detail.json()['id'] == supervisor_id
    assert detail.json()['assigned_site_ids'] == []


def test_projects_create_list_get(client: TestClient, tenant_headers: dict[str, str]) -> None:
    project_id = _create_project(client, tenant_headers, 'Project API Matrix')

    listing = client.get('/api/v1/projects', headers=tenant_headers)
    assert listing.status_code == 200
    assert any(item['id'] == project_id for item in listing.json())

    detail = client.get(f'/api/v1/projects/{project_id}', headers=tenant_headers)
    assert detail.status_code == 200
    assert detail.json()['name'] == 'Project API Matrix'


def test_projects_update_and_delete(client: TestClient, tenant_headers: dict[str, str]) -> None:
    project_id = _create_project(client, tenant_headers, 'Project CRUD')

    update = client.put(
        f'/api/v1/projects/{project_id}',
        headers=tenant_headers,
        json={'name': 'Project CRUD Updated', 'estimated_budget': '99999.00'},
    )
    assert update.status_code == 200
    assert update.json()['message'] == 'Updated'

    detail = client.get(f'/api/v1/projects/{project_id}', headers=tenant_headers)
    assert detail.status_code == 200
    assert detail.json()['name'] == 'Project CRUD Updated'

    delete = client.delete(f'/api/v1/projects/{project_id}', headers=tenant_headers)
    assert delete.status_code == 200
    assert delete.json()['message'] == 'Deleted'

    detail_after_delete = client.get(f'/api/v1/projects/{project_id}', headers=tenant_headers)
    assert detail_after_delete.status_code == 404


def test_projects_get_not_found(client: TestClient, tenant_headers: dict[str, str]) -> None:
    response = client.get(f'/api/v1/projects/{uuid4()}', headers=tenant_headers)
    assert response.status_code == 404


def test_sites_create_list_update(client: TestClient, tenant_headers: dict[str, str]) -> None:
    project_id = _create_project(client, tenant_headers, 'Site Project')
    site_id = _create_site(client, tenant_headers, project_id)

    listing = client.get('/api/v1/sites', headers=tenant_headers)
    assert listing.status_code == 200
    assert any(item['id'] == site_id for item in listing.json())

    update = client.put(f'/api/v1/sites/{site_id}', headers=tenant_headers, json={'status': 'paused'})
    assert update.status_code == 200
    assert update.json()['message'] == 'Updated'


def test_sites_get_and_delete(client: TestClient, tenant_headers: dict[str, str]) -> None:
    project_id = _create_project(client, tenant_headers, 'Site CRUD Project')
    site_id = _create_site(client, tenant_headers, project_id)

    detail = client.get(f'/api/v1/sites/{site_id}', headers=tenant_headers)
    assert detail.status_code == 200
    assert detail.json()['id'] == site_id

    delete = client.delete(f'/api/v1/sites/{site_id}', headers=tenant_headers)
    assert delete.status_code == 200
    assert delete.json()['message'] == 'Deleted'

    detail_after_delete = client.get(f'/api/v1/sites/{site_id}', headers=tenant_headers)
    assert detail_after_delete.status_code == 404


def test_materials_create_transaction_and_summary(client: TestClient, tenant_headers: dict[str, str]) -> None:
    project_id = _create_project(client, tenant_headers, 'Material Project')
    site_id = _create_site(client, tenant_headers, project_id)
    material_id = _create_material(client, tenant_headers, 'Steel')

    tx = client.post(
        '/api/v1/material-transactions',
        headers=tenant_headers,
        json={'site_id': site_id, 'material_id': material_id, 'quantity_received': '120', 'quantity_used': '20', 'unit_cost': '80'},
    )
    assert tx.status_code == 200

    summary = client.get(f'/api/v1/site/{site_id}/materials-summary', headers=tenant_headers)
    assert summary.status_code == 200
    assert len(summary.json()) == 1
    assert float(summary.json()[0]['remaining_stock']) == 100.0


def test_material_transaction_negative_validation(client: TestClient, tenant_headers: dict[str, str]) -> None:
    project_id = _create_project(client, tenant_headers, 'Material Validation Project')
    site_id = _create_site(client, tenant_headers, project_id)
    material_id = _create_material(client, tenant_headers, 'Bricks')

    response = client.post(
        '/api/v1/material-transactions',
        headers=tenant_headers,
        json={'site_id': site_id, 'material_id': material_id, 'quantity_received': '-1', 'quantity_used': '0'},
    )
    assert response.status_code == 422


def test_tasks_create_update_list(client: TestClient, tenant_headers: dict[str, str]) -> None:
    project_id = _create_project(client, tenant_headers, 'Task Project')
    site_id = _create_site(client, tenant_headers, project_id)
    task_id = _create_task(client, tenant_headers, site_id)

    update = client.put(f'/api/v1/tasks/{task_id}', headers=tenant_headers, json={'progress_percent': 75})
    assert update.status_code == 200

    listing = client.get(f'/api/v1/site/{site_id}/tasks', headers=tenant_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_tasks_get_and_delete(client: TestClient, tenant_headers: dict[str, str]) -> None:
    project_id = _create_project(client, tenant_headers, 'Task CRUD Project')
    site_id = _create_site(client, tenant_headers, project_id)
    task_id = _create_task(client, tenant_headers, site_id)

    detail = client.get(f'/api/v1/tasks/{task_id}', headers=tenant_headers)
    assert detail.status_code == 200
    assert detail.json()['id'] == task_id

    delete = client.delete(f'/api/v1/tasks/{task_id}', headers=tenant_headers)
    assert delete.status_code == 200
    assert delete.json()['message'] == 'Deleted'

    detail_after_delete = client.get(f'/api/v1/tasks/{task_id}', headers=tenant_headers)
    assert detail_after_delete.status_code == 404


def test_tasks_validation_failure(client: TestClient, tenant_headers: dict[str, str]) -> None:
    project_id = _create_project(client, tenant_headers, 'Task Validation Project')
    site_id = _create_site(client, tenant_headers, project_id)

    response = client.post(
        '/api/v1/tasks',
        headers=tenant_headers,
        json={'site_id': site_id, 'title': 'Bad progress', 'status': 'in_progress', 'progress_percent': 120},
    )
    assert response.status_code == 422


def test_expenses_create_and_list(client: TestClient, tenant_headers: dict[str, str]) -> None:
    project_id = _create_project(client, tenant_headers, 'Expense Project')
    site_id = _create_site(client, tenant_headers, project_id)

    create = client.post(
        '/api/v1/expenses',
        headers=tenant_headers,
        json={'site_id': site_id, 'category': 'Labor', 'amount': '15000', 'description': 'Wages'},
    )
    assert create.status_code == 200

    listing = client.get(f'/api/v1/site/{site_id}/expenses', headers=tenant_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_expenses_validation_failure(client: TestClient, tenant_headers: dict[str, str]) -> None:
    project_id = _create_project(client, tenant_headers, 'Expense Validation Project')
    site_id = _create_site(client, tenant_headers, project_id)

    response = client.post(
        '/api/v1/expenses',
        headers=tenant_headers,
        json={'site_id': site_id, 'category': 'Fuel', 'amount': '-1'},
    )
    assert response.status_code == 422


def test_dashboard_summary_aggregates(client: TestClient, tenant_headers: dict[str, str]) -> None:
    project_id = _create_project(client, tenant_headers, 'Dashboard Project')
    site_id = _create_site(client, tenant_headers, project_id)
    material_id = _create_material(client, tenant_headers, 'Sand')
    _ = _create_task(client, tenant_headers, site_id)

    client.post(
        '/api/v1/material-transactions',
        headers=tenant_headers,
        json={'site_id': site_id, 'material_id': material_id, 'quantity_received': '60', 'quantity_used': '10', 'unit_cost': '90'},
    )
    client.post(
        '/api/v1/expenses',
        headers=tenant_headers,
        json={'site_id': site_id, 'category': 'Machinery', 'amount': '8000'},
    )

    summary = client.get('/api/v1/dashboard/summary', headers=tenant_headers)
    assert summary.status_code == 200
    body = summary.json()
    assert body['total_sites'] == 1
    assert body['active_sites'] == 1
    assert body['total_expense'] == 8000.0
    assert body['total_material_cost'] == 900.0


def test_missing_tenant_header_returns_400(client: TestClient) -> None:
    response = client.get('/api/v1/projects')
    assert response.status_code == 400


def test_invalid_tenant_header_returns_400(client: TestClient) -> None:
    response = client.get('/api/v1/projects', headers={'X-Tenant-ID': 'bad-uuid'})
    assert response.status_code == 400


def test_unknown_tenant_returns_404(client: TestClient) -> None:
    response = client.get('/api/v1/projects', headers={'X-Tenant-ID': str(uuid4())})
    assert response.status_code == 404


def test_inactive_subscription_is_read_only(client: TestClient, tenant_headers: dict[str, str], expire_subscription) -> None:
    _create_project(client, tenant_headers, 'Subscription Block Project')
    expire_subscription(tenant_headers['X-Tenant-ID'])

    get_response = client.get('/api/v1/projects', headers=tenant_headers)
    assert get_response.status_code == 200
    write_response = client.post('/api/v1/projects', headers=tenant_headers, json={'name': 'Blocked Project'})
    assert write_response.status_code == 402
