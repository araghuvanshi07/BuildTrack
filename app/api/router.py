from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.contractor import router as contractor_router
from app.api.v1.dashboard import router as dashboard_router
from app.api.v1.expenses import router as expenses_router
from app.api.v1.materials import router as materials_router
from app.api.v1.projects import router as projects_router
from app.api.v1.sites import router as sites_router
from app.api.v1.supervisor import router as supervisor_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.tenants import router as tenants_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(tenants_router)
api_router.include_router(projects_router)
api_router.include_router(sites_router)
api_router.include_router(materials_router)
api_router.include_router(tasks_router)
api_router.include_router(expenses_router)
api_router.include_router(dashboard_router)
api_router.include_router(contractor_router)
api_router.include_router(supervisor_router)
