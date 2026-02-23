from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi.testclient import TestClient


def _bootstrap_site_flow(client: TestClient, tenant_headers: dict[str, str]) -> tuple[str, str]:
    project = client.post(
        '/api/v1/projects',
        headers=tenant_headers,
        json={
            'name': 'Apartment Tower A',
            'location': 'Pune',
            'estimated_budget': '1000000.00',
        },
    )
    assert project.status_code == 200
    project_id = project.json()['id']

    site = client.post(
        '/api/v1/sites',
        headers=tenant_headers,
        json={'project_id': project_id, 'status': 'active'},
    )
    assert site.status_code == 200
    site_id = site.json()['id']
    return project_id, site_id


def test_auth_send_verify_and_refresh(client: TestClient) -> None:
    send = client.post('/api/v1/auth/send-otp', json={'phone': '9999999999'})
    assert send.status_code == 200
    otp = send.json()['otp_for_dev']

    verify = client.post('/api/v1/auth/verify-otp', json={'phone': '9999999999', 'otp': otp})
    assert verify.status_code == 200
    verify_body = verify.json()
    assert verify_body['token_type'] == 'bearer'
    assert 'access_token' in verify_body
    assert 'refresh_token' in verify_body

    refresh = client.post('/api/v1/auth/refresh-token', json={'subject': '9999999999'})
    assert refresh.status_code == 200
    refresh_body = refresh.json()
    assert refresh_body['token_type'] == 'bearer'
    assert 'access_token' in refresh_body


def test_tenant_create_and_manual_subscription(client: TestClient) -> None:
    tenant_resp = client.post(
        '/api/v1/tenants',
        json={
            'name': 'Contractor Sub Test',
            'schema_name': f'tsubmanual{uuid4().hex[:8]}',
            'billing_cycle': 'MONTHLY',
        },
    )
    assert tenant_resp.status_code == 200
    tenant_id = tenant_resp.json()['tenant_id']

    period_start = datetime.now(timezone.utc) - timedelta(days=30)
    period_end = datetime.now(timezone.utc) - timedelta(days=15)
    sub_resp = client.post(
        '/api/v1/tenants/subscription',
        json={
            'tenant_id': tenant_id,
            'billing_cycle': 'MONTHLY',
            'status': 'EXPIRED',
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'trial_end': None,
        },
    )
    assert sub_resp.status_code == 200
    assert 'subscription_id' in sub_resp.json()


def test_projects_endpoints(client: TestClient, tenant_headers: dict[str, str]) -> None:
    create = client.post(
        '/api/v1/projects',
        headers=tenant_headers,
        json={
            'name': 'Project API Test',
            'location': 'Mumbai',
            'estimated_budget': '500000.00',
        },
    )
    assert create.status_code == 200
    project_id = create.json()['id']

    listing = client.get('/api/v1/projects', headers=tenant_headers)
    assert listing.status_code == 200
    assert len(listing.json()) >= 1

    detail = client.get(f'/api/v1/projects/{project_id}', headers=tenant_headers)
    assert detail.status_code == 200
    assert detail.json()['id'] == project_id


def test_sites_endpoints(client: TestClient, tenant_headers: dict[str, str]) -> None:
    project_id, site_id = _bootstrap_site_flow(client, tenant_headers)

    listing = client.get('/api/v1/sites', headers=tenant_headers)
    assert listing.status_code == 200
    assert any(site['id'] == site_id for site in listing.json())

    update = client.put(f'/api/v1/sites/{site_id}', headers=tenant_headers, json={'status': 'paused'})
    assert update.status_code == 200
    assert update.json()['message'] == 'Updated'

    _ = project_id


def test_materials_endpoints(client: TestClient, tenant_headers: dict[str, str]) -> None:
    _, site_id = _bootstrap_site_flow(client, tenant_headers)

    material = client.post(
        '/api/v1/materials',
        headers=tenant_headers,
        json={'name': 'Cement', 'unit': 'bag', 'default_unit_cost': '350'},
    )
    assert material.status_code == 200
    material_id = material.json()['id']

    tx = client.post(
        '/api/v1/material-transactions',
        headers=tenant_headers,
        json={
            'site_id': site_id,
            'material_id': material_id,
            'quantity_received': '100',
            'quantity_used': '40',
            'unit_cost': '350',
        },
    )
    assert tx.status_code == 200

    summary = client.get(f'/api/v1/site/{site_id}/materials-summary', headers=tenant_headers)
    assert summary.status_code == 200
    assert len(summary.json()) == 1
    assert float(summary.json()[0]['remaining_stock']) == 60.0


