# Drop-off Implementation - Consolidated Status

**Last Updated:** 2025-12-26

## Quick Status Overview

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 1: DocTypes & Controllers | ✅ COMPLETED | 1-truck design implemented |
| Phase 2: API Endpoints | ✅ COMPLETED | api/v1/dropoff.py created |
| Phase 3: API Testing | 🔜 NEXT SESSION | Test all endpoints |
| Phase 4: Terminal UI | 🔜 PENDING | Manual weight entry mode needed |

---

## NEXT SESSION TODO

### 1. Test All APIs
- [ ] Test api/v1/dropoff.py endpoints
- [ ] Test api/v1/pos.py session heartbeat
- [ ] Test scheduler cron job (close_idle_sessions)
- [ ] Run `bench migrate` to apply DocType changes

### 2. Terminal Manual Weight Mode
- [ ] Add option to run terminal WITHOUT WebSocket scale connection
- [ ] Allow manual weight entry for testing/fallback
- [ ] Scale integration should be optional, not required

---

## Architecture: 1-Truck-Per-Dropoff Design ✅ IMPLEMENTED

### Design Decision
- **1 Dropoff = 1 Truck** (license_plate directly on Dropoff form)
- **Truck Weight DocType** for weighing history (standalone, links to Dropoff)

### Controllers
- dropoff.py: Edge cases 13.3, 13.12, 13.16, 13.20, 13.21, 13.22
- allocate_weights_if_closing() - Pro-rata weight allocation
- update_pos_orders_if_closed() - Syncs fulfillment

---

## Phase 2: API Endpoints ✅ COMPLETED

### api/v1/dropoff.py - Core functions
- lookup_dropoff(query)
- get_dropoff_by_qr(qr_data)
- get_dropoff_details(dropoff)
- record_truck_weight(dropoff, weight_type, weight, scale, session)
- record_scrap_weight(session, dropoff, items, ...)
- get_dropoff_verification(dropoff)
- complete_dropoff(dropoff)
- load_scrap_weight(scrap_weight_id)
- mark_truck_reweighed(dropoff, reason)
- save_truck_remarks(dropoff, remarks)
- save_truck_photo(dropoff, photo)

### api/v1/pos.py - Session Management
- update_session_activity(session) - heartbeat for timeout tracking

### scheduler.py - Cron Jobs
- close_idle_sessions() - runs every 15 mins, closes sessions idle > 90 mins

### Dropoff Status Flow
Draft → Scheduled → Weighing → Unloading → Verified/Needs Attention → Closed

---

*Reference: docs/DROPOFF_ARCHITECTURE.md for full design decisions*
