from datetime import date, timedelta
from uuid import uuid4

from fastapi.testclient import TestClient


def _create_project(client: TestClient, headers: dict[str, str], name: str = 'Payroll Project') -> str:
    response = client.post(
        '/api/v1/projects',
        headers=headers,
        json={'name': name, 'location': 'Pune', 'estimated_budget': '350000.00'},
    )
    assert response.status_code == 200
    return response.json()['id']


def _create_site(client: TestClient, headers: dict[str, str], project_id: str, status: str = 'active') -> str:
    response = client.post('/api/v1/sites', headers=headers, json={'project_id': project_id, 'status': status})
    assert response.status_code == 200
    return response.json()['id']


def _create_worker(
    client: TestClient,
    headers: dict[str, str],
    site_id: str,
    name: str,
    salary_type: str = 'daily',
    daily_wage: str | None = '1000',
    monthly_salary: str | None = None,
) -> str:
    payload = {
        'site_id': site_id,
        'name': name,
        'salary_type': salary_type,
        'daily_wage': daily_wage,
        'monthly_salary': monthly_salary,
        'is_attendance_based': True,
    }
    response = client.post('/api/v1/workers', headers=headers, json=payload)
    assert response.status_code == 200
    return response.json()['id']


def test_workforce_daily_salary_summary_and_settlement(client: TestClient, tenant_headers: dict[str, str]) -> None:
    project_id = _create_project(client, tenant_headers)
    site_id = _create_site(client, tenant_headers, project_id)
    worker_id = _create_worker(client, tenant_headers, site_id, 'Daily Worker', salary_type='daily', daily_wage='1000')

    day_1 = date(2026, 3, 1)
    day_2 = day_1 + timedelta(days=1)
    day_3 = day_1 + timedelta(days=2)

    a1 = client.post(
        '/api/v1/attendance',
        headers=tenant_headers,
        json={'worker_id': worker_id, 'site_id': site_id, 'date': day_1.isoformat(), 'status': 'present'},
    )
    assert a1.status_code == 200

    a2 = client.post(
        '/api/v1/attendance',
        headers=tenant_headers,
        json={'worker_id': worker_id, 'site_id': site_id, 'date': day_2.isoformat(), 'status': 'half_day'},
    )
    assert a2.status_code == 200

    a3 = client.post(
        '/api/v1/attendance',
        headers=tenant_headers,
        json={'worker_id': worker_id, 'site_id': site_id, 'date': day_3.isoformat(), 'status': 'paid_leave'},
    )
    assert a3.status_code == 200

    dup = client.post(
        '/api/v1/attendance',
        headers=tenant_headers,
        json={'worker_id': worker_id, 'site_id': site_id, 'date': day_1.isoformat(), 'status': 'present'},
    )
    assert dup.status_code == 409

    bonus = client.post(
        '/api/v1/bonus',
        headers=tenant_headers,
        json={'worker_id': worker_id, 'amount': '200', 'date': day_3.isoformat(), 'note': 'Performance'},
    )
    assert bonus.status_code == 200

    summary = client.get(
        f'/api/v1/salary-summary?worker_id={worker_id}&from={day_1.isoformat()}&to={day_3.isoformat()}',
        headers=tenant_headers,
    )
    assert summary.status_code == 200
    body = summary.json()
    assert body['total_days'] == 3
    assert body['present_days'] == 1
    assert body['base_salary'] == 2500.0
    assert body['total_bonus'] == 200.0
    assert body['total_salary'] == 2700.0
    assert body['total_paid'] == 0.0
    assert body['pending_salary'] == 2700.0
    assert body['status'] == 'UNPAID'

    settle = client.post(
        '/api/v1/salary-settlements',
        headers=tenant_headers,
        json={
            'worker_id': worker_id,
            'from_date': day_1.isoformat(),
            'to_date': day_3.isoformat(),
            'is_paid': True,
            'paid_on': day_3.isoformat(),
        },
    )
    assert settle.status_code == 200

    summary_paid = client.get(
        f'/api/v1/salary-summary?worker_id={worker_id}&from={day_1.isoformat()}&to={day_3.isoformat()}',
        headers=tenant_headers,
    )
    assert summary_paid.status_code == 200
    assert summary_paid.json()['status'] == 'PAID'
    assert summary_paid.json()['is_paid'] is True


def test_workforce_supervisor_permissions_and_site_scope(client: TestClient, tenant_headers: dict[str, str]) -> None:
    sup_response = client.post(
        '/api/v1/contractor/supervisors',
        headers=tenant_headers,
        json={'name': 'Supervisor One', 'email': f'sup-{uuid4().hex[:8]}@example.com', 'phone': f'91{uuid4().hex[:8]}'},
    )
    assert sup_response.status_code == 200
    supervisor_id = sup_response.json()['id']

    project_id = _create_project(client, tenant_headers, 'Scope Project')
    site_a = _create_site(client, tenant_headers, project_id)
    site_b = _create_site(client, tenant_headers, project_id)

    assign = client.post(f'/api/v1/contractor/supervisors/{supervisor_id}/sites/{site_a}', headers=tenant_headers)
    assert assign.status_code == 200

    worker_a = _create_worker(client, tenant_headers, site_a, 'A Worker')
    _ = _create_worker(client, tenant_headers, site_b, 'B Worker')

    sup_headers = {**tenant_headers, 'X-User-ID': supervisor_id}

    sup_workers = client.get('/api/v1/workers', headers=sup_headers)
    assert sup_workers.status_code == 200
    assert len(sup_workers.json()) == 1
    assert sup_workers.json()[0]['id'] == worker_a

    mark_attendance = client.post(
        '/api/v1/attendance',
        headers=sup_headers,
        json={'worker_id': worker_a, 'site_id': site_a, 'date': date(2026, 3, 10).isoformat(), 'status': 'present'},
    )
    assert mark_attendance.status_code == 200

    bonus_forbidden = client.post(
        '/api/v1/bonus',
        headers=sup_headers,
        json={'worker_id': worker_a, 'amount': '100', 'date': date(2026, 3, 10).isoformat(), 'note': 'N/A'},
    )
    assert bonus_forbidden.status_code == 403

    bad_site_attendance = client.post(
        '/api/v1/attendance',
        headers=sup_headers,
        json={'worker_id': worker_a, 'site_id': site_b, 'date': date(2026, 3, 11).isoformat(), 'status': 'present'},
    )
    assert bad_site_attendance.status_code in {400, 403}
