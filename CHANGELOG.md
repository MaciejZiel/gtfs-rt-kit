# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Typed, immutable models for GTFS-Realtime feeds: vehicle positions, trip updates
  and service alerts, with UTC datetimes and enum names.
- `parse_feed()` / `load_feed()` decoding protobuf payloads via `gtfs-realtime-bindings`.
- Project skeleton: packaging with hatchling, MIT license, CI on Python 3.10-3.13.
