from fastapi import APIRouter

from app.api.routes import businesses, export, geocode, health, leads, notes, routes, saved_leads

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(geocode.router, prefix="/geocode", tags=["geocode"])
api_router.include_router(routes.router, prefix="/routes", tags=["routes"])
api_router.include_router(leads.router, prefix="/routes", tags=["leads"])
api_router.include_router(businesses.router, prefix="/businesses", tags=["businesses"])
api_router.include_router(export.router, prefix="/export", tags=["export"])
api_router.include_router(saved_leads.router, prefix="/saved-leads", tags=["saved-leads"])
api_router.include_router(notes.router, prefix="/notes", tags=["notes"])
