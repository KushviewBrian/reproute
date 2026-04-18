from fastapi import APIRouter

from app.api.routes import admin_import, businesses, enrichment, export, geocode, health, leads, notes, routes, saved_leads, validation

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(geocode.router, prefix="/geocode", tags=["geocode"])
api_router.include_router(routes.router, prefix="/routes", tags=["routes"])
api_router.include_router(leads.router, prefix="/routes", tags=["leads"])
api_router.include_router(businesses.router, prefix="/businesses", tags=["businesses"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(saved_leads.router, prefix="/saved-leads", tags=["saved-leads"])
api_router.include_router(notes.router, prefix="/notes", tags=["notes"])
api_router.include_router(admin_import.router, prefix="/admin/import", tags=["admin-import"])
api_router.include_router(validation.lead_router, prefix="/leads", tags=["validation"])
api_router.include_router(validation.admin_router, prefix="/admin/validation", tags=["validation-admin"])
api_router.include_router(enrichment.router, prefix="/leads", tags=["enrichment"])
