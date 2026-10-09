"""Decoding of GTFS-Realtime protobuf payloads into typed models."""

from __future__ import annotations

from datetime import datetime, timezone
from os import PathLike
from pathlib import Path

from google.protobuf.message import DecodeError
from google.transit import gtfs_realtime_pb2 as pb

from .errors import FeedDecodeError
from .models import (
    Alert,
    EntitySelector,
    Feed,
    FeedHeader,
    Position,
    StopTimeEvent,
    StopTimeUpdate,
    TimeRange,
    TranslatedString,
    Translation,
    TripDescriptor,
    TripUpdate,
    VehicleDescriptor,
    VehiclePosition,
)

__all__ = ["load_feed", "parse_feed"]


def parse_feed(data: bytes) -> Feed:
    """Decode a serialized GTFS-Realtime ``FeedMessage``.

    Raises:
        FeedDecodeError: if ``data`` is not a valid feed message.
    """
    message = pb.FeedMessage()
    try:
        message.ParseFromString(data)
    except DecodeError as error:
        raise FeedDecodeError(f"invalid GTFS-Realtime payload: {error}") from error
    if not message.HasField("header"):
        raise FeedDecodeError("invalid GTFS-Realtime payload: missing feed header")
    return _feed(message)


def load_feed(path: str | PathLike[str]) -> Feed:
    """Read and decode a GTFS-Realtime feed stored in a local file."""
    return parse_feed(Path(path).read_bytes())


def _feed(message: pb.FeedMessage) -> Feed:
    vehicles: list[VehiclePosition] = []
    trip_updates: list[TripUpdate] = []
    alerts: list[Alert] = []
    deleted: list[str] = []
    for entity in message.entity:
        if entity.is_deleted:
            deleted.append(entity.id)
            continue
        if entity.HasField("vehicle"):
            vehicles.append(_vehicle_position(entity.id, entity.vehicle))
        if entity.HasField("trip_update"):
            trip_updates.append(_trip_update(entity.id, entity.trip_update))
        if entity.HasField("alert"):
            alerts.append(_alert(entity.id, entity.alert))
    return Feed(
        header=_header(message.header),
        vehicles=tuple(vehicles),
        trip_updates=tuple(trip_updates),
        alerts=tuple(alerts),
        deleted_entity_ids=tuple(deleted),
    )


def _header(header: pb.FeedHeader) -> FeedHeader:
    return FeedHeader(
        gtfs_realtime_version=header.gtfs_realtime_version,
        incrementality=pb.FeedHeader.Incrementality.Name(header.incrementality),
        timestamp=_time(header.timestamp) if header.HasField("timestamp") else None,
        feed_version=header.feed_version if header.HasField("feed_version") else None,
    )


def _vehicle_position(entity_id: str, vehicle: pb.VehiclePosition) -> VehiclePosition:
    enums = pb.VehiclePosition
    return VehiclePosition(
        entity_id=entity_id,
        trip=_trip(vehicle.trip) if vehicle.HasField("trip") else None,
        vehicle=_vehicle(vehicle.vehicle) if vehicle.HasField("vehicle") else None,
        position=_position(vehicle.position) if vehicle.HasField("position") else None,
        current_stop_sequence=(
            vehicle.current_stop_sequence if vehicle.HasField("current_stop_sequence") else None
        ),
        stop_id=vehicle.stop_id if vehicle.HasField("stop_id") else None,
        current_status=(
            enums.VehicleStopStatus.Name(vehicle.current_status)
            if vehicle.HasField("current_status")
            else None
        ),
        timestamp=_time(vehicle.timestamp) if vehicle.HasField("timestamp") else None,
        congestion_level=(
            enums.CongestionLevel.Name(vehicle.congestion_level)
            if vehicle.HasField("congestion_level")
            else None
        ),
        occupancy_status=(
            enums.OccupancyStatus.Name(vehicle.occupancy_status)
            if vehicle.HasField("occupancy_status")
            else None
        ),
        occupancy_percentage=(
            vehicle.occupancy_percentage if vehicle.HasField("occupancy_percentage") else None
        ),
    )


