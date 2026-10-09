# Any GTFS-Realtime feed

Nothing in the library is specific to one city. This script works with any feed URL
(vehicle positions, trip updates and alerts, separately or combined) and, given a
static GTFS zip, lists the most delayed trips. It uses the asynchronous client.

Public feeds are listed in the [Mobility Database](https://mobilitydatabase.org/).
Many agencies require an API key; pass it with `headers=` (or as a query parameter in
the URL, depending on the provider).

```python
--8 < --"examples/generic_feed.py"
```
