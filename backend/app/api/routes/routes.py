from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user
from app.db.session import get_db
from app.models.route import Route
from app.models.route_candidate import RouteCandidate
from app.models.user import User
from app.schemas.route import CreateRouteRequest, CreateRouteResponse, PatchRouteRequest, RouteSummaryResponse
from app.services.lead_service import refresh_route_candidates_and_scores
from app.services.routing_service import get_route_multi
from app.utils.geo import linestring_wkt_from_geojson
from app.utils.rate_limit import enforce_rate_limit
router = APIRouter()


@router.post("", response_model=CreateRouteResponse)
async def create_route(
    payload: CreateRouteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> CreateRouteResponse:
    await enforce_rate_limit(f"rl:create_route:{user.id}", limit=30, window_seconds=60)

    all_waypoints = (
        [(payload.origin_lat, payload.origin_lng)]
        + [(w.lat, w.lng) for w in payload.waypoints]
        + [(payload.destination_lat, payload.destination_lng)]
    )
    route_response = await get_route_multi(all_waypoints)

    feature = route_response.get("features", [{}])[0]
    geometry = feature.get("geometry")
    if not geometry:
        raise HTTPException(status_code=502, detail="Routing provider returned no geometry")

    properties = feature.get("properties", {}).get("summary", {})
    distance = int(properties.get("distance", 0))
    duration = int(properties.get("duration", 0))

    route = Route(
        user_id=user.id,
        origin_label=payload.origin_label,
        destination_label=payload.destination_label,
        origin_lat=payload.origin_lat,
        origin_lng=payload.origin_lng,
        destination_lat=payload.destination_lat,
        destination_lng=payload.destination_lng,
        route_geom=linestring_wkt_from_geojson(geometry),
        route_distance_meters=distance,
        route_duration_seconds=duration,
        corridor_width_meters=payload.corridor_width_meters,
        ors_response_json=route_response,
    )
    db.add(route)
    await db.commit()

    lead_count = await refresh_route_candidates_and_scores(db, route.id, payload.corridor_width_meters)

    return CreateRouteResponse(
        route_id=route.id,
        route_distance_meters=distance,
        route_duration_seconds=duration,
        lead_count=lead_count,
        route_geojson=geometry,
    )


@router.get("/{route_id}", response_model=RouteSummaryResponse)
async def get_route_summary(
    route_id: UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RouteSummaryResponse:
    await enforce_rate_limit(f"rl:get_route:{user.id}", limit=180, window_seconds=60)
    result = await db.execute(select(Route).where(Route.id == route_id, Route.user_id == user.id))
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    candidate_count = await db.scalar(select(func.count()).select_from(RouteCandidate).where(RouteCandidate.route_id == route.id))

    return RouteSummaryResponse(
        route_id=route.id,
        origin_label=route.origin_label,
        destination_label=route.destination_label,
        route_distance_meters=route.route_distance_meters,
        route_duration_seconds=route.route_duration_seconds,
        candidate_count=int(candidate_count or 0),
    )


@router.patch("/{route_id}", response_model=RouteSummaryResponse)
async def patch_route(
    route_id: UUID,
    payload: PatchRouteRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> RouteSummaryResponse:
    await enforce_rate_limit(f"rl:patch_route:{user.id}", limit=60, window_seconds=60)
    result = await db.execute(select(Route).where(Route.id == route_id, Route.user_id == user.id))
    route = result.scalar_one_or_none()
    if not route:
        raise HTTPException(status_code=404, detail="Route not found")

    route.corridor_width_meters = payload.corridor_width_meters
    await db.commit()

    await refresh_route_candidates_and_scores(db, route.id, payload.corridor_width_meters)

    candidate_count = await db.scalar(select(func.count()).select_from(RouteCandidate).where(RouteCandidate.route_id == route.id))
    return RouteSummaryResponse(
        route_id=route.id,
        origin_label=route.origin_label,
        destination_label=route.destination_label,
        route_distance_meters=route.route_distance_meters,
        route_duration_seconds=route.route_duration_seconds,
        candidate_count=int(candidate_count or 0),
    )
