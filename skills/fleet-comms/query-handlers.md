# Query Handlers

Reference for handling incoming queries on the asset inbox channel.

## Query: `status`

Returns current operational status.

**Params:** None

**Response data:**
```json
{
  "status": "OPERATIONAL",
  "hour_meter": 12849.5,
  "fuel_estimate_pct": 65,
  "last_activity": "2024-01-15T10:00:00Z",
  "concerns": []
}
```

**How to gather:**
1. Read `SOUL.md` → `hour_meter.current`
2. Calculate fuel estimate from last fill and consumption rate
3. Read `memory/YYYY-MM-DD.md` for last activity timestamp
4. Check for any active flags or concerns

---

## Query: `load_history`

Returns loading/dumping records for a date.

**Params:**
- `date` (required): "today", "yesterday", or "YYYY-MM-DD"
- `include_weights` (optional): Include tonnage if available

**Response data:**
```json
{
  "loads": [
    {"time": "08:15", "material": "overburden", "truck": "RT-001", "tons": 180},
    {"time": "09:30", "material": "ore", "truck": "HT-044", "tons": 165}
  ],
  "total_loads": 2,
  "total_tons": 345
}
```

**How to gather:**
1. Resolve date ("today" → current date)
2. Read `memory/YYYY-MM-DD.md`
3. Extract all entries matching "load" or "dump" patterns
4. Aggregate totals

---

## Query: `fuel_status`

Returns current fuel level estimate.

**Params:** None

**Response data:**
```json
{
  "tank_capacity": 680,
  "estimated_level": 442,
  "estimated_pct": 65,
  "last_fill": {
    "liters": 180,
    "hours": 12840,
    "timestamp": "2024-01-15T06:00:00Z"
  },
  "hours_until_empty": 15.8
}
```

**How to gather:**
1. Read `SOUL.md` → `fuel` section
2. Calculate current estimate: `last_fill - (hours_delta × consumption_rate)`
3. Calculate hours remaining: `estimated_level / consumption_rate`

---

## Query: `hours`

Returns current hour meter reading.

**Params:** None

**Response data:**
```json
{
  "current": 12849.5,
  "last_updated": "2024-01-15T10:00:00Z"
}
```

**How to gather:**
1. Read `SOUL.md` → `hour_meter.current`

---

## Query: `location`

Returns last known GPS position.

**Params:** None

**Response data:**
```json
{
  "lat": -23.5505,
  "lon": 46.6333,
  "accuracy_m": 5,
  "timestamp": "2024-01-15T10:00:00Z",
  "source": "gps_hub"
}
```

**How to gather:**
1. Read `SOUL.md` → `location` section
2. Include timestamp to indicate freshness

---

## Query: `availability`

Returns whether asset can accept work.

**Params:**
- `work_type` (optional): Type of work being requested

**Response data:**
```json
{
  "available": true,
  "status": "OPERATIONAL",
  "constraints": [],
  "estimated_until": null
}
```

Or if unavailable:
```json
{
  "available": false,
  "status": "MAINTENANCE",
  "constraints": ["scheduled_service"],
  "estimated_until": "2024-01-15T14:00:00Z",
  "reason": "500-hour service in progress"
}
```

**How to gather:**
1. Check current status from `SOUL.md`
2. Check for any blocking concerns
3. Check maintenance schedule

---

## Query: `consumption_stats`

Returns fuel consumption statistics.

**Params:**
- `period` (optional): "day", "week", "month" (default: "week")

**Response data:**
```json
{
  "period": "week",
  "average_rate": 28.5,
  "min_rate": 24.2,
  "max_rate": 33.1,
  "total_liters": 4850,
  "total_hours": 170,
  "sample_count": 12
}
```

**How to gather:**
1. Read `SOUL.md` → `consumption_samples`
2. Filter by requested period
3. Calculate statistics

---

## Query: `maintenance_status`

Returns upcoming and recent maintenance.

**Params:** None

**Response data:**
```json
{
  "next_service": {
    "type": "500-hour",
    "due_hours": 13000,
    "hours_remaining": 150.5
  },
  "recent_maintenance": [
    {"date": "2024-01-10", "type": "daily_inspection", "notes": "All OK"}
  ],
  "open_issues": []
}
```

**How to gather:**
1. Read `SOUL.md` → `maintenance` section
2. Calculate hours until next service
3. Read recent memory entries for maintenance records

---

## Unknown Query

If query type is not recognized:

**Response:**
```json
{
  "error": "unknown_query",
  "message": "Query type 'foo' not recognized",
  "available_queries": ["status", "load_history", "fuel_status", "hours", "location", "availability", "consumption_stats", "maintenance_status"]
}
```
