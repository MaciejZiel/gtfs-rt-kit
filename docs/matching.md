# Matching and delays

## Vehicles to trips and routes

```python
from gtfs_rt_kit import filter_by_route, match_vehicles

matched = match_vehicles(feed, gtfs)
for item in filter_by_route(matched, "15"):
    print(item.vehicle.vehicle_id, item.line, item.mode, item.trip and item.trip.headsign)
```

The route of a vehicle is resolved from its trip descriptor's `route_id`, then from the
static trip, then from an optional `route_hint` callable. Each candidate is looked up as
a route id first and as a short name second. `filter_by_route()` compares route ids,
short names and raw route keys case-insensitively.

Some feeds encode the line elsewhere. The Warsaw feed, for instance, uses vehicle ids
like `V/15/7`; pass `route_hint=gtfs_rt_kit.warsaw.route_from_vehicle_id`, or write your
own `Callable[[VehiclePosition], str | None]`.

## Delays of a trip update

```python
from gtfs_rt_kit import trip_delays

update = feed.trip_update_for(trip_id)
for stop in trip_delays(update, gtfs):
    print(stop.stop_id, stop.event, stop.scheduled, stop.predicted, stop.delay)
```

For each stop time update the arrival is used when present, otherwise the departure.
An explicit `delay` in the feed wins; otherwise the delay is `time - scheduled`. Skipped
stops are flagged with `skipped=True`.

The service date comes from the trip's `start_date`, falling back to the local date of
the update's timestamp, or can be passed explicitly with `service_date=`. Scheduled
times follow the GTFS definition ("noon minus 12 hours"), so trips past midnight and
days with a daylight-saving change are handled correctly.

## Delay of a vehicle

`estimate_vehicle_delay(vehicle, gtfs)` compares a vehicle's timestamp with the
scheduled time at its current stop. It is a rough estimate that only applies when the
vehicle is stopped at (or reported at) a stop of a known trip; otherwise it returns
`None`.
