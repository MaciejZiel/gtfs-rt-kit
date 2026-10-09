# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Typed, immutable models for GTFS-Realtime feeds: vehicle positions, trip updates
  and service alerts, with UTC datetimes and enum names.
- `parse_feed()` / `load_feed()` decoding protobuf payloads via `gtfs-realtime-bindings`.
- `GtfsRtClient` and `AsyncGtfsRtClient` (httpx, optional `http` extra) with timeouts,
  exponential backoff, `Retry-After` support and `FeedFetchError` reporting.
- `RetryPolicy` to configure attempts, backoff and retryable status codes.
- `StaticGtfs`: lazy loader for static GTFS zip archives (agencies, stops, routes, trips,
  stop times) from a path, bytes or a file object.
- Vehicle matching to trips and routes (`match_vehicles`, `filter_by_route`) with pluggable
  route hints, including a Warsaw (ZTM) helper in `gtfs_rt_kit.warsaw`.
- Delay computation against the schedule (`trip_delays`, `estimate_vehicle_delay`),
  handling times past midnight and daylight-saving changes.
- Project skeleton: packaging with hatchling, MIT license, CI on Python 3.10-3.13.
