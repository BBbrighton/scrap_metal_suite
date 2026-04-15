# Scrap Metal Suite - Complete User Guide

**Version:** 2.0
**Last Updated:** 2026-04-15
**System Version:** v1.0.0 + Price Lock Settlement

---

## Table of Contents

1. [Business Overview](#1-business-overview)
2. [System Architecture](#2-system-architecture)
3. [Roles & Permissions](#3-roles--permissions)
4. [Complete Business Flow](#4-complete-business-flow)
5. [Module Guide: Price Lock (SMT Price Lock)](#5-module-guide-price-lock-smt-po)
6. [Module Guide: POS Operations](#6-module-guide-pos-operations)
7. [Module Guide: Dropoff & Weighing](#7-module-guide-dropoff--weighing)
8. [Module Guide: Production Sorting](#8-module-guide-production-sorting)
9. [Module Guide: Settlement (SMT Purchase Order)](#9-module-guide-settlement-smt-po-final)
10. [Variance & Verification](#10-variance--verification)
11. [Printing & Documents](#11-printing--documents)
12. [Scheduled Tasks (Cron Jobs)](#12-scheduled-tasks-cron-jobs)
13. [Validation Rules Reference](#13-validation-rules-reference)
14. [Role Guide: POS Operator](#14-role-guide-pos-operator)
15. [Role Guide: Production Worker](#15-role-guide-production-worker)
16. [Role Guide: SMT Accountant](#16-role-guide-smt-accountant)
17. [Role Guide: Manager](#17-role-guide-manager)
18. [Workspaces](#18-workspaces)
19. [Troubleshooting](#19-troubleshooting)
20. [Appendix: Keyboard Shortcuts](#20-appendix-keyboard-shortcuts)

---

## 1. Business Overview

### What is Scrap Metal Suite?

Scrap Metal Suite is a complete system for managing scrap metal purchasing operations. It covers the full lifecycle:

1. **Price commitment** — A supplier agrees to sell specific metals at locked prices
2. **Delivery** — The supplier brings material to the yard by truck
3. **Weighing** — Material is weighed (truck scale + individual item scales)
4. **Sorting & QC** — Production team sorts, grades, and verifies material quality
5. **Settlement** — Accountant reconciles deliveries against price commitments and creates purchase invoices

### Why Not Standard ERPNext Purchase Orders?

Scrap metal has unique properties that break the standard flow:

- **Price is locked before delivery** — Supplier calls in the morning: "lock 10kg copper at 300 THB/kg." Delivery happens days later.
- **Delivered material rarely matches** — Quantities change (re-weighed at yard), grades get downgraded after sorting.
- **Many-to-many relationships** — One delivery can fulfill multiple price commitments. One commitment can be fulfilled across multiple deliveries.
- **Spot pricing** — Material without a price commitment gets priced at the accountant's discretion.

### Key Business Terms

| Term | Meaning |
|------|---------|
| **SMT Price Lock** | Price commitment (Purchase Order). "We'll buy X kg of item Y at Z THB/kg." |
| **POS Order** | Operational record of an expected delivery. Auto-created from SMT Price Lock. |
| **Dropoff** | A single truck delivery event. One truck, one supplier, possibly fulfilling multiple orders. |
| **Scrap Weight** | Individual weighing record for scrap items on the platform scale. |
| **Truck Weight** | Gross (loaded) and tare (empty) weight of the delivery truck. |
| **Production Sorting** | QC step where material is sorted into good items and unwanted items (by grade). |
| **Dropoff Final** | The authoritative record of what was actually received after sorting. |
| **SMT Purchase Order** | Accountant's reconciliation document. Matches deliveries to price commitments. |
| **Spot Rate** | Price set by the accountant for material not covered by any PO. |

---

## 2. System Architecture

### Document Flow

```
SMT Price Lock (Price Lock)
  │
  ├──▶ POS Order (auto-created)
  │         │
  │         ▼
  │    Dropoff (truck arrives)
  │         │
  │    ┌────┼────────────┐
  │    ▼    ▼            ▼
  │  Truck  Scrap     POS Session
  │  Weight Weight    (operator login)
  │    │    │
  │    ▼    ▼
  │    Dropoff (Completed)
  │         │
  │         ▼
  │    Production Sorting
  │    (sort, grade, verify)
  │         │
  │         ▼
  │    Dropoff Final
  │    (good items + unwanted items)
  │         │
  └────────►│
            ▼
       SMT Purchase Order
       (allocate PO rates + spot rates)
            │
            ▼
       Purchase Invoice (Draft)
            │
            ▼
       Payment Entry
```

### Technology

- **Backend:** Frappe Framework (Python) + ERPNext
- **Database:** MariaDB
- **Frontend:** Frappe Desk + Custom web terminals (HTML/JS)
- **Scale Integration:** WebSerial API (Chrome/Edge) for industrial scales
- **Protocols:** STX-M, STX, HP-05 scale communication

---

## 3. Roles & Permissions

### Role Overview

| Role | Purpose | Access Level |
|------|---------|-------------|
| **POS Operator** | Yard staff: weighing, dropoff recording | POS/Dropoff/Weight doctypes |
| **Production Worker** | Sorting team: grade and sort material | Production Sorting, Production Session |
| **Production Manager** | Supervise sorting, override variance | All production doctypes + override |
| **SMT Accountant** | Create POs, settle deliveries, generate invoices | Full on SMT Price Lock/PO Final, read on everything else |
| **SMT Accounting Manager** | Same as Accountant (v1), future: approvals | Same as SMT Accountant |
| **System Manager** | Full access to everything | All doctypes |

### Permission Matrix

**Full Access (Create, Read, Write, Submit, Cancel):**

| DocType | POS Operator | Production Worker | Production Manager | SMT Accountant |
|---------|-------------|-------------------|-------------------|----------------|
| SMT Price Lock | - | - | - | Full |
| SMT Purchase Order | - | - | - | Full |
| POS Order | Full | - | - | - |
| Dropoff | Full | - | - | - |
| Scrap Weight | Full | - | - | - |
| Truck Weight | Full | - | - | - |
| POS Session | Full | - | - | - |
| Production Sorting | - | Full | Full | - |
| Production Session | - | Full | Full | - |
| Dropoff Final | - | Full | Full | - |

**Read-Only Access:**

SMT Accountant and SMT Accounting Manager have read-only access to ALL SMT doctypes (Dropoff, Dropoff Final, Production Sorting, Production Session, Truck Weight, Scrap Weight, Scrap Purchase, POS Order, POS Session, Scale). This allows them to trace the full evidence chain when reconciling.

---

## 4. Complete Business Flow

### Step-by-Step Walkthrough

#### Phase 1: Price Commitment

1. Supplier calls: "I want to lock 10kg copper wire at 300 THB/kg"
2. **SMT Accountant** creates an **SMT Price Lock** in the system:
   - Supplier: ACME Metals
   - Item: Copper Wire, Qty: 10 kg, Rate: 300 THB/kg
   - Optional: set expiry date (auto-expires if supplier doesn't deliver)
3. On submit:
   - PO status → **Open**
   - **POS Order** auto-created with the same items and quantities
   - Yard team can now see the expected delivery

#### Phase 2: Delivery Arrives

4. Supplier drives truck to the yard
5. **POS Operator** opens a POS Session (logs in at terminal)
6. Operator creates a **Dropoff**:
   - Links to the POS Order
   - Enters license plate, scheduled times
   - Expected items auto-populated from order
7. **Truck Weighing:**
   - Truck drives onto platform scale
   - Operator records **Gross Weight** (truck + material)
   - Truck unloads material
   - Operator records **Tare Weight** (empty truck)
   - System calculates **Net Weight** = Gross - Tare
8. **Scrap Weighing:**
   - Individual items weighed on scrap scale
   - Operator records each item's weight
   - System tracks variance between expected and actual
9. Dropoff status transitions: Draft → Scheduled → In Progress → **Completed**

#### Phase 3: Quality Control

10. **Production Worker** opens a Production Session
11. Worker creates a **Production Sorting** linked to the Dropoff:
    - Reviews source items from the Dropoff
    - Sorts into **Good Items** (by grade) and **Unwanted Items** (contaminated, wrong material, etc.)
    - Example: 10kg copper → 9kg Grade A (good) + 1kg Grade B (downgraded)
12. Sorting is submitted
13. **Dropoff Final** auto-populates:
    - Aggregates all sorting results
    - Calculates variance vs truck weight
    - If variance within threshold (default 5%) → status: **Unsettled**
    - If variance exceeds threshold → status: **In Progress** (Needs Review)

#### Phase 4: Settlement

14. **SMT Accountant** creates an **SMT Purchase Order**:
    - Selects supplier: ACME Metals
    - Selects unsettled Dropoff Final(s) to close
    - Builds allocation table:
      - 9kg Copper Grade A → allocate against SMT Price Lock @ 300 THB/kg (rate locked)
      - 1kg Copper Grade B → Spot rate @ 285 THB/kg (accountant sets manually)
    - System validates: all items fully allocated, no over-allocation
15. On submit:
    - PO `settled_qty` updated (9/10 copper → Partially Settled)
    - Dropoff Final → **Settled**
    - **Draft Purchase Invoice** created for 2,985 THB
16. Accountant reviews the Draft PI, sets warehouse, submits
17. Payment Entry created, supplier paid

#### Phase 5: Remaining Delivery

18. Supplier delivers remaining 1kg copper in a second truck
19. Same process: Dropoff → Weigh → Sort → Dropoff Final → PO Final
20. PO `settled_qty` reaches 10/10 → **Fully Settled**

---

## 5. Module Guide: Price Lock (SMT Price Lock)

### Purpose

SMT Price Lock (Scrap Metal Trading Purchase Order) is a price commitment: "We will buy X kg of item Y at Z THB/kg from this supplier."

### Creating an SMT Price Lock

1. Go to **SMT Accounting** workspace → **SMT Price Lock** → **New**
2. Select **Supplier**
3. Set **PO Date** (defaults to today)
4. Optionally set **Expiry Date** (PO auto-expires after this date)
5. Add items:
   | Item | Qty (kg) | Rate (THB/kg) |
   |------|----------|---------------|
   | Copper Wire | 10 | 300 |
   | Aluminum Sheet | 5 | 75 |
6. Total PO Value auto-calculates: 3,375 THB
7. Click **Submit**

### What Happens on Submit

- Status → **Open**
- A **POS Order** is auto-created with:
  - Same supplier
  - Same order date
  - Same items and quantities
  - Status: Pending
- The yard team can now see this expected delivery

### Status Lifecycle

```
Open → Partially Settled → Fully Settled
  ↘ Expired (auto, if expiry_date passes)
  ↘ Cancelled (manual, only if zero settled qty)
```

| Status | Meaning |
|--------|---------|
| **Open** | Submitted, waiting for deliveries |
| **Partially Settled** | Some items settled via PO Final, remaining qty still open |
| **Fully Settled** | All items fully allocated. No more deliveries expected. |
| **Expired** | Past expiry date. Only Open POs expire (not Partially Settled). |
| **Cancelled** | Manually cancelled. Only possible if zero settled quantity. |

### Cancellation Rules

- **Cannot cancel** if any item has settled quantity > 0 → cancel the PO Final(s) first
- On cancel, linked POS Orders with status "Pending" are auto-cancelled
- POS Orders already in progress (Processing/Processed) are NOT cancelled

### Expiry Rules

- Auto-expiry runs daily at 1:00 AM
- Only POs with status **Open** and a set expiry date in the past are expired
- **Partially Settled POs are NEVER auto-expired** — supplier already delivered material
- Expired POs cannot be used in PO Final allocations

---

## 6. Module Guide: POS Operations

### POS Session

Every operator must open a session before working. Sessions track who did what and when.

**Opening a Session:**
1. Navigate to `/pos`
2. Select your POS Profile
3. Click **Open Session**
4. Select a scale (one-time per session)

**Session Rules:**
- One open session per operator at a time
- Session heartbeat tracks activity every 30 seconds
- Idle sessions auto-close after 90 minutes (POS) or 10 minutes (Production)
- Scale is locked to the session — no other operator can use it

**Closing a Session:**
- Click **Close Session** in the terminal
- System calculates session totals (weight count, total weight)
- Scale is released for other operators

### POS Order

POS Orders represent expected deliveries. They can be:
- **Auto-created** from an SMT Price Lock (linked via `smt_price_lock` field)
- **Manually created** by the operator for walk-in suppliers

**Fields:**
| Field | Description |
|-------|-------------|
| Supplier | Who is delivering |
| Order Date | When (auto-filled from PO or today) |
| SMT Price Lock | Link to price commitment (if any) |
| Order Items | Expected items with contracted weights |
| Weighed Items | Actual weights received (auto-filled from Dropoff) |
| Fulfillment % | How much of the order has been delivered |

**Fulfillment Status:**
| % Range | Status |
|---------|--------|
| 0% | Pending |
| 1–97% | Partial |
| 98–102% | Fulfilled |
| >102% | Over-delivered |

### Scale Integration

The system supports industrial scales via WebSerial API (Chrome/Edge only):

**Supported Protocols:**
- **STX-M** — Most common
- **STX** — Standard
- **HP-05** — Chinese scales

**Configuration (Scale DocType):**
| Setting | Typical Value |
|---------|--------------|
| Baud Rate | 9600 |
| Data Bits | 8 |
| Parity | None |
| Stop Bits | 1 |
| Max Capacity | 500 kg (scrap) / 5000 kg (truck) |

---

## 7. Module Guide: Dropoff & Weighing

### Dropoff

A Dropoff represents one truck arriving at the yard. It links to POS Orders and contains all weight records.

**Creating a Dropoff:**
1. Select supplier
2. Link POS Order(s) — one dropoff can fulfill multiple orders
3. Enter license plate
4. Set scheduled start/end times
5. Add expected items (auto-populated from linked orders)

**Status Flow:**
```
Draft → Scheduled → In Progress → Completed
                                   ↘ Cancelled
```

| Transition | Trigger |
|-----------|---------|
| Draft → Scheduled | License plate + scheduled time set |
| Scheduled → In Progress | First weight recorded (truck or scrap) |
| In Progress → Completed | All weights recorded |

**Immutability Rules:**
- Cannot change scheduled start time after status moves past Scheduled
- Cannot remove linked orders from a Completed dropoff
- Cannot clear license plate if weights are recorded

### Truck Weighing

Two weights are needed per truck:

1. **Gross Weight** — Truck fully loaded with material
2. **Tare Weight** — Empty truck after unloading

**Net Weight** = Gross - Tare

**Validation:**
- Weight must be > 0
- Weight must not exceed scale's max capacity
- Tare must be less than Gross

**Process:**
1. Navigate to `/pos/truck`
2. Select the Dropoff
3. Drive truck onto scale → read weight (manual entry or auto from scale)
4. Click **Record Gross Weight**
5. Unload material
6. Drive truck back onto scale
7. Click **Record Tare Weight**
8. Net weight auto-calculated

### Scrap Weighing

Individual items are weighed on the scrap scale.

**Process:**
1. Navigate to `/pos/terminal`
2. Search for POS Order (by name, license plate, or supplier)
3. Place item on scale
4. Select item type from the list
5. Record weight (manual or auto from scale)
6. Repeat for each item
7. System tracks variance vs contracted weight

**Reweighing:**
- An existing scrap weight can be loaded and re-weighed
- Must provide a reweight reason
- Original weight is preserved in history

---

## 8. Module Guide: Production Sorting

### Purpose

After material arrives and is weighed, the production team sorts and grades it. This determines the final quantities and quality grades for settlement.

### Production Session

Similar to POS Session — each worker opens a session before sorting.

**Rules:**
- One open session per operator
- Auto-closes after 10 minutes of inactivity
- Scale can be assigned for digital weighing during sorting

### Creating a Sorting Record

1. Open Production terminal at `/production/terminal`
2. Look up a Completed Dropoff
3. View source items (what arrived)
4. Sort into:
   - **Good Items** — Material that passes QC (item code, weight, remarks)
   - **Unwanted Items** — Rejected material (item code, weight, return reason, remarks)

**Return Reasons for Unwanted Items:**
- Contamination
- Wrong Material
- Packaging
- Dirt/Debris
- Other

**Example:**
| Source | Good Items | Unwanted Items |
|--------|-----------|----------------|
| 10.2 kg Copper | 9.0 kg Copper Grade A | 1.0 kg Copper Grade B (Other: downgraded) |
| | | 0.2 kg Copper (Contamination: plastic coating) |
| 4.5 kg Aluminum | 4.5 kg Aluminum Sheet | — |

### Submitting a Sorting

- On submit, the Dropoff Final is automatically updated
- Good items and unwanted items are aggregated by item code
- Totals and variance are recalculated

### Manager Override

- Production Manager can override variance flags
- Manager can close sessions opened by other workers

---

## 9. Module Guide: Settlement (SMT Purchase Order)

### Purpose

The SMT Purchase Order is the accountant's reconciliation document. It matches physical deliveries (Dropoff Finals) against price commitments (SMT Price Locks) and generates a Purchase Invoice.

### Creating a PO Final

1. Go to **SMT Accounting** workspace → **SMT Purchase Order** → **New**
2. Select **Supplier**
3. **Dropoff Finals panel** — select which unsettled Dropoff Finals to close
4. **Allocation table** — the heart of settlement:

For each item in the selected Dropoff Final(s):
| Action | Source | Rate |
|--------|--------|------|
| Allocate against PO | Select PO from dropdown | Auto-locked to PO rate |
| Price at Spot | Select "Spot" | Enter rate manually |

### Allocation Rules

1. **Full coverage required** — Every item in every selected Dropoff Final must be allocated. No partial dropoff settlement.
2. **No over-allocation** — Cannot allocate more than the PO's remaining quantity
3. **Rate is locked** — When source is PO, the rate comes from the PO and cannot be overridden
4. **Spot rate must be > 0** — Manual entry required for spot pricing
5. **Supplier consistency** — All POs and Dropoff Finals must belong to the same supplier
6. **No double-settle** — A Dropoff Final that is already "Settled" cannot be used again

### Splitting Allocations

If a single item in a Dropoff Final needs to span two POs (different rates), add two allocation rows for the same item, each pointing to a different PO. The total must equal the Dropoff Final's quantity for that item.

### What Happens on Submit

1. **PO settlement updated** — `settled_qty` incremented atomically on each PO item row
2. **PO status recomputed** — Open → Partially Settled → Fully Settled
3. **Dropoff Final(s) marked Settled** — status, po_final link, settled_by, settled_at
4. **Draft Purchase Invoice created** — with line items from allocations
5. **PO Final status → Submitted**

### What Happens on Cancel

1. Draft PI is deleted (if still draft)
2. If PI is submitted → cancel is blocked ("Cancel the Purchase Invoice first")
3. PO `settled_qty` reverted
4. PO status recomputed
5. Dropoff Final(s) reverted to Unsettled
6. PO Final status → Cancelled

### Cancellation Protection (Frappe Cascade)

Once a Payment Entry is submitted against the PI:
```
Cannot cancel PO Final
  ← because PI is submitted
    ← because Payment Entry is submitted
```

To unwind: Cancel Payment Entry → Cancel PI → Cancel PO Final (reverse order).

### Amending a PO Final

Use Frappe's standard amend flow:
1. Cancel the PO Final
2. Click **Amend** → creates a new version (POF-...-1)
3. Fix the allocation
4. Submit
5. Audit trail preserved via `amended_from`

---

## 10. Variance & Verification

### Types of Variance

The system tracks variance at multiple levels:

#### 1. Truck vs Scrap Variance

Compares truck net weight against total scrap weights.

```
Truck Net Weight:     15.0 kg (Gross 2500 - Tare 2485)
Total Scrap Weight:   14.7 kg (sum of individual scrap weights)
Variance:             0.3 kg (2.0%)
```

**Why it varies:** Material falls off during unloading, scale calibration differences, moisture loss.

#### 2. Indicated vs Actual Variance

Compares what the supplier said (POS Order contracted weight) against what was actually weighed.

```
Contracted:  15.0 kg (from POS Order)
Actual:      14.7 kg (from scrap weighing)
Variance:    -0.3 kg (-2.0%)
```

#### 3. Sorting Variance (Dropoff Final)

Compares Dropoff total weight against total sorted weight.

```
Dropoff Total:     14.7 kg
Sorted Good:       13.5 kg
Sorted Unwanted:    1.2 kg
Total Verified:    14.7 kg
Variance:           0.0 kg (0.0%)
```

### Variance Threshold

Configured in **Production Sorting Settings**:
- Default: **5%**
- If variance % ≤ threshold → **Variance OK**, Dropoff Final → **Unsettled** (ready for settlement)
- If variance % > threshold → **Needs Review**, Dropoff Final stays **In Progress**
- A manager must investigate and manually approve before settlement

### Verification Status

| Status | Meaning |
|--------|---------|
| **Pending** | No sorting done yet |
| **Verified** | Variance within threshold — auto-approved |
| **Needs Review** | Variance exceeds threshold — requires manager review |

---

## 11. Printing & Documents

### Available Print Formats

| Print Format | DocType | Description |
|-------------|---------|-------------|
| ใบยืนยันราคา (Price Lock) | SMT Price Lock | Supplier, locked items with rates/settled/remaining, totals, signatures |
| ใบสั่งซื้อ (Purchase Order) | SMT Purchase Order | Dropoff Finals, allocation table with PO/Spot breakdown, grand total, PI link |
| ใบคัดแยก (Sorting Report) | Dropoff Final | Good items, unwanted items with reasons, variance summary (pass/fail) |
| ใบคิวสองภาษา (Queue Ticket) | Dropoff | Truck weights, item summary (indicated vs actual), variance verification |
| ใบสรุปการส่งมอบ (Delivery Summary) | POS Order | Order items, weighed items, fulfillment status |
| Scrap Weight Thermal | Scrap Weight | 80mm thermal receipt for individual scrap weighing |
| Truck Weight Thermal | Truck Weight | 80mm thermal receipt for truck weighing |

All A4 formats are bilingual (Thai/English) with company letterhead, QR codes, and signature lines.
Thermal formats are 80mm width for receipt printers.

### Printing from Terminal

- In the POS terminal, click **Print** after recording weights
- Opens browser print dialog
- Thermal printer compatible (configure page size in browser settings)

### Reprinting

- Any submitted document can be reprinted from Frappe Desk
- Go to the document → **Menu** → **Print**
- Select print format → **Print** or **PDF**

---

## 12. Scheduled Tasks (Cron Jobs)

### Active Scheduled Tasks

| Task | Schedule | What it does |
|------|----------|-------------|
| **Close Idle POS Sessions** | Every 15 minutes | Closes POS sessions idle > 90 minutes. Releases the assigned scale. |
| **Close Idle Production Sessions** | Every 5 minutes | Closes Production sessions idle > 10 minutes. Releases the assigned scale. |
| **Expire Open POs** | Daily at 1:00 AM | Expires SMT Price Locks with status "Open" and expiry_date in the past. Does NOT expire Partially Settled POs. |

### How Idle Detection Works

- Each terminal sends a **heartbeat** every 30 seconds (via API call `update_session_activity`)
- The scheduler compares `last_activity` against the threshold
- If `last_activity` is older than the threshold, the session is auto-closed
- The operator sees a warning in the terminal when the session has been closed
- They must open a new session to continue working

### Session Auto-Close Details

When a session is auto-closed:
1. Session status → **Closed**
2. Closing time set to current time
3. Closed by → "Administrator"
4. If a scale was assigned, it is released (`in_use = 0`, `in_use_by_session = None`)

---

## 13. Validation Rules Reference

### SMT Price Lock

| Rule | Error Message |
|------|--------------|
| At least one item required | "At least one item row is required" |
| Qty must be > 0 | "Row X: Qty must be greater than 0" |
| Rate must be > 0 | "Row X: Rate must be greater than 0" |
| Cannot cancel with settled qty | "Cannot cancel: Row X has settled quantity. Cancel related PO Finals first." |

### SMT Purchase Order

| Rule | Error Message |
|------|--------------|
| Supplier consistency (Dropoff Final) | "Row X: Dropoff Final Y belongs to supplier Z, not W" |
| Dropoff Final already settled | "Row X: Dropoff Final Y is already settled. Cancel the existing PO Final first." |
| Allocation qty > 0 | "Allocation row X: Qty must be greater than 0" |
| Dropoff Final must be in panel | "Allocation row X: Dropoff Final Y is not in the Dropoff Finals table above" |
| PO required for PO source | "Allocation row X: PO is required when source is PO" |
| PO status must be Open/Partially Settled | "Allocation row X: PO Y has status Z, cannot allocate against it" |
| No over-allocation | "Allocation row X: Total allocation exceeds remaining qty" |
| Spot rate > 0 | "Allocation row X: Rate must be greater than 0 for Spot" |
| Full item coverage | "Dropoff Final X: Item Y has Z kg but only W kg allocated" |
| No phantom items | "Allocation references item X in Dropoff Final Y, but that item is not in the Dropoff Final" |
| Cannot cancel if PI submitted | "Cannot cancel: Purchase Invoice X is submitted. Cancel the Purchase Invoice first." |

### Dropoff

| Rule | Error Message |
|------|--------------|
| Single supplier per dropoff | "All orders must be from the same supplier" |
| No duplicate orders | "Same order cannot be linked multiple times" |
| Expected items must match orders | "POS Order X is linked but none of its items are in Expected Items" |
| Cannot change schedule after weighing | "Cannot change scheduled start time after weighing has started" |
| End time must be after start | "Scheduled end must be after start" |
| Cannot modify completed dropoff | (blocks order removal from Completed dropoff) |
| Cannot remove weights | (blocks license plate change if weights exist) |
| Tare must be less than gross | "Tare weight must be less than gross weight" |
| Cancellation needs reason | (requires cancellation_reason when status = Cancelled) |

### Truck Weight

| Rule | Error Message |
|------|--------------|
| Weight > 0 | "Weight must be greater than 0" |
| Weight ≤ scale max capacity | "Weight exceeds scale maximum capacity" |

### Production Sorting

| Rule | Error Message |
|------|--------------|
| Return reason must be valid | Must be: Contamination, Wrong Material, Packaging, Dirt/Debris, Other |
| Weight > 0 per item | Required |

---

## 14. Role Guide: POS Operator

### Your Job

You are the yard operator. You weigh trucks, weigh scrap items, and record deliveries.

### Daily Workflow

1. **Start of shift:** Go to `/pos` → Open Session → Select Scale
2. **When a truck arrives:**
   - Search for the POS Order (by name, license plate, or scan QR)
   - Create a Dropoff if one doesn't exist
   - Record Gross Weight (truck on scale)
   - Unload the truck
   - Record Tare Weight (empty truck on scale)
3. **Weigh individual items:**
   - Go to Scrap Terminal (`/pos/terminal`)
   - Select each item type → place on scale → record weight
   - Repeat for all items
4. **End of shift:** Close Session

### Screen 1: POS Index (`/pos`)

This is your starting page. You select a terminal and open your session here.

```
┌─────────────────────────────────────────────────────────┐
│                    🏭 SMT Price LockS                           │
│                      by X-DESK                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  Profile: [ Default POS Profile ▼ ]                    │
│                                                         │
│  ┌─────────────────┐  ┌─────────────────┐              │
│  │       ⚖️        │  │       🚛        │              │
│  │  Scrap Weighing │  │   Truck Scale   │              │
│  │  ชั่งเศษโลหะ     │  │   ชั่งรถบรรทุก    │              │
│  │                 │  │                 │              │
│  │  [ Click to     │  │  [ Click to     │              │
│  │    Start ]      │  │    Start ]      │              │
│  └─────────────────┘  └─────────────────┘              │
│                                                         │
│  ┌─────────────────┐                                    │
│  │       🔧        │                                    │
│  │  Production     │                                    │
│  │  Sorting        │                                    │
│  │  การคัดแยก       │                                    │
│  └─────────────────┘                                    │
│                                                         │
│  [🌐 EN/TH]  [☀️/🌙 Theme]                              │
│                                                         │
│  Operator: john@company.com          [ Logout ]        │
└─────────────────────────────────────────────────────────┘
```

**Actions:**
- Click a terminal card to open that terminal and start/resume a session
- Select a POS Profile from the dropdown (if multiple profiles exist)
- Use language/theme toggles at the bottom

### Screen 2: Scrap Weighing Terminal (`/pos/terminal`)

This is where you weigh individual scrap items.

```
┌─────────────────────────────────────────────────────────────────┐
│ [←] X-DESK  SES-260415-001  Profile  Operator  ⚖️Scale  14:32 │
│                                    [TH/EN] [☀️/🌙] [🖨️] [📊] [✕]│
├──────────────────────────┬──────────────────────────────────────┤
│                          │                                      │
│  ITEM CATEGORIES         │  DROP-OFF ID                         │
│  ┌─────┬──────┬──────┐   │  [_________________] [📷 Scan]       │
│  │ All │ From │Metal │   │                                      │
│  │     │Order │      │   │  ┌─ Dropoff Card ─────────────────┐  │
│  └─────┴──────┴──────┘   │  │ DO-260415-001          [▼] [✕] │  │
│                          │  │ Supplier: ACME Metals           │  │
│  ┌────────┐ ┌────────┐   │  │ Plate: ABC-1234                │  │
│  │Copper  │ │Aluminum│   │  │ Status: In Progress             │  │
│  │Wire    │ │Sheet   │   │  │ Expected: Cu 10kg, Al 5kg       │  │
│  │        │ │        │   │  └────────────────────────────────┘  │
│  └────────┘ └────────┘   │                                      │
│  ┌────────┐ ┌────────┐   │  SORTED ITEMS (CART)           [▼]  │
│  │Copper  │ │Steel   │   │  ┌──────────────────────────────┐   │
│  │Grade B │ │Scrap   │   │  │ Copper Wire     9.5 kg  [✕]  │   │
│  └────────┘ └────────┘   │  │ Aluminum Sheet  4.8 kg  [✕]  │   │
│                          │  └──────────────────────────────┘   │
│                          │                                      │
│                          │  TOTAL: 14.3 kg                      │
│                          │                                      │
│                          │  [💬 Remarks] [📷 Photo]              │
│                          │  [Cancel]  [✅ Record Weight]         │
└──────────────────────────┴──────────────────────────────────────┘
```

**Header Buttons (top right):**
| Button | Label | Action |
|--------|-------|--------|
| TH/EN | Language | Switch between Thai and English |
| ☀️/🌙 | Theme | Switch dark/light mode |
| 🖨️ | Print | Reprint last weight ticket |
| 📊 | Summary | View session totals |
| ✕ | Close Session | End your session |

**Left Panel — Item Selection:**
- **Category tabs** filter the item grid (All, From Order, or by item group)
- **Item cards** — click an item to open the weight input modal

**Right Panel — Transaction:**
- **Dropoff search** — type a Dropoff ID, license plate, or supplier name
- **📷 Scan** — open camera to scan QR/barcode
- **Dropoff card** — shows delivery details after selection (collapsible with ▼)
- **Cart** — items you've added with their weights. Click ✕ to remove.
- **Record Weight** — disabled until a Dropoff is selected and items are in the cart

**Weight Input Modal (appears when you click an item):**
```
┌───────────────────────────────────┐
│  Copper Wire                  [✕] │
├───────────────────────────────────┤
│                                   │
│  Scale Reading:                   │
│  ┌─────────────────────┐          │
│  │      9.520 kg       │  ● Live  │
│  └─────────────────────┘          │
│  [ Use This Weight ]             │
│                                   │
│  ── OR enter manually ──         │
│  [ 0.000 ] kg                    │
│                                   │
│  [Cancel]     [Add to Cart]      │
└───────────────────────────────────┘
```

- If scale is connected: live weight shows automatically. Click **Use This Weight** to capture it.
- If no scale or manual mode: type weight in the input field.
- Click **Add to Cart** to add the item.

### Screen 3: Truck Weighing Terminal (`/pos/truck`)

This is where you weigh the delivery truck (gross and tare).

```
┌─────────────────────────────────────────────────────────────────┐
│ [←] X-DESK  SES-260415-001  Profile  Operator  ⚖️Scale  14:32 │
│                                    [TH/EN] [☀️/🌙] [🖨️] [📊] [✕]│
├──────────────────────────┬──────────────────────────────────────┤
│                          │                                      │
│  🚛 TRUCK WEIGHTS        │  DROP-OFF ID                         │
│                          │  [_________________] [📷 Scan]       │
│  ┌──────────┬─────────┐  │                                      │
│  │  Gross   │  Tare   │  │  ┌─ Dropoff Card ─────────────┐     │
│  │  Weight  │  Weight │  │  │ DO-260415-001        [▼][✕] │     │
│  │  ✓ Done  │         │  │  │ ACME Metals / ABC-1234      │     │
│  └──────────┴─────────┘  │  └─────────────────────────────┘     │
│                          │                                      │
│  ┌────────────────────┐  │  WEIGHT VERIFICATION                 │
│  │ Weigh truck with   │  │  ┌──────────────────────────────┐   │
│  │ full load          │  │  │ Net Truck:     15.0 kg       │   │
│  │                    │  │  │ Total Scrap:   14.7 kg       │   │
│  │  [ 2500.0 ] kg     │  │  │ Variance:       0.3 kg (2%) │   │
│  │                    │  │  │ Status: ✅ Within threshold   │   │
│  │  [📷 Photo]        │  │  └──────────────────────────────┘   │
│  │  [Save Weight]     │  │                                      │
│  └────────────────────┘  │  SCRAP WEIGHTS                  [▼] │
│                          │  ┌──────────────────────────────┐   │
│  ✅ Gross: 2500.0 kg     │  │ Copper Wire      9.5 kg      │   │
│     14:20 Manual Entry   │  │ Aluminum Sheet   4.8 kg      │   │
│                          │  │ Total:          14.3 kg      │   │
│  NET WEIGHT SUMMARY      │  └──────────────────────────────┘   │
│  Gross:  2,500.0 kg      │                                      │
│  Tare:   2,485.0 kg      │                                      │
│  Net:       15.0 kg      │                                      │
│                          │                                      │
│  [💬 Remarks]            │                                      │
│  [✅ Complete Dropoff]    │                                      │
└──────────────────────────┴──────────────────────────────────────┘
```

**Left Panel — Weight Recording:**
- **Gross/Tare tabs** — switch between the two weight types
- After recording a weight, a ✓ confirmation appears with timestamp and method
- **Net Weight Summary** — appears when both weights are saved
- **Complete Dropoff** — marks the dropoff as Completed (only after both weights)

**Right Panel — Verification:**
- **Weight Verification** — compares truck net vs total scrap weights
- Shows variance amount and percentage
- Green ✅ if within threshold, red ⚠️ if exceeded
- **Scrap Weights** — collapsible list of all scrap weights for this dropoff

### Tips

- Always check the license plate matches the Dropoff
- If the scale reading looks wrong, re-weigh (provide a reason)
- If your session times out (90 min idle), just open a new one
- Use dark mode for outdoor/bright conditions (easier on the eyes)
- The **Print** button reprints the last weight ticket
- The **Summary** button shows your session totals (how many weights, total kg)

### What You Cannot Do

- Create or modify SMT Price Locks (price commitments)
- Create Production Sortings (that's the production team)
- Create PO Finals (that's the accountant)
- View settlement or accounting data

---

## 15. Role Guide: Production Worker

### Your Job

You sort and grade material after it arrives. You determine what is good quality and what needs to be rejected or downgraded.

### Daily Workflow

1. **Start of shift:** Go to `/production/terminal` → Open Session
2. **When material is ready for sorting:**
   - Look up the Completed Dropoff
   - View source items (what arrived)
   - Sort material physically
   - Record good items with weights
   - Record unwanted items with reasons
   - Submit the sorting
3. **End of shift:** Close Session (or it auto-closes after 10 min idle)

### Production Sorting Terminal (`/production/terminal`)

```
┌─────────────────────────────────────────────────────────────────┐
│ [←] X-DESK  PSORT-SES-001  Operator  ⚖️Scale  14:32           │
│                                    [TH/EN] [☀️/🌙] [📊] [✕]    │
├──────────────────────────┬──────────────────────────────────────┤
│                          │                                      │
│  ITEM CATEGORIES         │  DROP-OFF ID                         │
│  ┌─────┬──────┬──────┐   │  [_________________]                 │
│  │ All │Metal │Other │   │                                      │
│  └─────┴──────┴──────┘   │  ┌─ Dropoff Card ─────────────────┐  │
│                          │  │ DO-260415-001              [✕]  │  │
│  ┌────────┐ ┌────────┐   │  │ Supplier: ACME Metals          │  │
│  │Copper  │ │Aluminum│   │  │ Plate: ABC-1234                │  │
│  │Wire    │ │Sheet   │   │  │ Weight: 15.0 kg                │  │
│  │        │ │        │   │  │ Status: Completed               │  │
│  └────────┘ └────────┘   │  │                                 │  │
│  ┌────────┐ ┌────────┐   │  │ Source Items:                   │  │
│  │Copper  │ │Steel   │   │  │  • Copper Wire    10.2 kg       │  │
│  │Grade B │ │Scrap   │   │  │  • Aluminum Sheet  4.5 kg       │  │
│  └────────┘ └────────┘   │  └─────────────────────────────────┘  │
│                          │                                      │
│  Click an item to add    │  SORTED ITEMS                    2   │
│  it to sorted items.     │  ┌──────────────────────────────┐   │
│  Use the item grid for   │  │ Copper Wire     9.0 kg  [✕]  │   │
│  GOOD items.             │  │ Aluminum Sheet  4.5 kg  [✕]  │   │
│                          │  └──────────────────────────────┘   │
│                          │                                      │
│                          │  VARIANCE                            │
│                          │  Drop-off Weight:  14.7 kg           │
│                          │  Total Sorted:     13.5 kg           │
│                          │  Variance:         -1.2 kg (8.2%)    │
│                          │  [⚠️ Needs Review]                   │
│                          │                                      │
│                          │  [Save]       [✅ Complete Sorting]   │
└──────────────────────────┴──────────────────────────────────────┘
```

**Header Buttons:**
| Button | Action |
|--------|--------|
| TH/EN | Switch language |
| ☀️/🌙 | Switch dark/light mode |
| 📊 | View session summary (how many sortings, total weight) |
| ✕ Close Session | End your session |

**Left Panel — Item Selection:**
- **Category tabs** filter items by group (All, or specific item groups)
- **Item cards** — click to open weight modal. Items shown are filtered by Production Sorting Settings (allowed item groups only).

**Right Panel — Sorting:**
- **Dropoff search** — type a Dropoff ID to find a completed dropoff
- **Dropoff card** — shows source items (what arrived from weighing)
- **Sorted Items** — items you've added. Click ✕ to remove.
- **Variance** — real-time comparison of dropoff weight vs sorted weight
  - Green badge: **Verified** (within 5% threshold)
  - Yellow badge: **Needs Review** (exceeds threshold)
  - Grey badge: **Pending** (no items sorted yet)

**Action Buttons:**
| Button | Action |
|--------|--------|
| **Save** | Save sorting as draft (can edit later) |
| **Complete Sorting** | Submit the sorting — updates Dropoff Final |

**Weight Input Modal (appears when you click an item):**
```
┌───────────────────────────────┐
│  Copper Wire              [✕] │
├───────────────────────────────┤
│                               │
│     [ 9.000 ] kg              │
│                               │
│  [Cancel]          [OK]      │
└───────────────────────────────┘
```

- Enter weight manually or read from connected scale
- Click **OK** to add to sorted items

### How to Record Unwanted Items

Unwanted items (contaminated, wrong material, downgraded) are added the same way as good items, but with a return reason. The system tracks them separately.

**Available Return Reasons:**
| Reason | When to use |
|--------|-------------|
| Contamination | Material mixed with non-metal (plastic, wood, etc.) |
| Wrong Material | Not the item type expected |
| Packaging | Packaging material mixed in |
| Dirt/Debris | Excessive dirt or debris |
| Other | Any other reason (e.g., "Downgraded to Grade B") |

### Example: Grade Downgrade

If 10kg of Copper Wire arrives but 1kg is lower grade:

1. Add **Good Item:** Copper Wire — 9.0 kg
2. Add **Good Item:** Copper Grade B — 1.0 kg (the downgraded portion, different item code)
3. If 0.2kg is contaminated: Add **Unwanted Item:** Copper Wire — 0.2 kg, reason: "Contamination"

Total sorted: 10.2 kg (should match what arrived)

### Tips

- Always check the source items in the Dropoff card before sorting
- If variance exceeds 5%, the Dropoff Final will show "Needs Review" — a manager must approve
- Your session auto-closes after **10 minutes** of inactivity (shorter than POS)
- Your sorting directly determines what the accountant can settle — accuracy matters

### What You Cannot Do

- Record truck or scrap weights (that's the POS Operator)
- Create POs or settle deliveries (that's the accountant)
- Override variance thresholds (that's the Production Manager)

---

## 16. Role Guide: SMT Accountant

### Your Job

You manage price commitments, reconcile deliveries against commitments, and generate purchase invoices.

### Daily Workflow

1. **Price commitments:** Create SMT Price Locks when suppliers call to lock prices
2. **Settlement:** At end of day (or when Dropoff Finals are ready):
   - Go to SMT Accounting workspace
   - Check for unsettled Dropoff Finals
   - Create SMT Purchase Order for each supplier
   - Allocate items against POs or spot rates
   - Submit → Draft PI created
3. **Invoice review:** Open the Draft PI, verify, set warehouse, submit
4. **Payment:** Create Payment Entry against the PI

### Your Workspace

**SMT Accounting** workspace gives you:
- **Shortcuts:** New SMT Price Lock, New SMT Purchase Order
- **Settlement cards:** SMT Price Lock, SMT Purchase Order
- **Reference cards:** Dropoff Final, Dropoff, Production Sorting, Scrap Purchase, Truck Weight

### Key Screens

All work is done in **Frappe Desk** (the standard admin interface), not custom terminals.

**SMT Price Lock Form:**
```
┌─────────────────────────────────────────────────────────────┐
│  SMT Price Lock: PO-2026-00001                    [Submit] [Menu]  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Status: [Open]              Supplier: [ACME Metals ▼]     │
│  Supplier Name: ACME Metals                                 │
│                                                             │
│  ── Dates ──────────────────────────────────────────────    │
│  PO Date: [2026-04-15]      Expiry Date: [________]        │
│                                                             │
│  ── Items ──────────────────────────────────────────────    │
│  ┌──────────────┬────────┬───────────┬─────────┬────────┐  │
│  │ Item Code    │ PO Qty │ PO Rate   │ Amount  │Remaining│ │
│  ├──────────────┼────────┼───────────┼─────────┼────────┤  │
│  │ Copper Wire  │ 10.000 │ 300.00    │ 3000.00 │ 10.000 │  │
│  │ Aluminum     │  5.000 │  75.00    │  375.00 │  5.000 │  │
│  └──────────────┴────────┴───────────┴─────────┴────────┘  │
│  [Add Row]                                                  │
│                                                             │
│  ── Totals ─────────────────────────────────────────────    │
│  Total PO Value: 3,375.00    Total Settled: 0.00            │
│                                                             │
│  ── Notes ──────────────────────────────────────────────    │
│  [_________________________________________________]       │
│                                                             │
│  Connections: POS Orders (1) │ PO Finals (0)               │
└─────────────────────────────────────────────────────────────┘
```

**SMT Purchase Order Form:**
```
┌─────────────────────────────────────────────────────────────┐
│  SMT Purchase Order: POF-2026-00001              [Submit] [Menu] │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Status: [Draft]             Supplier: [ACME Metals ▼]     │
│  Final Date: [2026-04-15]                                   │
│                                                             │
│  ── Dropoff Finals Being Settled ───────────────────────    │
│  ┌────────────────────┬────────────┬──────────────┐         │
│  │ Dropoff Final      │ Date       │ Weight (kg)  │         │
│  ├────────────────────┼────────────┼──────────────┤         │
│  │ DFL-260415-001     │ 2026-04-15 │ 15.000       │         │
│  └────────────────────┴────────────┴──────────────┘         │
│  [Add Row]                                                  │
│                                                             │
│  ── Allocations ────────────────────────────────────────    │
│  ┌──────────┬────────┬──────┬────────┬────────┬────────┐   │
│  │ DOF      │ Item   │ Qty  │ Source │ SMT Price Lock │ Rate   │   │
│  ├──────────┼────────┼──────┼────────┼────────┼────────┤   │
│  │ DFL-001  │ Cu A   │ 9.0  │ PO     │PO-001  │ 300.00 │   │
│  │ DFL-001  │ Cu B   │ 1.0  │ Spot   │        │ 285.00 │   │
│  │ DFL-001  │ Al     │ 5.0  │ PO     │PO-001  │  75.00 │   │
│  └──────────┴────────┴──────┴────────┴────────┴────────┘   │
│  [Add Row]                                                  │
│                                                             │
│  ── Totals ─────────────────────────────────────────────    │
│  PO Total: 3,075.00    Spot Total: 285.00                   │
│  Grand Total: 3,360.00                                      │
│                                                             │
│  ── Linked Documents ───────────────────────────────────    │
│  Purchase Invoice: [ACC-PINV-2026-00001]                    │
│                                                             │
│  Connections: SMT Price Lock (1) │ Dropoff Final (1) │ PI (1)      │
└─────────────────────────────────────────────────────────────┘
```

**Allocation Workflow:**
1. Select supplier → dropoff final dropdown filters to Unsettled for that supplier
2. Add Dropoff Final to the panel → system shows the items and weights
3. For each item, add an allocation row:
   - Pick **Source: PO** → select which PO → rate auto-fills and locks
   - Pick **Source: Spot** → enter rate manually
4. System validates: total allocated per item = Dropoff Final qty
5. Click **Submit** → settlement runs, Draft PI created

### Read-Only Access

You can view (but not modify) all operational documents:
- Dropoff records — to verify delivery details
- Dropoff Finals — to see sorted quantities
- Production Sorting — to understand grade changes
- Truck Weights — to check gross/tare/net
- Scrap Weights — to verify individual item weights
- POS Orders — to see contracted quantities

### Dashboard Connections

When viewing an SMT Price Lock, the sidebar shows:
- **Orders** → POS Orders created from this PO
- **Settlement** → PO Finals that allocated against this PO

When viewing an SMT Purchase Order, the sidebar shows:
- **Settlement** → SMT Price Locks and Dropoff Finals referenced
- **Accounting** → linked Purchase Invoice

### Tips

- Always check the Dropoff Final's verification status before settling
- If a Dropoff Final shows "Needs Review", coordinate with the Production Manager
- Use Spot pricing only for material not covered by any PO
- If you made a mistake, cancel the PO Final (which deletes the draft PI), then amend and re-submit
- The PO rate is locked — you cannot override it in allocations

### What You Cannot Do

- Modify Dropoff records or weights (read-only access)
- Create or modify Production Sortings
- Open POS or Production sessions

---

## 17. Role Guide: Manager

### Production Manager

- Full access to Production Sorting and Production Session
- Can close sessions opened by other workers
- Can override variance flags on Dropoff Finals
- Can approve Dropoff Finals with "Needs Review" status

### System Manager

- Full access to everything
- Can configure:
  - Production Sorting Settings (variance threshold, allowed item groups)
  - Scale configurations
  - POS Profiles
  - User roles and permissions
- Can run tests and manage scheduled tasks

---

## 18. Workspaces

### SMT Production

**For:** Production Workers, Production Managers
**Shows:**
- Production Sorting (shortcut to list view)
- Production Sorting Settings

### SMT Accounting

**For:** SMT Accountant, SMT Accounting Manager
**Restricted to roles:** SMT Accountant, SMT Accounting Manager, System Manager
**Shows:**
- **Shortcuts:** SMT Price Lock, SMT Purchase Order
- **Settlement cards:** SMT Price Lock, SMT Purchase Order
- **Reference cards:** Dropoff Final, Dropoff, Production Sorting, Scrap Purchase, Truck Weight

---

## 19. Troubleshooting

### Scale Not Connecting

1. Check USB connection
2. Verify Chrome/Edge browser (WebSerial required)
3. Go to `/scale-test` to run diagnostics
4. Check scale settings: baud rate, data bits, parity, stop bits
5. Try auto-detect to identify the protocol

### Session Expired / Auto-Closed

- POS sessions auto-close after 90 minutes of inactivity
- Production sessions auto-close after 10 minutes
- Simply open a new session — your previous work is saved

### "Cannot Cancel" Errors

| Error | Solution |
|-------|----------|
| "settled quantity exists" | Cancel the PO Final(s) that reference this PO first |
| "Purchase Invoice is submitted" | Cancel the PI first, then cancel the PO Final |
| "Payment Entry linked" | Cancel the Payment Entry first, then PI, then PO Final |
| "Dropoff Final already settled" | Cancel the existing PO Final that settled this DOF |

### Variance Too High

- Check if material was properly sorted
- Verify scale calibration
- Compare truck net weight vs scrap total
- Production Manager may need to override

### POS Order Shows Wrong Fulfillment

- Fulfillment is auto-calculated from linked Dropoff weights
- If a Dropoff is cancelled, fulfillment is recalculated
- Check if all Dropoffs are properly linked to the order

---

## 20. Appendix: Keyboard Shortcuts

### Terminal Shortcuts

| Shortcut | Action |
|----------|--------|
| Click theme toggle | Switch dark/light mode |
| Click language toggle | Switch English/Thai |

### Frappe Desk Shortcuts

| Shortcut | Action |
|----------|--------|
| `Ctrl+S` | Save document |
| `Ctrl+Enter` | Submit document |
| `Ctrl+Shift+S` | Save and submit |
| `Esc` | Close dialog / go back |
| `/` | Quick search |

---

*End of Scrap Metal Suite User Guide v2.0*
