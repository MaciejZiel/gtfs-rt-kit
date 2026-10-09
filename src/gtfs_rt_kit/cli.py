"""Command-line interface: ``gtfs-rt-kit vehicles|trip-updates|alerts SOURCE``."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, TextIO

from . import __version__
from .decode import parse_feed
from .delay import trip_delays
from .errors import GtfsRtKitError
from .matching import MatchedVehicle, RouteHint, filter_by_route, match_vehicles
from .models import Feed
from .retry import RetryPolicy
from .serialize import to_jsonable
from .static import StaticGtfs
from .warsaw import route_from_vehicle_id

__all__ = ["main"]


def _is_url(source: str) -> bool:
    return source.startswith(("http://", "https://"))


def _read_source(source: str, args: argparse.Namespace) -> bytes:
    if source == "-":
        return sys.stdin.buffer.read()
    if not _is_url(source):
        try:
            return Path(source).read_bytes()
        except OSError as error:
            raise GtfsRtKitError(f"cannot read {source}: {error.strerror}") from error
    try:
        from .client import GtfsRtClient
    except ImportError as error:
        raise GtfsRtKitError(str(error)) from error
    retry = RetryPolicy(attempts=args.retries + 1)
    with GtfsRtClient(timeout=args.timeout, retry=retry) as client:
        return client.fetch_bytes(source)


def _load_static(args: argparse.Namespace) -> StaticGtfs | None:
    if args.static is None:
        return None
    return StaticGtfs(_read_source(args.static, args))


def _route_hint(args: argparse.Namespace) -> RouteHint | None:
    return route_from_vehicle_id if args.warsaw else None


def _table(rows: Sequence[Sequence[str]], headers: Sequence[str], out: TextIO) -> None:
    widths = [len(header) for header in headers]
    for row in rows:
        widths = [max(width, len(cell)) for width, cell in zip(widths, row, strict=True)]
    for row in (headers, *rows):
        out.write(
            "  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)).rstrip()
        )
        out.write("\n")


def _time(value: datetime | None) -> str:
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if value else "-"


def _matched(feed: Feed, args: argparse.Namespace, static: StaticGtfs | None) -> list[Any]:
    hint = _route_hint(args)
    if static is not None:
        matched = match_vehicles(feed, static, route_hint=hint)
    else:
        matched = [
            MatchedVehicle(
                vehicle=vehicle, route_key=vehicle.route_id or (hint(vehicle) if hint else None)
            )
            for vehicle in feed.vehicles
        ]
    if args.route:
        matched = filter_by_route(matched, args.route)
    return matched


def _cmd_vehicles(args: argparse.Namespace, out: TextIO) -> int:
    feed = parse_feed(_read_source(args.source, args))
    static = _load_static(args)
    matched = _matched(feed, args, static)
    if args.json:
        payload = [
            {
                **to_jsonable(item.vehicle),
                "vehicle_id": item.vehicle.vehicle_id,
                "line": item.line,
                "mode": item.mode,
                "headsign": item.trip.headsign if item.trip else None,
            }
            for item in matched
        ]
        json.dump(payload, out, ensure_ascii=False, indent=2)
        out.write("\n")
        return 0
    rows = []
    for item in matched:
        position = item.vehicle.position
        rows.append(
            [
                item.vehicle.vehicle_id,
                item.line or "-",
                item.vehicle.trip_id or "-",
                f"{position.latitude:.5f}" if position else "-",
                f"{position.longitude:.5f}" if position else "-",
                _time(item.vehicle.timestamp),
            ]
        )
    _table(rows, ["VEHICLE", "LINE", "TRIP", "LAT", "LON", "TIMESTAMP"], out)
    out.write(f"{len(rows)} vehicle(s), feed time {_time(feed.timestamp)}\n")
    return 0


def _cmd_trip_updates(args: argparse.Namespace, out: TextIO) -> int:
    feed = parse_feed(_read_source(args.source, args))
    static = _load_static(args)
    updates = list(feed.trip_updates)
    if args.route:
        wanted = args.route.casefold()

        def route_keys(route_id: str | None, trip_id: str | None) -> set[str]:
            keys = {route_id} if route_id else set()
            if static is not None:
                trip = static.trip(trip_id) if trip_id else None
                route = static.find_route(route_id or (trip.route_id if trip else ""))
                if route is not None:
                    keys.update({route.route_id, route.short_name})
            return {key.casefold() for key in keys if key}

        updates = [u for u in updates if wanted in route_keys(u.route_id, u.trip_id)]
    results = []
    for update in updates:
        delays = trip_delays(update, static) if static is not None else ()
        results.append((update, delays))
    if args.json:
        payload = [
            {**to_jsonable(update), "stop_delays": to_jsonable(delays)}
            for update, delays in results
        ]
        json.dump(payload, out, ensure_ascii=False, indent=2)
        out.write("\n")
        return 0
    rows = []
    for update, delays in results:
        known = [d.delay for d in delays if d.delay is not None]
        feed_delays = [
            event.delay
            for stu in update.stop_time_updates
            for event in (stu.arrival, stu.departure)
            if event is not None and event.delay is not None
        ]
        delay = update.delay
        if known:
            delay = known[-1]
        elif delay is None and feed_delays:
            delay = feed_delays[-1]
        rows.append(
            [
                update.trip_id or "-",
                update.route_id or "-",
                str(len(update.stop_time_updates)),
                f"{delay:+d}s" if delay is not None else "-",
            ]
        )
    _table(rows, ["TRIP", "ROUTE", "STOPS", "DELAY"], out)
    out.write(f"{len(rows)} trip update(s), feed time {_time(feed.timestamp)}\n")
    return 0


def _cmd_alerts(args: argparse.Namespace, out: TextIO) -> int:
    feed = parse_feed(_read_source(args.source, args))
    alerts = list(feed.alerts)
    if args.route:
        alerts = [alert for alert in alerts if alert.affects_route(args.route)]
    if args.active or args.at is not None:
        moment = args.at or datetime.now(timezone.utc)
        alerts = [alert for alert in alerts if alert.is_active(moment)]
    if args.json:
        json.dump(to_jsonable(alerts), out, ensure_ascii=False, indent=2)
        out.write("\n")
        return 0
    for alert in alerts:
        header = alert.header_text.text(args.lang) if alert.header_text else None
        routes = sorted({s.route_id for s in alert.informed_entities if s.route_id})
        stops = sorted({s.stop_id for s in alert.informed_entities if s.stop_id})
        out.write(f"[{alert.effect}] {header or '(no header)'}\n")
        if routes:
            out.write(f"  routes: {', '.join(routes)}\n")
        if stops:
            out.write(f"  stops: {', '.join(stops)}\n")
    out.write(f"{len(alerts)} alert(s), feed time {_time(feed.timestamp)}\n")
    return 0


def _aware_datetime(value: str) -> datetime:
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid ISO 8601 time: {value!r}") from error
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def build_parser() -> argparse.ArgumentParser:
    """The argument parser of the ``gtfs-rt-kit`` command."""
    parser = argparse.ArgumentParser(
        prog="gtfs-rt-kit",
        description="Inspect GTFS-Realtime feeds from a URL, a local file or stdin ('-').",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, metavar="COMMAND")

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("source", help="feed URL, path to a .pb file, or '-' for stdin")
    common.add_argument("--route", help="only show this route (id or short name)")
    common.add_argument("--json", action="store_true", help="print JSON instead of a table")
    common.add_argument(
        "--timeout", type=float, default=10.0, help="HTTP timeout in seconds (default: 10)"
    )
    common.add_argument(
        "--retries", type=int, default=2, help="retries for failed downloads (default: 2)"
    )

    schedule = argparse.ArgumentParser(add_help=False)
    schedule.add_argument(
        "--static", metavar="GTFS_ZIP", help="static GTFS zip (path or URL) to match against"
    )

    vehicles = commands.add_parser(
        "vehicles", parents=[common, schedule], help="list vehicle positions"
    )
    vehicles.add_argument(
        "--warsaw",
        action="store_true",
        help="derive the line from Warsaw-style vehicle ids (V/<line>/<brigade>)",
    )
    vehicles.set_defaults(handler=_cmd_vehicles)

    trip_updates = commands.add_parser(
        "trip-updates", parents=[common, schedule], help="list trip updates and delays"
    )
    trip_updates.set_defaults(handler=_cmd_trip_updates)

    alerts = commands.add_parser("alerts", parents=[common], help="list service alerts")
    alerts.add_argument("--lang", help="preferred language of alert texts, e.g. 'pl'")
    alerts.add_argument("--active", action="store_true", help="only alerts active right now")
    alerts.add_argument(
        "--at",
        type=_aware_datetime,
        metavar="ISO_TIME",
        help="only alerts active at this ISO 8601 time (UTC if no offset is given)",
    )
    alerts.set_defaults(handler=_cmd_alerts)
    return parser


def main(argv: Sequence[str] | None = None, *, out: TextIO | None = None) -> int:
    """Run the CLI and return its exit code."""
    args = build_parser().parse_args(argv)
    if args.retries < 0:
        build_parser().error("--retries must not be negative")
    try:
        result: int = args.handler(args, out or sys.stdout)
    except GtfsRtKitError as error:
        print(f"gtfs-rt-kit: error: {error}", file=sys.stderr)
        return 1
    return result


def main_entry() -> None:  # pragma: no cover - thin console-script wrapper
    """Console-script entry point."""
    sys.exit(main())
