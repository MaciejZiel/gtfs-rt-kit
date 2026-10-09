"""Matching realtime vehicles to static trips and routes."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .models import Feed, VehiclePosition
from .static import Route, StaticGtfs, Trip

__all__ = ["MatchedVehicle", "RouteHint", "filter_by_route", "match_vehicle", "match_vehicles"]

RouteHint = Callable[[VehiclePosition], "str | None"]
"""A callable deriving a route id or short name from a vehicle when the feed omits it."""


@dataclass(frozen=True, slots=True)
class MatchedVehicle:
    """A vehicle position enriched with its scheduled trip and route."""

    vehicle: VehiclePosition
    trip: Trip | None = None
    route: Route | None = None
    route_key: str | None = None

    @property
    def line(self) -> str | None:
        """Passenger-facing line name: route short name, else the raw route key."""
        if self.route is not None:
            return self.route.name
        return self.route_key

    @property
    def mode(self) -> str | None:
        """Transport mode of the matched route."""
        return self.route.mode if self.route is not None else None


def match_vehicle(
    vehicle: VehiclePosition, static: StaticGtfs, *, route_hint: RouteHint | None = None
) -> MatchedVehicle:
    """Resolve the trip and route of ``vehicle``.

    Resolution order for the route: the trip descriptor's ``route_id``, the route of
    the matched trip, then ``route_hint(vehicle)``. Each candidate is looked up as a
    route id first and as a route short name second.
    """
    trip = static.trip(vehicle.trip_id) if vehicle.trip_id else None
    candidates = [vehicle.route_id, trip.route_id if trip else None]
    if route_hint is not None:
        candidates.append(route_hint(vehicle))
    route: Route | None = None
    route_key: str | None = None
    for candidate in candidates:
        if not candidate:
            continue
        route_key = route_key or candidate
        route = static.find_route(candidate)
        if route is not None:
            break
    return MatchedVehicle(vehicle=vehicle, trip=trip, route=route, route_key=route_key)


def match_vehicles(
    vehicles: Feed | Iterable[VehiclePosition],
    static: StaticGtfs,
    *,
    route_hint: RouteHint | None = None,
) -> list[MatchedVehicle]:
    """Match every vehicle of a feed (or an iterable of vehicles)."""
    items = vehicles.vehicles if isinstance(vehicles, Feed) else vehicles
    return [match_vehicle(vehicle, static, route_hint=route_hint) for vehicle in items]


def filter_by_route(matched: Iterable[MatchedVehicle], route: str) -> list[MatchedVehicle]:
    """Keep vehicles whose route id, short name or raw route key equals ``route``.

    The comparison is case-insensitive, so ``"n91"`` matches the night line ``N91``.
    """
    wanted = route.casefold()
    result = []
    for item in matched:
        keys = {item.route_key}
        if item.route is not None:
            keys.update({item.route.route_id, item.route.short_name})
        if any(key is not None and key.casefold() == wanted for key in keys):
            result.append(item)
    return result