def _trip(trip: pb.TripDescriptor) -> TripDescriptor:
    return TripDescriptor(
        trip_id=trip.trip_id if trip.HasField("trip_id") else None,
        route_id=trip.route_id if trip.HasField("route_id") else None,
        direction_id=trip.direction_id if trip.HasField("direction_id") else None,
        start_time=trip.start_time if trip.HasField("start_time") else None,
        start_date=trip.start_date if trip.HasField("start_date") else None,
        schedule_relationship=(
            pb.TripDescriptor.ScheduleRelationship.Name(trip.schedule_relationship)
            if trip.HasField("schedule_relationship")
            else None
        ),
    )


def _vehicle(vehicle: pb.VehicleDescriptor) -> VehicleDescriptor:
    return VehicleDescriptor(
        id=vehicle.id if vehicle.HasField("id") else None,
        label=vehicle.label if vehicle.HasField("label") else None,
        license_plate=vehicle.license_plate if vehicle.HasField("license_plate") else None,
    )


def _position(position: pb.Position) -> Position:
    return Position(
        latitude=position.latitude,
        longitude=position.longitude,
        bearing=position.bearing if position.HasField("bearing") else None,
        odometer=position.odometer if position.HasField("odometer") else None,
        speed=position.speed if position.HasField("speed") else None,
    )


def _trip_update(entity_id: str, update: pb.TripUpdate) -> TripUpdate:
    return TripUpdate(
        entity_id=entity_id,
        trip=_trip(update.trip),
        vehicle=_vehicle(update.vehicle) if update.HasField("vehicle") else None,
        stop_time_updates=tuple(_stop_time_update(stu) for stu in update.stop_time_update),
        timestamp=_time(update.timestamp) if update.HasField("timestamp") else None,
        delay=update.delay if update.HasField("delay") else None,
    )


def _stop_time_update(update: pb.TripUpdate.StopTimeUpdate) -> StopTimeUpdate:
    return StopTimeUpdate(
        stop_sequence=update.stop_sequence if update.HasField("stop_sequence") else None,
        stop_id=update.stop_id if update.HasField("stop_id") else None,
        arrival=_event(update.arrival) if update.HasField("arrival") else None,
        departure=_event(update.departure) if update.HasField("departure") else None,
        schedule_relationship=pb.TripUpdate.StopTimeUpdate.ScheduleRelationship.Name(
            update.schedule_relationship
        ),
    )


def _event(event: pb.TripUpdate.StopTimeEvent) -> StopTimeEvent:
    return StopTimeEvent(
        delay=event.delay if event.HasField("delay") else None,
        time=_time(event.time) if event.HasField("time") else None,
        uncertainty=event.uncertainty if event.HasField("uncertainty") else None,
        scheduled_time=(_time(event.scheduled_time) if event.HasField("scheduled_time") else None),
    )


def _alert(entity_id: str, alert: pb.Alert) -> Alert:
    return Alert(
        entity_id=entity_id,
        active_periods=tuple(_time_range(period) for period in alert.active_period),
        informed_entities=tuple(_selector(selector) for selector in alert.informed_entity),
        cause=pb.Alert.Cause.Name(alert.cause),
        effect=pb.Alert.Effect.Name(alert.effect),
        severity_level=pb.Alert.SeverityLevel.Name(alert.severity_level),
        url=_translated(alert.url) if alert.HasField("url") else None,
        header_text=_translated(alert.header_text) if alert.HasField("header_text") else None,
        description_text=(
            _translated(alert.description_text) if alert.HasField("description_text") else None
        ),
    )


def _time_range(period: pb.TimeRange) -> TimeRange:
    return TimeRange(
        start=_time(period.start) if period.HasField("start") else None,
        end=_time(period.end) if period.HasField("end") else None,
    )


def _selector(selector: pb.EntitySelector) -> EntitySelector:
    return EntitySelector(
        agency_id=selector.agency_id if selector.HasField("agency_id") else None,
        route_id=selector.route_id if selector.HasField("route_id") else None,
        route_type=selector.route_type if selector.HasField("route_type") else None,
        direction_id=selector.direction_id if selector.HasField("direction_id") else None,
        trip=_trip(selector.trip) if selector.HasField("trip") else None,
        stop_id=selector.stop_id if selector.HasField("stop_id") else None,
    )


def _translated(value: pb.TranslatedString) -> TranslatedString:
    return TranslatedString(
        translations=tuple(
            Translation(
                text=item.text,
                language=item.language if item.HasField("language") else None,
            )
            for item in value.translation
        )
    )


def _time(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, timezone.utc)
