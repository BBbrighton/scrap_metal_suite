# Scrap Metal Suite - User Manual
# คู่มือการใช้งานระบบรับซื้อเศษโลหะ

**Version:** 1.1
**Last Updated:** 2026-01-18

---

## Table of Contents / สารบัญ

1. [System Overview / ภาพรวมระบบ](#1-system-overview--ภาพรวมระบบ)
2. [DocType Reference / อ้างอิงเอกสาร](#2-doctype-reference--อ้างอิงเอกสาร)
3. [POS Order Workflow / ขั้นตอนการสร้างใบสั่งซื้อ](#3-pos-order-workflow--ขั้นตอนการสร้างใบสั่งซื้อ)
4. [Dropoff Workflow / ขั้นตอนการรับสินค้า](#4-dropoff-workflow--ขั้นตอนการรับสินค้า)
5. [POS Terminal (Scrap Weighing) / หน้าจอชั่งสแครป](#5-pos-terminal--หน้าจอชั่งสแครป)
6. [Truck Terminal / หน้าจอชั่งรถ](#6-truck-terminal--หน้าจอชั่งรถ)
7. [Printing & Documents / การพิมพ์และเอกสาร](#7-printing--documents--การพิมพ์และเอกสาร)
8. [Desk Operations / การใช้งานผ่าน Desk](#8-desk-operations--การใช้งานผ่าน-desk)

---

## 1. System Overview / ภาพรวมระบบ

### What is Scrap Metal Suite? / ระบบนี้คืออะไร?

**English:**
Scrap Metal Suite is a complete solution for managing scrap metal purchasing operations. It handles the entire workflow from creating purchase orders, scheduling truck deliveries (dropoffs), weighing scrap materials, tracking fulfillment, and generating receipts.

**ภาษาไทย:**
ระบบรับซื้อเศษโลหะ (Scrap Metal Suite) เป็นระบบครบวงจรสำหรับจัดการการรับซื้อเศษโลหะ ครอบคลุมตั้งแต่การสร้างใบสั่งซื้อ กำหนดการส่งสินค้า (Dropoff) ชั่งน้ำหนักเศษโลหะ ติดตามการส่งมอบ และออกใบเสร็จ

### System Flow / ลำดับการทำงาน

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   POS Order     │────▶│     Dropoff     │────▶│   Completion    │
│  ใบสั่งซื้อ      │     │   การรับสินค้า    │     │   เสร็จสิ้น      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                               │
                    ┌──────────┼──────────┐
                    ▼          ▼          ▼
             ┌──────────┐ ┌──────────┐ ┌──────────┐
             │  Truck   │ │  Scrap   │ │   Item   │
             │  Weight  │ │  Weight  │ │ Summary  │
             │ น้ำหนักรถ │ │น้ำหนักสแครป│ │  สรุปรายการ │
             └──────────┘ └──────────┘ └──────────┘
```

### Core Documents / เอกสารหลัก

| Document | Thai | Purpose |
|----------|------|---------|
| POS Order | ใบสั่งซื้อ | Contract with supplier for specific items and weights |
| Dropoff | ใบรับสินค้า | Single truck delivery event, can fulfill multiple orders |
| Scrap Weight | บันทึกชั่งสแครป | Individual weighing record for scrap items |
| Truck Weight | บันทึกชั่งรถ | Gross/Tare weight of delivery truck |
| POS Session | เซสชั่นผู้ใช้งาน | Operator's work session for terminal access |
| Scale | เครื่องชั่ง | Scale configuration and calibration tracking |

---

## 2. DocType Reference / อ้างอิงเอกสาร

### 2.1 POS Order / ใบสั่งซื้อ

**Purpose / วัตถุประสงค์:**
- EN: A purchase order/contract specifying what items and quantities are expected from a supplier
- TH: ใบสั่งซื้อ/สัญญากำหนดรายการและปริมาณที่คาดหวังจากซัพพลายเออร์

**Naming:** `ORD-.YY.MM.DD.-` (e.g., ORD-26.01.15-00001)

#### Fields / ฟิลด์ข้อมูล

| Field | Thai | Type | Required | Description |
|-------|------|------|----------|-------------|
| `supplier` | ซัพพลายเออร์ | Link → Supplier | Yes | The supplier/seller providing the scrap metal / ผู้ขายเศษโลหะ |
| `supplier_name` | ชื่อซัพพลายเออร์ | Data | Auto | Automatically fetched from supplier record / ดึงอัตโนมัติจากข้อมูลซัพพลายเออร์ |
| `order_date` | วันที่สั่งซื้อ | Date | Yes | Date of the order, should match Purchase Order / วันที่สั่งซื้อ ควรตรงกับใบสั่งซื้อ |
| `status` | สถานะ | Select | Yes | Current status of the order / สถานะปัจจุบันของใบสั่งซื้อ |
| `purchase_order` | เลขที่ใบสั่งซื้อ | Data | No | Reference to external purchase order / อ้างอิงใบสั่งซื้อภายนอก |
| `notes` | หมายเหตุ | Small Text | No | Additional notes / หมายเหตุเพิ่มเติม |

**Status Options / ตัวเลือกสถานะ:**
- `Pending` (รอดำเนินการ): Order created, waiting for delivery
- `Processing` (กำลังดำเนินการ): Delivery in progress
- `Processed` (ดำเนินการแล้ว): Order completed
- `Cancelled` (ยกเลิก): Order cancelled

#### Order Items Table / ตารางรายการสั่งซื้อ (`order_items`)

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `item_code` | รหัสสินค้า | Link → Item | Scrap metal item (only "Scrap Metal" group) / สินค้าเศษโลหะ |
| `item_name` | ชื่อสินค้า | Data | Auto-fetched item name / ชื่อสินค้าดึงอัตโนมัติ |
| `weight` | น้ำหนักสั่งซื้อ (kg) | Float | Contracted/ordered weight / น้ำหนักที่สั่งซื้อ |
| `uom` | หน่วย | Link → UOM | Unit of measure (default: Kg) / หน่วยวัด |
| `received_weight` | น้ำหนักที่ได้รับ (kg) | Float | Actual received weight (auto-calculated) / น้ำหนักจริงที่ได้รับ |
| `item_fulfillment_percent` | % การส่งมอบ | Percent | Per-item fulfillment percentage / เปอร์เซ็นต์การส่งมอบต่อรายการ |

#### Weighed Items Table / ตารางรายการที่ชั่งแล้ว (`items`)

Read-only table showing items allocated from dropoffs / ตารางแสดงรายการที่จัดสรรจาก Dropoff (อ่านอย่างเดียว)

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `dropoff` | Dropoff | Link → Dropoff | Source dropoff record / บันทึก Dropoff ต้นทาง |
| `scrap_weight` | บันทึกชั่ง | Link → Scrap Weight | Source weighing record / บันทึกการชั่งน้ำหนัก |
| `item_code` | รหัสสินค้า | Link → Item | Item code / รหัสสินค้า |
| `item_name` | ชื่อสินค้า | Data | Item name / ชื่อสินค้า |
| `weight` | น้ำหนัก (kg) | Float | Allocated weight / น้ำหนักที่จัดสรร |
| `uom` | หน่วย | Link → UOM | Unit of measure / หน่วยวัด |

#### Fulfillment Tracking / การติดตามการส่งมอบ

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `contracted_weight` | น้ำหนักตามสัญญา (kg) | Float | Sum of all ordered weights / ผลรวมน้ำหนักที่สั่งซื้อ |
| `total_received` | น้ำหนักที่ได้รับ (kg) | Float | Sum of all received weights / ผลรวมน้ำหนักที่ได้รับ |
| `fulfillment_percent` | % การส่งมอบ | Percent | (received / contracted) × 100 |
| `fulfillment_status` | สถานะการส่งมอบ | Select | Auto-calculated status / สถานะคำนวณอัตโนมัติ |

**Fulfillment Status Options / ตัวเลือกสถานะการส่งมอบ:**
- `Pending` (รอดำเนินการ): No items received yet
- `Partial` (บางส่วน): Some items received, not complete
- `Fulfilled` (ครบถ้วน): 100% delivered
- `Over-delivered` (เกินจำนวน): More than 100% delivered

---

### 2.2 Dropoff / ใบรับสินค้า

**Purpose / วัตถุประสงค์:**
- EN: A single truck delivery event. One truck can deliver for multiple POS Orders.
- TH: เหตุการณ์รับสินค้าครั้งเดียว รถหนึ่งคันสามารถส่งให้หลายใบสั่งซื้อได้

**Naming:** `DO-.YY.MM.DD.-` (e.g., DO-26.01.15-00001)

**Calendar View:** Dropoffs can be viewed on a calendar based on `dropoff_scheduled_start` and `dropoff_scheduled_end`

#### Header Fields / ฟิลด์ส่วนหัว

| Field | Thai | Type | Required | Description |
|-------|------|------|----------|-------------|
| `dropoff_scheduled_start` | เวลานัดหมาย (เริ่ม) | Datetime | Yes | When truck is expected to arrive / เวลาที่คาดว่ารถจะมาถึง |
| `dropoff_scheduled_end` | เวลานัดหมาย (สิ้นสุด) | Datetime | No | When dropoff should be complete / เวลาที่คาดว่าจะเสร็จ |
| `license_plate` | ทะเบียนรถ | Data | Yes | Truck license plate number / หมายเลขทะเบียนรถ |
| `status` | สถานะ | Select | Yes | Current dropoff status / สถานะปัจจุบัน |
| `supplier` | ซัพพลายเออร์ | Link → Supplier | Auto | Auto-set from linked orders / ตั้งอัตโนมัติจากใบสั่งซื้อที่เชื่อมโยง |
| `supplier_name` | ชื่อซัพพลายเออร์ | Data | Auto | Auto-fetched / ดึงอัตโนมัติ |

**Status Flow / ลำดับสถานะ:**

```
Draft → Scheduled → In Progress → Completed
  │         │            │
  │         │            └── Auto: all weights recorded
  │         └── Auto: first weight recorded
  └── Auto: has license_plate + scheduled date
              │
              └──→ Cancelled (manual, requires reason)
```

| Status | Thai | Trigger | Color |
|--------|------|---------|-------|
| `Draft` | ร่าง | Default | Grey |
| `Scheduled` | นัดหมายแล้ว | Auto: has license plate + date | Blue |
| `In Progress` | กำลังดำเนินการ | Auto: first weight recorded | Orange |
| `Completed` | เสร็จสิ้น | Auto: has gross + tare + scrap | Green |
| `Cancelled` | ยกเลิก | Manual (requires reason) | Dark Grey |

#### Linked Orders Table / ตารางใบสั่งซื้อที่เชื่อมโยง (`orders`)

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `pos_order` | ใบสั่งซื้อ | Link → POS Order | Linked POS Order / ใบสั่งซื้อที่เชื่อมโยง |
| `allocated_weight` | น้ำหนักที่จัดสรร (kg) | Float | Weight allocated to this order (auto) / น้ำหนักที่จัดสรรให้ใบสั่งซื้อนี้ |

#### Truck Weight Fields / ฟิลด์น้ำหนักรถ

**Gross Weight Section / ส่วนน้ำหนักรวม:**

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `gross_weight` | น้ำหนักรวม (kg) | Float | Weight of truck WITH scrap / น้ำหนักรถพร้อมสินค้า |
| `gross_weight_scale` | เครื่องชั่ง | Link → Scale | Scale used / เครื่องชั่งที่ใช้ |
| `gross_weight_time` | เวลาชั่ง | Datetime | When weighed / เวลาที่ชั่ง |
| `gross_weight_operator` | ผู้ชั่ง | Link → User | Who weighed / ผู้ที่ทำการชั่ง |

**Tare Weight Section / ส่วนน้ำหนักเปล่า:**

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `tare_weight` | น้ำหนักเปล่า (kg) | Float | Weight of EMPTY truck / น้ำหนักรถเปล่า |
| `tare_weight_scale` | เครื่องชั่ง | Link → Scale | Scale used / เครื่องชั่งที่ใช้ |
| `tare_weight_time` | เวลาชั่ง | Datetime | When weighed / เวลาที่ชั่ง |
| `tare_weight_operator` | ผู้ชั่ง | Link → User | Who weighed / ผู้ที่ทำการชั่ง |

**Net Weight / น้ำหนักสุทธิ:**

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `net_weight` | น้ำหนักสุทธิ (kg) | Float | Gross - Tare (auto-calculated) / น้ำหนักรวม - น้ำหนักเปล่า |
| `truck_photo` | รูปถ่ายรถ | Attach Image | Photo of truck / รูปถ่ายรถ |
| `truck_remarks` | หมายเหตุ | Small Text | Notes about truck / หมายเหตุเกี่ยวกับรถ |

#### Item Summary Table / ตารางสรุปรายการ (`item_summary`)

Auto-generated summary of all weighed items / สรุปรายการที่ชั่งทั้งหมด (สร้างอัตโนมัติ)

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `item` | สินค้า | Link → Item | Item code / รหัสสินค้า |
| `item_name` | ชื่อสินค้า | Data | Item name / ชื่อสินค้า |
| `total_weight` | น้ำหนักรวม (kg) | Float | Total weight for this item / น้ำหนักรวมของสินค้านี้ |
| `weigh_count` | จำนวนครั้งที่ชั่ง | Int | Number of weighings / จำนวนครั้งที่ชั่ง |

#### Variance Tracking / การติดตามความแตกต่าง

**Truck Variance / ความแตกต่างน้ำหนักรถ:**
Compares net truck weight vs total scrap weight / เปรียบเทียบน้ำหนักสุทธิรถกับน้ำหนักสแครปรวม

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `total_truck_weight` | น้ำหนักรถสุทธิ | Float | = net_weight |
| `total_scrap_weight` | น้ำหนักสแครปรวม | Float | Sum from Scrap Weight records / ผลรวมจากบันทึกชั่งสแครป |
| `truck_variance_threshold_percent` | เกณฑ์ความแตกต่าง % | Percent | Maximum acceptable variance (default 0.01%) / ความแตกต่างที่ยอมรับได้ |
| `truck_variance` | ความแตกต่าง (kg) | Float | truck - scrap weight |
| `truck_variance_percent` | ความแตกต่าง % | Percent | Percentage difference / เปอร์เซ็นต์ความแตกต่าง |
| `truck_variance_ok` | ผ่านเกณฑ์ | Check | Auto: within threshold / อัตโนมัติ: อยู่ในเกณฑ์ |

**Indicated Variance / ความแตกต่างที่ระบุ:**
Compares supplier's indicated weight vs actual weighed / เปรียบเทียบน้ำหนักที่ซัพพลายเออร์ระบุกับน้ำหนักจริง

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `total_indicated_weight` | น้ำหนักที่ระบุ | Float | What supplier claimed / น้ำหนักที่ซัพพลายเออร์แจ้ง |
| `indicated_variance_threshold_percent` | เกณฑ์ความแตกต่าง % | Percent | Maximum acceptable (default 0.01%) |
| `indicated_variance` | ความแตกต่าง (kg) | Float | indicated - actual |
| `indicated_variance_percent` | ความแตกต่าง % | Percent | Percentage difference |
| `indicated_variance_ok` | ผ่านเกณฑ์ | Check | Auto: within threshold |

**Verification Status / สถานะการตรวจสอบ:**

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `verification_status` | สถานะการตรวจสอบ | Data | Auto-calculated / คำนวณอัตโนมัติ |

Values / ค่า:
- `Pending` (รอตรวจสอบ): Missing weights
- `Verified` (ตรวจสอบแล้ว): All weights OK, variances within threshold
- `Needs Review` (ต้องตรวจสอบ): Variances exceed threshold

---

### 2.3 Scrap Weight / บันทึกชั่งสแครป

**Purpose / วัตถุประสงค์:**
- EN: Individual weighing record for scrap items. Multiple records can be created for one Dropoff.
- TH: บันทึกการชั่งน้ำหนักสแครปแต่ละครั้ง สามารถสร้างหลายบันทึกต่อหนึ่ง Dropoff

**Naming:** `WGT-.YY.MM.DD.-` (e.g., WGT-26.01.15-00001)

#### Fields / ฟิลด์ข้อมูล

| Field | Thai | Type | Required | Description |
|-------|------|------|----------|-------------|
| `dropoff` | Dropoff | Link → Dropoff | Yes | The dropoff this weight belongs to / Dropoff ที่บันทึกนี้สังกัด |
| `supplier_name` | ชื่อซัพพลายเออร์ | Data | Auto | Auto-fetched / ดึงอัตโนมัติ |
| `posting_date` | วันที่บันทึก | Date | Yes | Date of weighing / วันที่ชั่ง |
| `posting_time` | เวลาบันทึก | Time | No | Time of weighing / เวลาที่ชั่ง |
| `session` | เซสชั่น | Link → POS Session | No | Operator's session / เซสชั่นผู้ปฏิบัติงาน |
| `operator` | ผู้ปฏิบัติงาน | Link → User | Auto | Who recorded this / ผู้บันทึก |
| `pos_profile` | POS Profile | Link | Auto | Profile used / โปรไฟล์ที่ใช้ |
| `scale` | เครื่องชั่ง | Link → Scale | Auto | Scale used / เครื่องชั่งที่ใช้ |
| `entry_method` | วิธีบันทึก | Select | No | How weight was entered / วิธีการบันทึกน้ำหนัก |
| `total_weight` | น้ำหนักรวม (kg) | Float | Auto | Sum of all items / ผลรวมน้ำหนักทุกรายการ |
| `remarks` | หมายเหตุ | Small Text | No | Additional notes / หมายเหตุเพิ่มเติม |

**Entry Method Options / ตัวเลือกวิธีบันทึก:**
- `Scale (Auto)` (จากเครื่องชั่ง): Weight captured from connected scale
- `Manual Entry` (บันทึกเอง): Weight entered manually

**Entry Method Tracking (v1.1):** The system automatically tracks how each weight was recorded. When a scale is connected, the manual entry option is hidden to ensure accurate tracking. Entry method is shown on thermal receipts.

**การติดตามวิธีบันทึก (v1.1):** ระบบติดตามวิธีการบันทึกน้ำหนักแต่ละครั้งโดยอัตโนมัติ เมื่อเชื่อมต่อเครื่องชั่ง ตัวเลือกบันทึกเองจะถูกซ่อนเพื่อความถูกต้อง วิธีบันทึกจะแสดงในใบเสร็จ thermal

#### Reweight Fields / ฟิลด์การชั่งซ้ำ

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `is_reweight` | ชั่งซ้ำ | Check | Indicates this is a re-weighing / ระบุว่าเป็นการชั่งซ้ำ |
| `reweight_reason` | เหตุผล | Small Text | Reason for reweigh / เหตุผลในการชั่งซ้ำ |
| `reweight_by` | ชั่งซ้ำโดย | Link → User | Who performed reweigh / ผู้ทำการชั่งซ้ำ |
| `reweight_at` | เวลาชั่งซ้ำ | Datetime | When reweighed / เวลาที่ชั่งซ้ำ |

#### Items Table / ตารางรายการ (`items`)

| Field | Thai | Type | Required | Description |
|-------|------|------|----------|-------------|
| `item_code` | รหัสสินค้า | Link → Item | Yes | Scrap item / สินค้าเศษโลหะ |
| `item_name` | ชื่อสินค้า | Data | Auto | Item name / ชื่อสินค้า |
| `weight` | น้ำหนัก (kg) | Float | Yes | Weight of this item / น้ำหนักสินค้านี้ |
| `uom` | หน่วย | Link → UOM | Auto | Unit (default Kg) / หน่วย |

---

### 2.4 Truck Weight / บันทึกชั่งรถ

**Purpose / วัตถุประสงค์:**
- EN: Record gross or tare weight of delivery truck. Created automatically from Truck Terminal.
- TH: บันทึกน้ำหนักรวม (Gross) หรือน้ำหนักเปล่า (Tare) ของรถขนส่ง สร้างอัตโนมัติจากหน้าจอชั่งรถ

**Naming:** `TW-.YY.MM.DD.-` (e.g., TW-26.01.15-00001)

#### Fields / ฟิลด์ข้อมูล

| Field | Thai | Type | Required | Description |
|-------|------|------|----------|-------------|
| `dropoff` | Dropoff | Link → Dropoff | Yes | Linked dropoff / Dropoff ที่เชื่อมโยง |
| `license_plate` | ทะเบียนรถ | Data | Auto | Auto-fetched from dropoff / ดึงจาก Dropoff |
| `supplier_name` | ชื่อซัพพลายเออร์ | Data | Auto | Auto-fetched / ดึงอัตโนมัติ |
| `weight_type` | ประเภทน้ำหนัก | Select | Yes | Gross or Tare / น้ำหนักรวมหรือน้ำหนักเปล่า |
| `weighed_at` | เวลาชั่ง | Datetime | Yes | When weighed / เวลาที่ชั่ง |
| `weight` | น้ำหนัก (kg) | Float | Yes | Weight reading / ค่าน้ำหนัก |
| `scale` | เครื่องชั่ง | Link → Scale | No | Scale used / เครื่องชั่งที่ใช้ |
| `entry_method` | วิธีบันทึก | Select | No | Scale (Auto) or Manual Entry / วิธีการบันทึก |
| `operator` | ผู้ปฏิบัติงาน | Link → User | No | Who recorded / ผู้บันทึก |
| `remarks` | หมายเหตุ | Small Text | No | Notes / หมายเหตุ |

**Weight Type Options / ประเภทน้ำหนัก:**
- `Gross` (น้ำหนักรวม): Truck WITH scrap (weighed first)
- `Tare` (น้ำหนักเปล่า): Empty truck (weighed after unloading)

#### Reweight Fields / ฟิลด์การชั่งซ้ำ

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `is_reweight` | ชั่งซ้ำ | Check | Indicates this is a re-weighing |
| `reweight_reason` | เหตุผล | Small Text | Reason for reweigh (required if reweight) |
| `reweight_by` | ชั่งซ้ำโดย | Link → User | Who performed reweigh |
| `reweight_at` | เวลาชั่งซ้ำ | Datetime | When reweighed |

---

### 2.5 POS Session / เซสชั่นผู้ใช้งาน

**Purpose / วัตถุประสงค์:**
- EN: Operator's work session. Required to access POS Terminal or Truck Terminal.
- TH: เซสชั่นการทำงานของผู้ปฏิบัติงาน จำเป็นต้องมีเพื่อเข้าใช้หน้าจอชั่งสแครปหรือหน้าจอชั่งรถ

**Naming:** `SES-.YY.MM.DD.-` (e.g., SES-26.01.15-00001)

#### Fields / ฟิลด์ข้อมูล

| Field | Thai | Type | Required | Description |
|-------|------|------|----------|-------------|
| `pos_profile` | POS Profile | Link | Yes | Profile configuration / การตั้งค่าโปรไฟล์ |
| `operator` | ผู้ปฏิบัติงาน | Link → User | Yes | User operating the session / ผู้ใช้งานเซสชั่น |
| `scale` | เครื่องชั่ง | Link → Scale | No | Scale selected for this session / เครื่องชั่งที่เลือก |
| `status` | สถานะ | Select | Yes | Open or Closed / เปิดหรือปิด |
| `opening_time` | เวลาเปิด | Datetime | Yes | When session started / เวลาเริ่มเซสชั่น |
| `closing_time` | เวลาปิด | Datetime | No | When session ended / เวลาสิ้นสุดเซสชั่น |
| `last_activity` | กิจกรรมล่าสุด | Datetime | Auto | For timeout tracking / สำหรับติดตาม timeout |
| `closed_by` | ปิดโดย | Link → User | Auto | Who closed the session / ผู้ปิดเซสชั่น |

**Session Totals / สรุปเซสชั่น:**

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `total_purchases` | จำนวนรายการ | Int | Number of transactions / จำนวนรายการทั้งหมด |
| `total_amount` | ยอดรวม | Currency | Total amount / ยอดเงินรวม |
| `total_weight` | น้ำหนักรวม (kg) | Float | Total weight / น้ำหนักรวม |

---

### 2.6 Scale / เครื่องชั่ง

**Purpose / วัตถุประสงค์:**
- EN: Configuration and tracking for weighing scales. Supports WebSerial connection.
- TH: การตั้งค่าและติดตามเครื่องชั่ง รองรับการเชื่อมต่อ WebSerial

**Naming:** By `scale_name` field (e.g., SCALE-001)

#### Basic Fields / ฟิลด์พื้นฐาน

| Field | Thai | Type | Required | Description |
|-------|------|------|----------|-------------|
| `scale_name` | ชื่อเครื่องชั่ง | Data | Yes | Unique identifier / รหัสเครื่องชั่ง |
| `scale_type` | ประเภท | Select | Yes | Platform/Weighbridge/Hanging/Floor/Bench |
| `usage_type` | การใช้งาน | Select | Yes | Scrap or Truck / สำหรับสแครปหรือรถ |
| `location` | ตำแหน่ง | Data | No | Physical location / ตำแหน่งติดตั้ง |
| `is_active` | ใช้งาน | Check | Default=Yes | Enable/disable for selection / เปิด/ปิดการเลือกใช้ |
| `in_use` | กำลังใช้งาน | Check | Auto | Currently in use by a session / กำลังถูกใช้งาน |
| `in_use_by_session` | ใช้งานโดยเซสชั่น | Link | Auto | Which session is using it / เซสชั่นที่ใช้งานอยู่ |
| `max_capacity_kg` | ความจุสูงสุด (kg) | Float | No | Maximum weight capacity / น้ำหนักสูงสุดที่รับได้ |

**Usage Type Options / ประเภทการใช้งาน:**
- `Scrap` (สแครป): For weighing scrap items
- `Truck` (รถ): For weighing trucks (weighbridge)

#### Serial Connection Settings / การตั้งค่าการเชื่อมต่อ

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `baud_rate` | Baud Rate | Select | Communication speed (1200-115200) |
| `data_bits` | Data Bits | Select | 7 or 8 |
| `parity` | Parity | Select | none/even/odd |
| `stop_bits` | Stop Bits | Select | 1 or 2 |
| `flow_control` | Flow Control | Select | none/hardware |
| `protocol_detected` | Protocol | Data | Auto-detected (STX, HP-05) |

#### Unit Conversion / การแปลงหน่วย

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `unit_conversion_factor` | ตัวคูณแปลงหน่วย | Float | Multiply reading to get kg / คูณค่าที่อ่านเพื่อให้ได้ kg |
| `signal_unit` | หน่วยสัญญาณ | Select | Unit scale sends (kg/grams/tons/lb) |

**Common Conversion Factors / ตัวคูณที่ใช้บ่อย:**
- grams → kg: 0.001
- kg → kg: 1 (no conversion)
- tons → kg: 1000
- lb → kg: 0.453592

#### Calibration / การสอบเทียบ

| Field | Thai | Type | Description |
|-------|------|------|-------------|
| `last_calibration_date` | วันที่สอบเทียบล่าสุด | Date | Last calibration date |
| `calibration_certificate` | ใบรับรองการสอบเทียบ | Attach | Certificate file |
| `next_calibration_date` | วันที่สอบเทียบครั้งถัดไป | Date | Next calibration due date |

---

*Continue to Chapter 3...*

---

## 3. POS Order Workflow / ขั้นตอนการสร้างใบสั่งซื้อ

### Step 1: Create POS Order / สร้างใบสั่งซื้อ

**English:**
1. Go to: **Scrap Metal Suite > POS Order > New**
2. Select `supplier` from the dropdown
3. Set `order_date` (defaults to today)
4. Add items to the `order_items` table:
   - Select `item_code` (only Scrap Metal items shown)
   - Enter `weight` in kg (contracted amount)
5. Click **Save**

**ภาษาไทย:**
1. ไปที่: **Scrap Metal Suite > POS Order > สร้างใหม่**
2. เลือก `supplier` (ซัพพลายเออร์)
3. ตั้ง `order_date` (วันที่สั่งซื้อ - ค่าเริ่มต้นคือวันนี้)
4. เพิ่มรายการในตาราง `order_items`:
   - เลือก `item_code` (แสดงเฉพาะสินค้ากลุ่มเศษโลหะ)
   - ใส่ `weight` เป็น kg (จำนวนตามสัญญา)
5. คลิก **บันทึก**

### Step 2: Understanding Fulfillment / ทำความเข้าใจการส่งมอบ

When dropoffs are completed, the system automatically:
- Allocates weights to orders using **FIFO** (First In, First Out)
- Oldest orders get fulfilled first
- Updates `received_weight` and `item_fulfillment_percent` per item
- Updates overall `fulfillment_status`

เมื่อ Dropoff เสร็จสิ้น ระบบจะทำโดยอัตโนมัติ:
- จัดสรรน้ำหนักให้ใบสั่งซื้อแบบ **FIFO** (เข้าก่อน-ออกก่อน)
- ใบสั่งซื้อที่เก่าที่สุดจะได้รับการเติมเต็มก่อน
- อัปเดต `received_weight` และ `item_fulfillment_percent` ต่อรายการ
- อัปเดต `fulfillment_status` โดยรวม

### FIFO Allocation Example / ตัวอย่างการจัดสรรแบบ FIFO

```
Order A (2026-01-10): Copper 500kg ordered
Order B (2026-01-12): Copper 300kg ordered

Dropoff delivers: Copper 600kg

Result:
├── Order A gets 500kg (100% fulfilled) ← OLDEST FIRST
└── Order B gets 100kg (33% fulfilled)
```

---

## 4. Dropoff Workflow / ขั้นตอนการรับสินค้า

### Step 1: Create Dropoff / สร้าง Dropoff

**English:**
1. Go to: **Scrap Metal Suite > Dropoff > New**
2. Enter `license_plate` (required)
3. Set `dropoff_scheduled_start` (when truck expected)
4. Optionally set `dropoff_scheduled_end`
5. Add POS Orders to the `orders` table
6. Click **Save**

Status will auto-change to "Scheduled" when saved with license plate and date.

**ภาษาไทย:**
1. ไปที่: **Scrap Metal Suite > Dropoff > สร้างใหม่**
2. ใส่ `license_plate` (ทะเบียนรถ - จำเป็น)
3. ตั้ง `dropoff_scheduled_start` (เวลาที่คาดว่ารถจะมา)
4. ตั้ง `dropoff_scheduled_end` (ถ้าต้องการ)
5. เพิ่มใบสั่งซื้อในตาราง `orders`
6. คลิก **บันทึก**

สถานะจะเปลี่ยนเป็น "Scheduled" อัตโนมัติเมื่อมีทะเบียนรถและวันที่

### Step 2: Calendar View / มุมมองปฏิทิน

Dropoffs appear on calendar based on scheduled times:
- Go to: **Scrap Metal Suite > Dropoff** 
- Click the **Calendar** icon in the list view
- View dropoffs by day/week/month
- Click on a dropoff to open it

Dropoff จะแสดงในปฏิทินตามเวลานัดหมาย:
- ไปที่: **Scrap Metal Suite > Dropoff**
- คลิกไอคอน **ปฏิทิน** ในหน้ารายการ
- ดู Dropoff ตามวัน/สัปดาห์/เดือน
- คลิกที่ Dropoff เพื่อเปิดดู

### Step 3: Weighing Process / กระบวนการชั่งน้ำหนัก

The typical flow:

```
1. Truck arrives (รถมาถึง)
   └── Status: Scheduled → In Progress

2. Weigh Gross (ชั่งน้ำหนักรวม)
   └── Use Truck Terminal
   └── Auto-print: Truck Weight Thermal

3. Unload scrap (ขนสแครปลง)
   
4. Weigh Scrap items (ชั่งสแครป)
   └── Use POS Terminal
   └── Multiple weighings OK
   └── Auto-print: Scrap Weight Thermal

5. Weigh Tare (ชั่งน้ำหนักเปล่า)
   └── Use Truck Terminal
   └── Auto-print: Truck Weight Thermal

6. Complete (เสร็จสิ้น)
   └── Status: In Progress → Completed
   └── FIFO allocation runs automatically
```

### Step 4: Variance Checks / การตรวจสอบความแตกต่าง

After completion, system checks:

| Check | Formula | Threshold |
|-------|---------|-----------|
| Truck Variance | Net Truck Weight - Total Scrap Weight | 0.01% |
| Indicated Variance | Supplier Indicated - Actual Weighed | 0.01% |

If variance exceeds threshold: `verification_status` = "Needs Review"

หลังจากเสร็จสิ้น ระบบจะตรวจสอบ:

| การตรวจสอบ | สูตร | เกณฑ์ |
|------------|------|-------|
| ความแตกต่างรถ | น้ำหนักสุทธิรถ - น้ำหนักสแครปรวม | 0.01% |
| ความแตกต่างที่ระบุ | น้ำหนักที่ซัพพลายเออร์แจ้ง - น้ำหนักจริง | 0.01% |

ถ้าความแตกต่างเกินเกณฑ์: `verification_status` = "Needs Review"

---

## 5. POS Terminal / หน้าจอชั่งสแครป

### Accessing the Terminal / การเข้าใช้งาน

**URL:** `/pos/terminal?session=SES-XXXXXX`

**English:**
1. Go to: `/pos` 
2. Select or create a POS Session
3. Select a scale (if available)
4. Click **Enter Terminal**

**ภาษาไทย:**
1. ไปที่: `/pos`
2. เลือกหรือสร้างเซสชั่น POS
3. เลือกเครื่องชั่ง (ถ้ามี)
4. คลิก **เข้าสู่หน้าจอ**

### Terminal Interface / หน้าจอการทำงาน

The terminal has these sections:

| Section | Thai | Purpose |
|---------|------|---------|
| Dropoff Search | ค้นหา Dropoff | Find dropoff by license plate or ID |
| Scale Display | หน้าจอเครื่องชั่ง | Shows live weight from connected scale |
| Item Selection | เลือกสินค้า | Choose scrap metal type |
| Weight Entry | บันทึกน้ำหนัก | Enter or capture weight |
| Transaction List | รายการที่ชั่ง | Shows items weighed in current session |

### Recording Scrap Weight / บันทึกน้ำหนักสแครป

**English:**
1. Search for Dropoff (by license plate)
2. Select from search results
3. Choose item type
4. Either:
   - **Auto capture**: Click "Capture" when scale shows stable weight
   - **Manual entry**: Type weight and click "Save"
5. Thermal receipt prints automatically

**ภาษาไทย:**
1. ค้นหา Dropoff (ตามทะเบียนรถ)
2. เลือกจากผลการค้นหา
3. เลือกประเภทสินค้า
4. เลือกวิธี:
   - **จับอัตโนมัติ**: คลิก "จับน้ำหนัก" เมื่อเครื่องชั่งแสดงค่าคงที่
   - **บันทึกเอง**: พิมพ์น้ำหนักแล้วคลิก "บันทึก"
5. ใบเสร็จ thermal พิมพ์อัตโนมัติ

### Scale Connection / การเชื่อมต่อเครื่องชั่ง

The system uses **WebSerial API** (Chrome/Edge required):

1. Click "Connect Scale" button
2. Browser asks to select serial port
3. System auto-detects baud rate and protocol
4. Supported protocols: STX, HP-05

ระบบใช้ **WebSerial API** (ต้องใช้ Chrome/Edge):

1. คลิกปุ่ม "เชื่อมต่อเครื่องชั่ง"
2. เบราว์เซอร์ถามให้เลือก serial port
3. ระบบตรวจจับ baud rate และ protocol อัตโนมัติ
4. รองรับ protocol: STX, HP-05

**Auto-Reconnect (v1.1):** After page refresh, the system automatically reconnects to the previously used scale using saved configuration. No need to manually select the port again.

**การเชื่อมต่อใหม่อัตโนมัติ (v1.1):** หลังจากรีเฟรชหน้า ระบบจะเชื่อมต่อกับเครื่องชั่งที่ใช้ก่อนหน้าโดยอัตโนมัติ ไม่ต้องเลือก port ใหม่

### Reweigh Function / ฟังก์ชันชั่งซ้ำ

If weight needs correction:
1. Select the dropoff
2. Choose "Reweigh" option
3. Enter `reweight_reason` (required)
4. Record new weight

หากต้องการแก้ไขน้ำหนัก:
1. เลือก Dropoff
2. เลือกตัวเลือก "ชั่งซ้ำ"
3. ใส่ `reweight_reason` (จำเป็น)
4. บันทึกน้ำหนักใหม่

---

## 6. Truck Terminal / หน้าจอชั่งรถ

### Accessing the Terminal / การเข้าใช้งาน

**URL:** `/pos/truck?session=SES-XXXXXX`

Same login process as POS Terminal.

### Terminal Interface / หน้าจอการทำงาน

| Tab | Thai | Purpose |
|-----|------|---------|
| Gross | น้ำหนักรวม | Record truck weight WITH scrap |
| Tare | น้ำหนักเปล่า | Record truck weight AFTER unloading |
| Summary | สรุป | View net weight and variance |

### Recording Truck Weight / บันทึกน้ำหนักรถ

**For Gross Weight / สำหรับน้ำหนักรวม:**
1. Search for Dropoff
2. Go to **Gross** tab
3. Enter or capture weight
4. Click **Save Weight**
5. Confirm in popup
6. Thermal receipt prints automatically

**For Tare Weight / สำหรับน้ำหนักเปล่า:**
1. Same dropoff should be selected
2. Go to **Tare** tab
3. Enter or capture weight (must be less than gross)
4. Click **Save Weight**
5. Confirm in popup
6. Thermal receipt prints automatically

### Auto-Print Behavior / การพิมพ์อัตโนมัติ

**(v1.1 Enhanced)** After each weight is saved and confirmed:
- System automatically opens print dialog with **Truck Weight Thermal** format
- Receipt shows: License plate, weight type, weight value, time, entry method, QR code
- Print triggers immediately after successful save confirmation

**(v1.1 ปรับปรุง)** หลังจากบันทึกและยืนยันน้ำหนักแต่ละครั้ง:
- ระบบเปิดหน้าต่างพิมพ์อัตโนมัติด้วยฟอร์แมต **Truck Weight Thermal**
- ใบเสร็จแสดง: ทะเบียนรถ, ประเภทน้ำหนัก, ค่าน้ำหนัก, เวลา, วิธีบันทึก, QR code
- พิมพ์ทันทีหลังจากยืนยันการบันทึกสำเร็จ

---

## 7. Printing & Documents / การพิมพ์และเอกสาร

### Available Print Formats / รูปแบบการพิมพ์ที่มี

| Print Format | DocType | Size | Use Case |
|--------------|---------|------|----------|
| Scrap Weight Thermal | Scrap Weight | 80mm | Auto-print after scrap weighing |
| Truck Weight Thermal | Truck Weight | 80mm | Auto-print after truck weighing |
| ใบคิวสองภาษา | Dropoff | A4 | Full dropoff summary with letterhead |
| ใบสรุปการส่งมอบ | POS Order | A4 | Order fulfillment summary |
| Weight Receipt | POS Order | A4 | Original format (legacy) |

### Auto-Print Triggers / การพิมพ์อัตโนมัติ

| Action | Print Format | Location |
|--------|--------------|----------|
| Save Scrap Weight | Scrap Weight Thermal | POS Terminal |
| Save Truck Weight | Truck Weight Thermal | Truck Terminal |

### Manual Printing from Desk / การพิมพ์เองจาก Desk

**English:**
1. Open the document (Dropoff, POS Order, etc.)
2. Click **Menu** (three dots) → **Print**
3. Select print format from dropdown
4. Click **Print**

**ภาษาไทย:**
1. เปิดเอกสาร (Dropoff, POS Order, ฯลฯ)
2. คลิก **เมนู** (จุดสามจุด) → **พิมพ์**
3. เลือกรูปแบบการพิมพ์จาก dropdown
4. คลิก **พิมพ์**

### Print Format Features / คุณสมบัติรูปแบบการพิมพ์

**Thermal Receipts (80mm):**
- QR codes for quick lookup
- Entry method indicator (Scale/Manual)
- Compact design for thermal printers

**A4 Documents:**
- Letterhead with company logo (left) and address (right)
- Bilingual (Thai/English) labels
- Signature areas
- Full detail tables

### Uploading Signed Documents / อัปโหลดเอกสารที่เซ็นแล้ว

After printing and getting signatures:
1. Scan the signed document
2. Open the Dropoff or POS Order in Frappe Desk
3. Scroll to **Attachments** section
4. Click **Attach** and upload the scanned file
5. The signed document is now linked to the record

หลังจากพิมพ์และเซ็นเอกสาร:
1. สแกนเอกสารที่เซ็นแล้ว
2. เปิด Dropoff หรือ POS Order ใน Frappe Desk
3. เลื่อนไปที่ส่วน **ไฟล์แนบ**
4. คลิก **แนบ** และอัปโหลดไฟล์ที่สแกน
5. เอกสารที่เซ็นแล้วจะเชื่อมโยงกับบันทึก

---

## 8. Desk Operations / การใช้งานผ่าน Desk

### Accessing Documents / การเข้าถึงเอกสาร

All documents can be viewed and edited from Frappe Desk:

| Document | Path |
|----------|------|
| POS Order | Scrap Metal Suite > POS Order |
| Dropoff | Scrap Metal Suite > Dropoff |
| Scrap Weight | Scrap Metal Suite > Scrap Weight |
| Truck Weight | Scrap Metal Suite > Truck Weight |
| POS Session | Scrap Metal Suite > POS Session |
| Scale | Scrap Metal Suite > Scale |

### List View Features / คุณสมบัติหน้ารายการ

- **Filters**: Use standard filters to find documents
- **Status indicators**: Color-coded status badges
- **Calendar view**: Available for Dropoff (click calendar icon)
- **Export**: Export data to Excel/CSV

### Document Links / ลิงก์เอกสาร

Documents are linked to each other:

```
POS Order
└── Links to: Dropoff (via Dropoff Order table)

Dropoff
├── Links to: POS Orders (orders table)
├── Links to: Scrap Weights (automatic)
└── Links to: Truck Weights (automatic)

Scrap Weight
└── Links to: Dropoff

Truck Weight
└── Links to: Dropoff
```

### Printing from Desk / การพิมพ์จาก Desk

For any document:
1. Open the document
2. Click **Menu** (⋮) → **Print**
3. Select format:
   - For Dropoff: "ใบคิวสองภาษา"
   - For POS Order: "ใบสรุปการส่งมอบ"
4. Print or download as PDF

### Editing Completed Dropoffs / แก้ไข Dropoff ที่เสร็จแล้ว

Completed dropoffs CAN be edited:
- Weights can be adjusted
- Re-allocation happens automatically on save
- Orders cannot be removed once completed (validation enforced)

Dropoff ที่เสร็จแล้วสามารถแก้ไขได้:
- น้ำหนักสามารถปรับได้
- การจัดสรรใหม่เกิดขึ้นอัตโนมัติเมื่อบันทึก
- ไม่สามารถลบใบสั่งซื้อออกได้เมื่อเสร็จแล้ว

### Reports / รายงาน

Standard Frappe reports are available:
- Go to: **Scrap Metal Suite > Reports**
- Or use Query Report builder for custom reports

---

## Appendix A: Keyboard Shortcuts / ปุ่มลัด

| Shortcut | Action |
|----------|--------|
| `Ctrl + S` | Save document |
| `Ctrl + P` | Print |
| `Ctrl + E` | Edit mode |
| `/` | Focus search bar |

---

## Appendix B: Troubleshooting / การแก้ไขปัญหา

### Scale Not Connecting / เครื่องชั่งไม่เชื่อมต่อ

1. Ensure using Chrome or Edge browser
2. Check USB cable connection
3. Try different baud rates in Scale settings
4. Use `/scale-test` page to diagnose

### Print Not Working / พิมพ์ไม่ได้

1. Check browser popup blocker settings
2. Ensure printer is connected and online
3. Try manual print from Menu → Print

### Weight Not Saving / น้ำหนักไม่บันทึก

1. Ensure Dropoff is selected
2. Check weight is greater than 0
3. For reweight, reason is required
4. Check browser console for errors (F12)

---

**End of User Manual**

*Document generated: 2026-01-18*
*Version: 1.1*

---

### Version History / ประวัติเวอร์ชัน

| Version | Date | Changes |
|---------|------|---------|
| 1.1 | 2026-01-18 | Added: Scale auto-reconnect, entry method tracking, enhanced truck terminal auto-print |
| 1.0 | 2026-01-15 | Initial release |