def test_tasks_endpoints(client: TestClient, tenant_headers: dict[str, str]) -> None:
    _, site_id = _bootstrap_site_flow(client, tenant_headers)

    task = client.post(
        '/api/v1/tasks',
        headers=tenant_headers,
        json={
            'site_id': site_id,
            'title': 'Foundation work',
            'status': 'in_progress',
            'progress_percent': 50,
        },
    )
    assert task.status_code == 200
    task_id = task.json()['id']

    update = client.put(
        f'/api/v1/tasks/{task_id}',
        headers=tenant_headers,
        json={'progress_percent': 70},
    )
    assert update.status_code == 200

    listing = client.get(f'/api/v1/site/{site_id}/tasks', headers=tenant_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_expenses_endpoints(client: TestClient, tenant_headers: dict[str, str]) -> None:
    _, site_id = _bootstrap_site_flow(client, tenant_headers)

    expense = client.post(
        '/api/v1/expenses',
        headers=tenant_headers,
        json={
            'site_id': site_id,
            'category': 'Labor',
            'amount': '20000',
            'description': 'Weekly labor payout',
        },
    )
    assert expense.status_code == 200

    listing = client.get(f'/api/v1/site/{site_id}/expenses', headers=tenant_headers)
    assert listing.status_code == 200
    assert len(listing.json()) == 1


def test_dashboard_summary_endpoint(client: TestClient, tenant_headers: dict[str, str]) -> None:
    _, site_id = _bootstrap_site_flow(client, tenant_headers)

    material = client.post('/api/v1/materials', headers=tenant_headers, json={'name': 'Steel', 'unit': 'kg'})
    material_id = material.json()['id']

    client.post(
        '/api/v1/material-transactions',
        headers=tenant_headers,
        json={
            'site_id': site_id,
            'material_id': material_id,
            'quantity_received': '50',
            'quantity_used': '20',
            'unit_cost': '80',
        },
    )
    client.post(
        '/api/v1/tasks',
        headers=tenant_headers,
        json={'site_id': site_id, 'title': 'Slab work', 'status': 'in_progress', 'progress_percent': 60},
    )
    client.post(
        '/api/v1/expenses',
        headers=tenant_headers,
        json={'site_id': site_id, 'category': 'Machinery', 'amount': '5000'},
    )

    summary = client.get('/api/v1/dashboard/summary', headers=tenant_headers)
    assert summary.status_code == 200
    body = summary.json()
    assert body['total_sites'] == 1
    assert body['active_sites'] == 1
    assert body['total_expense'] == 5000.0
    assert body['total_material_cost'] == 1600.0
    assert body['overall_progress_percentage'] == 60.0


def test_material_transaction_validation(client: TestClient, tenant_headers: dict[str, str]) -> None:
    _, site_id = _bootstrap_site_flow(client, tenant_headers)

    material = client.post('/api/v1/materials', headers=tenant_headers, json={'name': 'Bricks', 'unit': 'pcs'})
    material_id = material.json()['id']

    invalid = client.post(
        '/api/v1/material-transactions',
        headers=tenant_headers,
        json={
            'site_id': site_id,
            'material_id': material_id,
            'quantity_received': '0',
            'quantity_used': '0',
        },
    )
    assert invalid.status_code == 422


def test_protected_route_requires_tenant_header(client: TestClient) -> None:
    response = client.get('/api/v1/projects')
    assert response.status_code == 400
    assert 'Missing tenant header' in response.json()['detail']


def test_invalid_tenant_uuid_header(client: TestClient) -> None:
    response = client.get('/api/v1/projects', headers={'X-Tenant-ID': 'not-a-uuid'})
    assert response.status_code == 400
    assert 'Invalid tenant UUID' in response.json()['detail']


def test_inactive_subscription_blocks_access(
    client: TestClient,
    tenant_headers: dict[str, str],
    expire_subscription,
) -> None:
    create = client.post(
        '/api/v1/projects',
        headers=tenant_headers,
        json={'name': 'Allowed first project', 'location': 'Mumbai'},
    )
    assert create.status_code == 200

    expire_subscription(tenant_headers['X-Tenant-ID'])
    blocked = client.get('/api/v1/projects', headers=tenant_headers)
    assert blocked.status_code == 402
