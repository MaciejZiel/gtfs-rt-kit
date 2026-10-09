# Warsaw (ZTM)

Warsaw's public transport data is republished as GTFS and GTFS-Realtime by
[Mikołaj Kuranowski](https://mkuran.pl/gtfs/) under CC0. The URLs are available as
constants in [`gtfs_rt_kit.warsaw`][gtfs_rt_kit.warsaw]:

| Constant | Content |
| --- | --- |
| `GTFS_URL` | static timetable (`warsaw.zip`, about 100 MB) |
| `VEHICLES_URL` | vehicle positions, refreshed every few seconds |
| `ALERTS_URL` | service alerts (Polish and English) |

The vehicle feed identifies vehicles as `V/<line>/<brigade>` and does not fill
`route_id`, so pass `route_hint=warsaw.route_from_vehicle_id` when matching.

## Quick look from the shell

```bash
gtfs-rt-kit vehicles https://mkuran.pl/gtfs/warsaw/vehicles.pb --warsaw --route 15
gtfs-rt-kit alerts https://mkuran.pl/gtfs/warsaw/alerts.pb --lang pl --active
```

## Script

```python
--8 < --"examples/warsaw_live.py"
```
