# BuildTrack Backend (FastAPI, Multi-tenant)

## Setup
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

## Run
```bash
uvicorn app.main:app --reload
```

## Initialize public schema + seed
```bash
python -m app.db.bootstrap
```

## What is included
- Public schema with minimal subscription model (`tenants`, `plans`, `tenant_subscriptions`, `tenant_add_ons`)
- Tenant onboarding API that creates contractor schema + tenant tables from code
- Tenant-aware APIs for projects, sites, materials, tasks, expenses, dashboard
- Subscription validity check before protected APIs

## Refactored Architecture
```text
app/
  api/
    router.py                  # central router registration
  core/
    config.py                  # app settings
    dependencies.py            # tenant/subscription dependencies
    security.py                # jwt helpers
  db/
    session.py                 # async session + request transaction scope
    sql.py                     # bootstrap + tenant schema SQL statements
    bootstrap.py               # initialize public schema
  models/
    base.py                    # SQLAlchemy base
    enums.py                   # shared enums
    public.py                  # public schema models (subscription domain)
    tenant.py                  # tenant-domain ORM references
  modules/
    <domain>/
      router.py                # HTTP layer
      service.py               # business logic
      repository.py            # SQL access
      schemas.py               # request/response contracts
```

## Test
```bash
pytest -q
```
