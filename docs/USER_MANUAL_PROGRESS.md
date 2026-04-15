# User Manual Progress Tracker

**Created:** 2026-01-15
**Purpose:** Track progress for writing the bilingual (Thai/English) User Manual
**Output File:** `docs/USER_MANUAL.md`

---

## Phase 1: Discovery (Explore Entire Codebase)

### 1.1 DocTypes to Document

**ACTIVE DocTypes (Document these):**

| DocType | Explored | Documented | Notes |
|---------|----------|------------|-------|
| POS Order | [ ] | [ ] | Main purchase order |
| POS Order Item | [ ] | [ ] | Child: ordered items |
| POS Order Weighed Item | [ ] | [ ] | Child: allocated weights |
| Dropoff | [ ] | [ ] | Main workflow document |
| Dropoff Order | [ ] | [ ] | Child: linked POS Orders |
| Dropoff Item Summary | [ ] | [ ] | Child: item totals |
| Scrap Weight | [ ] | [ ] | Individual weighing record |
| Scrap Weight Item | [ ] | [ ] | Child: items weighed |
| Truck Weight | [ ] | [ ] | Gross/Tare record |
| POS Session | [ ] | [ ] | Operator session |
| Scale | [ ] | [ ] | Scale configuration |

**STALE DocTypes (Future Development - DO NOT DOCUMENT NOW):**

| DocType | Status | Notes |
|---------|--------|-------|
| POS Authority Code | STALE | Future development |
| POS Profile Item | STALE | Future development |
| POS Profile Scrap | STALE | Future development |
| Scrap Purchase | STALE | Future development |
| Scrap Purchase Item | STALE | Future development |
| Supplier Registration Request | STALE | Future development |
| Dropoff Actual Item | STALE | Future development |
| Dropoff Expected Item | STALE | Future development |
| Dropoff Truck | STALE | Future development |
| Weight Photo | STALE | Future development |

### 1.2 Web Pages/Portals to Document

**ACTIVE Pages (Document these):**

| Page | Path | Explored | Documented | Notes |
|------|------|----------|------------|-------|
| POS Index | /pos | [ ] | [ ] | Session selection/start |
| POS Terminal | /pos/terminal | [ ] | [ ] | Scrap weighing interface |
| Truck Terminal | /pos/truck | [ ] | [ ] | Gross/Tare weighing |
| Scale Test | /scale-test | [ ] | [ ] | Scale connection testing |

**STALE Pages (Future Development - DO NOT DOCUMENT NOW):**

| Page | Path | Status | Notes |
|------|------|--------|-------|
| Manager Portal | /manager | STALE | Future development |
| Supplier Portal | /supplier | STALE | Future development |
| Dashboard | /dashboard | STALE | Future development |
| Reports | /reports | STALE | Future development |
| Portal | /portal | STALE | Future development |
| Supplier Registration | /supplier-registration-form | STALE | Future development |

### 1.3 APIs to Document

**ACTIVE APIs:**

| API Module | Path | Size | Explored | Documented |
|------------|------|------|----------|------------|
| POS API | api/v1/pos.py | 33KB | [ ] | [ ] |
| Dropoff API | api/v1/dropoff.py | 35KB | [ ] | [ ] |

**STALE APIs (Future Development):**

| API Module | Path | Status |
|------------|------|--------|
| Integrations | api/integrations/ | STALE |
| Webhooks | api/webhooks/ | STALE |

### 1.4 Print Formats

| Print Format | DocType | Explored | Documented |
|--------------|---------|----------|------------|
| Scrap Weight Thermal | Scrap Weight | [ ] | [ ] |
| Truck Weight Thermal | Truck Weight | [ ] | [ ] |
| ใบคิวสองภาษา | Dropoff | [ ] | [ ] |
| ใบสรุปการส่งมอบ | POS Order | [ ] | [ ] |
| Weight Receipt | POS Order | [ ] | [ ] |

### 1.5 Special Features to Document

| Feature | Explored | Documented | Notes |
|---------|----------|------------|-------|
| FIFO Allocation | [ ] | [ ] | Per-item fulfillment |
| Auto-print (Scrap) | [ ] | [ ] | terminal.html |
| Auto-print (Truck) | [ ] | [ ] | truck.html |
| Scale Integration | [ ] | [ ] | WebSerial API |
| Calendar View | [ ] | [ ] | Dropoff scheduling |
| Status Auto-transition | [ ] | [ ] | Draft→Scheduled→InProgress→Completed |
| Variance Tracking | [ ] | [ ] | Truck vs Scrap, Indicated vs Actual |
| QR Codes | [ ] | [ ] | On print formats |
| (others to discover) | | [ ] | |

---

## Phase 2: Exploration Notes

### DocTypes Found
(To be filled as I explore)

```
scrap_metal_suite/scrap_metal_suite/doctype/
├── (list all found)
```

### Key Findings
(To be filled as I discover features)

---

## Phase 3: User Manual Chapters

| Chapter | Title (EN) | Title (TH) | Status |
|---------|------------|------------|--------|
| 1 | System Overview | ภาพรวมระบบ | [x] DONE |
| 2 | DocType Reference | อ้างอิง DocType | [x] DONE (6 DocTypes + child tables) |
| 3 | POS Order Workflow | ขั้นตอนการสร้างใบสั่งซื้อ | [x] DONE |
| 4 | Dropoff Workflow | ขั้นตอนการรับสินค้า | [x] DONE |
| 5 | POS Terminal | หน้าจอชั่งสแครป | [x] DONE |
| 6 | Truck Terminal | หน้าจอชั่งรถ | [x] DONE |
| 7 | Printing & Documents | การพิมพ์และเอกสาร | [x] DONE |
| 8 | Desk Operations | การใช้งานผ่าน Desk | [x] DONE |
| A | Keyboard Shortcuts | ปุ่มลัด | [x] DONE |
| B | Troubleshooting | การแก้ไขปัญหา | [x] DONE |

---

## Current Task

**Status:** ✅ USER MANUAL COMPLETE
**Output:** `docs/USER_MANUAL.md`

---

## Summary of Active Components

```
ACTIVE DocTypes (11):
├── POS Order (+ 2 child tables)
├── Dropoff (+ 2 child tables)
├── Scrap Weight (+ 1 child table)
├── Truck Weight
├── POS Session
└── Scale

ACTIVE Web Pages (4):
├── /pos (index)
├── /pos/terminal (scrap weighing)
├── /pos/truck (truck weighing)
└── /scale-test

ACTIVE APIs (2):
├── api/v1/pos.py
└── api/v1/dropoff.py

Print Formats (5):
├── Scrap Weight Thermal
├── Truck Weight Thermal
├── ใบคิวสองภาษา (Dropoff)
├── ใบสรุปการส่งมอบ (POS Order)
└── Weight Receipt (POS Order)
```

---

## Session Log

### Session 1 (2026-01-15)
- Created this tracking document
- Explored codebase structure
- Identified 22 DocTypes total (11 active, 11 stale for future)
- Identified 4 active web pages (6 stale for future)
- Identified 2 active API modules
- **Completed:** Full User Manual in Thai/English
  - Chapter 1: System Overview
  - Chapter 2: DocType Reference (all fields for 6 DocTypes)
  - Chapter 3: POS Order Workflow + FIFO explanation
  - Chapter 4: Dropoff Workflow + Calendar + Status Flow
  - Chapter 5: POS Terminal (Scrap Weighing)
  - Chapter 6: Truck Terminal
  - Chapter 7: Printing & Documents
  - Chapter 8: Desk Operations
  - Appendix A: Keyboard Shortcuts
  - Appendix B: Troubleshooting
