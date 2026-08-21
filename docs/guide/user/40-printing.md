# Printing & Labels — Operator Guide / คู่มือผู้ใช้งาน

> **Status:** Production
> **Who / ใคร:** POS Operator (ผู้ปฏิบัติงานหน้าลาน), Truck Operator (ผู้ชั่งรถ), Production Operator (ผู้คัดแยก), Manager (ผู้จัดการ), Accountant (พนักงานบัญชี)
> **Where / ที่ไหน:** POS Terminal `/pos/terminal` · Truck Terminal `/pos/truck` · Desk (หน้าจอหลังบ้าน) for A4 documents
> **Last verified / ตรวจสอบล่าสุด:** 2026-08-21 against `feature/container-redesign`

---

> ### ⚠️ กฎเหล็ก: ชื่อสินค้าเป็นภาษาไทยเสมอ / Item names are always Thai
>
> ชื่อสินค้า เช่น **ทองแดงปอก** หรือ **อลูมิเนียมฉาก** คือ *ตัวระบุสินค้า* ไม่ใช่ป้ายกำกับ ระบบจะไม่แปลชื่อสินค้าเป็นภาษาอังกฤษ ไม่ว่าจะบนหน้าจอ บนสติ๊กเกอร์ บนใบเสร็จ หรือในข้อความแจ้งเตือน
>
> Item names such as **ทองแดงปอก** or **อลูมิเนียมฉาก** are the *identifier*, not a label. They are never translated — not on screen, not on a sticker, not on a receipt, not in an error message. An English "equivalent" would be an alias that exists nowhere else in the system, and paying out the wrong grade is a real consequence.
>
> ถ้าเห็นชื่อสินค้าเป็นภาษาอังกฤษบนเอกสารที่พิมพ์ออกมา **แจ้งทีมพัฒนา** — นั่นคือข้อผิดพลาด
> If you ever see an item name in English on printed output, **report it** — that is a bug.

---

## 1. What gets printed, and when / เอกสารที่พิมพ์

ระบบพิมพ์เอกสาร 8 แบบ แบ่งเป็นสองกลุ่มใหญ่ — **กลุ่มที่พิมพ์อัตโนมัติหน้าลาน** และ **กลุ่มที่พิมพ์เองจากหลังบ้าน**

The system prints eight documents, in two groups — **printed automatically at the yard**, and **printed by hand from the desk**.

### 1.1 พิมพ์อัตโนมัติ / Printed automatically

เอกสารสามแบบนี้ออกมาเองเมื่อคุณกดปุ่ม ไม่ต้องสั่งพิมพ์
These three come out on their own when you press a button — you never choose a format.

| เอกสาร / Document | พิมพ์เมื่อไหร่ / Printed when | กระดาษ / Paper |
|---|---|---|
| **สติ๊กเกอร์ภาชนะ**<br>Container Sticker | กดปุ่ม **Save & Print Sticker** หลังชั่งถุง<br>หรือกด **ชั่งใหม่ / Reweigh** | สติ๊กเกอร์ 50 × 80 มม. |
| **ใบชั่งสินค้า**<br>Scrap Weight receipt | กดปุ่ม **Finish Container Weighing** (จบการชั่ง) | ใบเสร็จความร้อน 80 มม. |
| **ใบชั่งรถ**<br>Truck Weight ticket | บันทึกน้ำหนักรถ (ขาเข้า หรือ ขาออก) | ใบเสร็จความร้อน 80 มม. |

### 1.2 พิมพ์เองจากหลังบ้าน / Printed by hand from the desk

เอกสาร A4 ห้าแบบนี้ **ไม่พิมพ์อัตโนมัติ** ต้องเปิดเอกสารในหน้าจอหลังบ้านแล้วกด Print
These five A4 documents **never print automatically**. Open the record in the desk and press Print.

| เอกสาร / Document | ของเอกสารอะไร / For which record | ใครใช้ / Who uses it |
|---|---|---|
| **ใบส่งสินค้า** (ใบคิวสองภาษา)<br>Drop-off Receipt | Dropoff | ผู้จัดการ, ผู้ขาย / Manager, supplier |
| **ใบสรุปการส่งมอบ**<br>Fulfillment Summary | POS Order | ผู้จัดการ / Manager |
| **ใบยืนยันราคา**<br>Price Lock | SMT Price Lock | ผู้ขาย / Supplier |
| **ใบสั่งซื้อ**<br>Purchase Order | SMT Purchase Order | บัญชี / Accounting |
| **ใบคัดแยก**<br>Sorting Report | Dropoff Final | ผู้คัดแยก, ผู้ตรวจสอบ / Sorter, reviewer |

ระบบเลือกแบบฟอร์มที่ถูกต้องให้อัตโนมัติเมื่อคุณกด Print — ไม่ต้องเลือกเอง
The system pre-selects the right format when you press Print — you do not pick from the list.

> **ยกเว้น / One exception:** ภาชนะ (Container) ไม่มีแบบฟอร์มตั้งต้น ถ้าพิมพ์จากหลังบ้านต้องเลือก **Scrap Weight Container Sticker** เองจากรายการ
> Containers have no default format. Printing one from the desk means picking **Scrap Weight Container Sticker** from the dropdown yourself.

---

## 2. The two printers / เครื่องพิมพ์สองเครื่อง

หน้าลานใช้เครื่องพิมพ์ **สองเครื่อง** ที่ใส่กระดาษคนละแบบ ใช้สลับกันไม่ได้
The yard runs **two printers** with different paper. They are not interchangeable.

```
┌─────────────────────────────┐     ┌─────────────────────────────┐
│  เครื่องพิมพ์ใบเสร็จ            │     │  เครื่องพิมพ์สติ๊กเกอร์          │
│  Thermal receipt printer    │     │  Sticker / label printer    │
│                             │     │                             │
│  กระดาษม้วน 80 มม.            │     │  สติ๊กเกอร์ 50 × 80 มม.       │
│  80 mm continuous roll      │     │  50 × 80 mm die-cut labels  │
│  ยาวเท่าไหร่ก็ได้              │     │  ขนาดตายตัว                  │
│                             │     │                             │
│  พิมพ์:                      │     │  พิมพ์:                      │
│   • ใบชั่งสินค้า               │     │   • สติ๊กเกอร์ภาชนะ            │
│   • ใบชั่งรถ                  │     │     (ติดบนถุง/ถัง/พาเลท)      │
└─────────────────────────────┘     └─────────────────────────────┘
```

| | ใบเสร็จ / Receipt | สติ๊กเกอร์ / Sticker |
|---|---|---|
| กว้าง / Width | 80 มม. | 50 มม. |
| ยาว / Length | ต่อเนื่อง ตัดเอง / continuous, you tear it | 80 มม. ตายตัว / fixed |
| เอกสาร / Documents | ใบชั่งสินค้า, ใบชั่งรถ | สติ๊กเกอร์ภาชนะ |
| ให้ใคร / Goes to | ผู้ขาย (ลูกค้า) / the supplier | ติดบนถุง — ใช้ภายใน / on the bag, internal |

**เอกสาร A4 ทั้งห้าแบบ** พิมพ์ที่เครื่องพิมพ์สำนักงานปกติ ไม่ใช่สองเครื่องนี้
**The five A4 documents** print on the ordinary office printer, not on either of these.

> **สำคัญ / Important:** ระบบไม่ได้เลือกเครื่องพิมพ์ให้ — **หน้าต่างพิมพ์ของเบราว์เซอร์** เป็นตัวเลือก ถ้าเครื่องหนึ่งพิมพ์งานของอีกเครื่องหนึ่ง แปลว่าเครื่องพิมพ์ตั้งต้น (default printer) ของเบราว์เซอร์ตั้งผิด ไม่ใช่ระบบผิด
> The app does not choose a printer — **the browser's print dialog** does. If one printer produces the other one's job, the browser's default printer is set wrong. That is a browser setting, not an app setting.

---

## 3. Every document explained / เอกสารแต่ละแบบ

### 3.1 สติ๊กเกอร์ภาชนะ / Container Sticker

**ของอะไร:** ภาชนะหนึ่งใบ (ถุง / ถัง / พาเลท) หนึ่งเกรด หนึ่งน้ำหนัก
**For:** one container (bag / bin / pallet), one grade, one weight
**กระดาษ:** สติ๊กเกอร์ 50 × 80 มม. · **พิมพ์เมื่อ:** อัตโนมัติ เมื่อกด Save & Print Sticker หรือ ชั่งใหม่

```
   ← 50 มม. →
┌──────────────────┐
│  CTN-2608-00003  │ ← เลขภาชนะ / bag number
│ ↻ REWEIGHT•ชั่งซ้ำ│ ← เฉพาะเมื่อชั่งใหม่ / only if reweighed
├──────────────────┤
│    ┌──────────┐  │
│    │ ▄▀█▄ QR  │  │ ← สแกนได้ / scannable
│    │ █▄▄▀ ▄█▀ │  │
│    └──────────┘  │
│                  │
│    ทองแดงปอก      │ ← เกรด (ไทยเสมอ) / grade, always Thai
├══════════════════┤
│      275.0  kg   │ ← น้ำหนักตัวใหญ่ / big weight
├══════════════════┤
│ Drop-off         │
│    DO-260821-013 │
│ ผู้ขาย • Supplier │
│  ร้านรับซื้อของเก่า │
│ ทะเบียน • Plate   │
│          70-1234 │
│ ผู้ชั่ง • Operator │
│      สมชาย ใจดี   │
│ วันที่ • Date     │
│ 2026-08-21 18:39 │
└──────────────────┘
```

**ต้องมีครบ 6 อย่างเสมอ / Six fields must always appear:** เลขใบส่งมอบ (Drop-off), ชื่อผู้ขาย (Supplier), วันที่ (Date), ชื่อสินค้า (Item), ผู้ชั่ง (Operator), ทะเบียนรถ (Plate).
ถ้าขาดข้อใดข้อหนึ่ง **อย่าติดสติ๊กเกอร์** — แจ้งผู้จัดการ / If any is missing, **do not use the label** — tell your manager.

**เลขภาชนะคือชื่อเอกสาร** `CTN-YYMM-#####` ไม่มีเลข "ถุงที่ 1, 2, 3" อีกแล้ว
The bag number *is* the document name, `CTN-YYMM-#####`. There is no separate "bag 1, 2, 3" counter any more.

---

### 3.2 ใบชั่งสินค้า / Scrap Weight receipt

**ของอะไร:** ทั้งใบส่งมอบ — รวมทุกถุง สรุปเป็นรายเกรด
**For:** the whole Drop-off — every bag, summed per grade
**กระดาษ:** ใบเสร็จความร้อน 80 มม. · **พิมพ์เมื่อ:** อัตโนมัติ เมื่อกด **Finish Container Weighing**
**ให้ใคร:** ผู้ขาย — นี่คือใบเสร็จที่ลูกค้าเอากลับไป / **Goes to:** the supplier. This is the customer's receipt.

```
        ← 80 มม. →
╔══════════════════════════════════════╗
║          Scrap Metal Trading         ║
║ 88/88 หมู่ 1 ต.ท่าไม้ อ.ลาดหลุมแก้ว จ.ปทุมธานี ║
║             ใบชั่งสินค้า              ║
║        เลขที่: WGT-260427-00005       ║
╟ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╢
║ วันที่:                    27/04/2026 ║
║ Drop-off:           DO-260427-00006  ║
║ ทะเบียนรถ:                  70-1234  ║
╟ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╢
║ ผู้ขาย:              ร้านรับซื้อของเก่า ║
╟ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╢
║ ┌──────────────────────────────────┐ ║  ← เฉพาะใบแก้ไข
║ │    ** ฉบับแก้ไข • AMENDED **     │ ║     only on a corrected
║ │  แทนที่ฉบับ WGT-260427-00004     │ ║     receipt
║ └──────────────────────────────────┘ ║
║                                      ║
║ รายการสินค้า • Items                  ║
║ ─────────────────────────────────────║
║ ทองแดงปอก (3 ภาชนะ)         95.00 kg ║
║ อลูมิเนียมฉาก (2 ภาชนะ)      41.50 kg ║
║ ══════════════════════════════════════║
║ น้ำหนักรวม / Total:        136.50 kg ║ ← ตัวใหญ่สุด
║ จำนวนภาชนะรวม / Bags:              5 ║
╟ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╢
║        ผู้ชั่ง: สมชาย ใจดี             ║
║   พิมพ์เมื่อ: 21/08/2026 18:39:44     ║
║        ขอบคุณที่ใช้บริการ              ║
╟ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╢
║          [QR]  Drop-off              ║
║               DO-260427-00006        ║
║          [QR]  ใบชั่งสินค้า / Scrap    ║
║               WGT-260427-00005       ║
╟ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╢
║      - - - - - ตัดตรงนี้ - - - - -    ║
╚══════════════════════════════════════╝
```

**หนึ่งบรรทัดคือหนึ่งเกรด ไม่ใช่หนึ่งถุง** ตัวเลขในวงเล็บคือจำนวนถุงของเกรดนั้น
**One line = one grade, not one bag.** The number in brackets is how many bags of that grade.

**ฉบับแก้ไข / Amended:** ถ้าเปิดใบส่งมอบกลับมาชั่งเพิ่ม (Reopen) แล้วจบการชั่งใหม่ ใบเดิมจะถูกยกเลิกและออกใบใหม่ที่มีกรอบ **ฉบับแก้ไข • AMENDED** พร้อมเลขใบเดิม — **เก็บใบเก่าคืนจากลูกค้าถ้าทำได้**
If a Drop-off is reopened and finished again, the old receipt is cancelled and a new one prints with the **AMENDED** box and the old number on it. **Take the old copy back from the customer if you can.**

---

### 3.3 ใบชั่งรถ / Truck Weight ticket

**ของอะไร:** การชั่งรถหนึ่งครั้ง — ขาเข้า (Gross) หรือ ขาออก (Tare)
**For:** one weighbridge reading — inbound (Gross) or outbound (Tare)
**กระดาษ:** ใบเสร็จความร้อน 80 มม. · **พิมพ์เมื่อ:** อัตโนมัติ ทันทีที่บันทึกน้ำหนัก

```
╔══════════════════════════════════════╗
║          Scrap Metal Trading         ║
║ 88/88 หมู่ 1 ต.ท่าไม้ อ.ลาดหลุมแก้ว จ.ปทุมธานี ║
║              ใบชั่งรถ                 ║ ← + "(ชั่งซ้ำ)" ถ้าชั่งใหม่
║        เลขที่: TW-260427-00008        ║
╟ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╢
║                                      ║
║             900.00                   ║ ← ตัวเลขใหญ่มาก อ่านไกลได้
║               Kg                     ║   huge, readable at arm's length
║                                      ║
║    ┌──────────┐   ┏━━━━━━━━━━┓       ║
║    │ [ ] ขาเข้า│   ┃ [X] ขาออก┃       ║ ← กรอบหนา = อันที่เลือก
║    │     Gross│   ┃      Tare┃       ║   thick box = the one selected
║    └──────────┘   ┗━━━━━━━━━━┛       ║
╟ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╢
║ วันที่/เวลา:         27/04/2026 13:10 ║
║ ทะเบียนรถ:                  70-1234  ║
║ Drop-off:           DO-260427-00006  ║
╟ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╢
║ ผู้ขาย:              ร้านรับซื้อของเก่า ║
║ ┌──────────────────┬─────────────────┐║
║ │ วิธีบันทึก:       │ รูปภาพ:         │║
║ │ [M] Manual       │ ไม่มี            │║ ← [A] = อ่านจากตราชั่ง
║ └──────────────────┴─────────────────┘║   [M] = พิมพ์เอง
║ ┌──────────────────────────────────┐ ║
║ │         ** ชั่งซ้ำ **             │ ║ ← เฉพาะเมื่อชั่งใหม่
║ │       <เหตุผลที่ชั่งใหม่>          │ ║
║ └──────────────────────────────────┘ ║
╟ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╢
║       ผู้ชั่ง: สมชาย ใจดี              ║
║      เครื่องชั่ง: ตราชั่งรถ 01          ║
║   พิมพ์เมื่อ: 21/08/2026 18:39:27     ║
║        ขอบคุณที่ใช้บริการ              ║
╟ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╢
║      [QR] Drop-off / [QR] ใบชั่งรถ     ║
╟ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ╢
║      - - - - - ตัดตรงนี้ - - - - -    ║
╚══════════════════════════════════════╝
```

**ตรวจช่องติ๊กทุกครั้ง / Always check the tick box.** `[X] ขาเข้า Gross` = รถเข้ามาพร้อมของ · `[X] ขาออก Tare` = รถออกไปเปล่า ติดผิดช่อง = น้ำหนักสุทธิผิด

**`[A]` กับ `[M]`:** `[A] Scale` คือเครื่องอ่านน้ำหนักจากตราชั่งเอง · `[M] Manual` คือคนพิมพ์ตัวเลขเข้าไป — ผู้จัดการดูช่องนี้เวลาสอบทาน
`[A] Scale` means the reading came from the scale itself; `[M] Manual` means someone typed it. Managers look at this field during review.

---

### 3.4 ใบส่งสินค้า / Drop-off Receipt (A4)

**ของอะไร:** สรุปทั้งใบส่งมอบแบบเต็ม — น้ำหนักรถ สรุปเกรด การตรวจสอบส่วนต่าง และช่องเซ็นชื่อ
**For:** the complete Drop-off summary — truck weights, grade summary, variance checks, signature blocks
**กระดาษ:** A4 · **พิมพ์เมื่อ:** พิมพ์เองจากหลังบ้าน

```
┌──────────────────────────────────────────────────────────────┐
│ [โลโก้]                        88/88 ถนน บางบัวทอง – สุพรรณบุรี │
│                               ปทุมธานี 12140                  │
├──────────────────────────────────────────────────────────────┤
│ ใบส่งสินค้า / Drop-off Receipt          DO-260427-00006      │
│                                          ─── Completed ───   │
├──────────────────────────────────────────────────────────────┤
│ ข้อมูลทั่วไป / General Information                            │
│ วันที่นัดหมาย 27/04/2026 09:00  │ ทะเบียนรถ 70-1234           │
│ ผู้ขาย ร้านรับซื้อของเก่า          │ สถานะตรวจสอบ Pending        │
├──────────────────────────────────────────────────────────────┤
│ ใบสั่งซื้อที่เชื่อมโยง / Linked Orders (PO)                    │
│ 1  ORD-260427-00002                          1,000.00 kg     │
├──────────────────────────────────────────────────────────────┤
│ น้ำหนักรถ / Truck Weight                                      │
│ ขาเข้า/Gross   123,213.00   27/04 13:10   ตราชั่งรถ 01        │
│ ขาออก/Tare     123,100.00   27/04 13:55   ตราชั่งรถ 01        │
│ น้ำหนักสุทธิ/Net    113.00                                     │
├──────────────────────────────────────────────────────────────┤
│ สรุปรายการสินค้า / Item Summary                                │
│ เกรด•Grade     จำนวน•Bags   น้ำหนัก•Weight    สถานะ•Status    │
│ ทองแดงปอก           3          95.0 kg           OK          │
│ อลูมิเนียมฉาก        2          41.5 kg      ⚠ นอกแผน         │
│ รวม                 5         136.5 kg            ⚠          │
├──────────────────────────────────────────────────────────────┤
│ การตรวจสอบน้ำหนัก / Weight Verification                       │
│ 1. น้ำหนักรถสุทธิ vs สินค้า  │ 2. น้ำหนักที่แจ้ง vs จริง        │
│    -23.50 kg (-1.20%) ✓ ผ่าน │    3.00 kg (2.20%) ✗ ไม่ผ่าน   │
├──────────────────────────────────────────────────────────────┤
│ เอกสารที่เกี่ยวข้อง / Related Documents                        │
│ ชั่งรถ (ขาเข้า)  TW-…-00003   123,213.00  27/12 18:22  [M]    │
│ ชั่งสินค้า/Scrap WGT-…-00001       12.00       -       [M]    │
├──────────────────────────────────────────────────────────────┤
│  ______________________        ______________________        │
│  ผู้ส่งสินค้า / Supplier         ผู้รับสินค้า / Receiver         │
│ พิมพ์เมื่อ 21/08/2026 18:39                    Administrator  │
└──────────────────────────────────────────────────────────────┘
```

**⚠ นอกแผน / Unplanned** หมายถึงเกรดนั้นไม่ได้อยู่ในใบสั่งซื้อ — ผู้จัดการต้องดู
**⚠ Unplanned** means that grade was not on the order. A manager needs to look at it.

> **หมายเหตุ / Note:** ช่อง "วันที่-เวลา" ของแถว **ชั่งสินค้า / Scrap** จะขึ้น `-` เสมอ เป็นข้อผิดพลาดที่ทราบแล้ว ให้ดูวันที่จากใบชั่งสินค้าโดยตรง
> The Date-Time cell on the **Scrap** row always shows `-`. This is a known bug — read the date off the Scrap Weight receipt instead.

---

### 3.5 ใบสรุปการส่งมอบ / Fulfillment Summary (A4)

**ของอะไร:** เทียบ "สั่งเท่าไหร่" กับ "รับจริงเท่าไหร่" ของ POS Order หนึ่งใบ
**For:** ordered vs. actually received, for one POS Order
**กระดาษ:** A4 · **พิมพ์เมื่อ:** พิมพ์เองจากหลังบ้าน

```
┌──────────────────────────────────────────────────────────────┐
│ ใบสรุปการส่งมอบ / Fulfillment Summary   ORD-260427-00002     │
│                                          ─── Partial ───     │
├──────────────────────────────────────────────────────────────┤
│ ผู้ขาย ร้านรับซื้อของเก่า        │ วันที่สั่ง 27/04/26            │
├──────────────────────────────────────────────────────────────┤
│ ┌────────────┬────────────┬────────────┬────────────┐        │
│ │ น้ำหนักสั่งซื้อ│ น้ำหนักที่รับ │ ผลต่าง      │ เปอร์เซ็นต์  │        │
│ │ 1,000.00kg │  136.50 kg │ -863.50 kg │     13.7%  │        │
│ └────────────┴────────────┴────────────┴────────────┘        │
├──────────────────────────────────────────────────────────────┤
│ รายการเปรียบเทียบ / Items Comparison                          │
│ รายการ/Item      สั่งซื้อ      รับจริง      ผลต่าง/Variance    │
│ ทองแดงปอก        600.00       95.00        -505.00           │
│ อลูมิเนียมฉาก     400.00       41.50        -358.50           │
│ รวม / Total    1,000.00      136.50        -863.50           │
├──────────────────────────────────────────────────────────────┤
│ การส่งมอบที่เกี่ยวข้อง / Related Dropoffs                       │
│ DO-260427-00006   27/04/26 09:00   136.50 kg   Completed     │
├──────────────────────────────────────────────────────────────┤
│  ผู้ส่ง / Supplier               ผู้รับ / Receiver               │
└──────────────────────────────────────────────────────────────┘
```

---

### 3.6 ใบยืนยันราคา / Price Lock (A4)

**ของอะไร:** ราคาที่ล็อกไว้ให้ผู้ขาย — เกรดไหน ราคาเท่าไหร่ หมดอายุเมื่อไหร่ ส่งมาแล้วเท่าไหร่
**For:** the locked quote — which grades, at what rate, expiring when, and how much has been delivered against it
**กระดาษ:** A4 · **พิมพ์เมื่อ:** พิมพ์เองจากหลังบ้าน · **ให้ใคร:** ผู้ขาย

```
┌──────────────────────────────────────────────────────────────┐
│ ใบยืนยันราคา / Price Lock                 PL-2026-00013      │
│                                            ─── Active ───    │
├──────────────────────────────────────────────────────────────┤
│ ผู้ขาย ร้านรับซื้อของเก่า      │ วันที่ / PO Date  15/04/2026    │
│ วันหมดอายุ / Expiry 30/04/2026 │ สถานะอัปเดต 15/04/26 18:00    │
├──────────────────────────────────────────────────────────────┤
│ รายการสินค้า / Locked Items                                   │
│ # รายการ/Item  ปริมาณ/Qty ราคา/Rate มูลค่า/Amt ชำระแล้ว คงเหลือ│
│ 1 ทองแดงปอก     600.000    285.00 171,000.00  95.000 505.000 │
│ 2 อลูมิเนียมฉาก  400.000     42.50  17,000.00  41.500 358.500 │
│               รวม / Total  188,000.00  40,282.50            │
├──────────────────────────────────────────────────────────────┤
│  ผู้ขาย / Supplier               ผู้รับซื้อ / Buyer              │
└──────────────────────────────────────────────────────────────┘
```

**ถ้าไม่กำหนดวันหมดอายุ** ช่องนั้นจะขึ้น `ไม่กำหนด / No expiry`
If no expiry is set, that field reads `ไม่กำหนด / No expiry`.

---

### 3.7 ใบสั่งซื้อ / Purchase Order (A4)

**ของอะไร:** เอกสารบัญชี — ครอบคลุมใบคัดแยกใบไหนบ้าง และแต่ละรายการคิดราคาจากล็อคราคาหรือราคาตลาด
**For:** the accounting document — which Sorting Reports it covers, and whether each line was priced from a Price Lock or at spot
**กระดาษ:** A4 · **พิมพ์เมื่อ:** พิมพ์เองจากหลังบ้าน · **ให้ใคร:** บัญชี

```
┌──────────────────────────────────────────────────────────────┐
│ ใบสั่งซื้อ / Purchase Order              SMTPL-2026-00010     │
│                                          ─── Submitted ───   │
├──────────────────────────────────────────────────────────────┤
│ ผู้ขาย ร้านรับซื้อของเก่า      │ วันที่ / Final Date 18/07/2026  │
├──────────────────────────────────────────────────────────────┤
│ ใบส่งมอบ / Dropoff Finals                                     │
│ 1 DFL-260718-00003      18/07/2026            136.500 kg     │
├──────────────────────────────────────────────────────────────┤
│ รายการจัดสรร / Allocations                                    │
│ # รายการ/Item  ปริมาณ  แหล่ง/Source  ใบยืนยันราคา  ราคา  มูลค่า │
│ 1 ทองแดงปอก    95.000 ล็อคราคา/PO  PL-2026-00013 285.00 27,075│
│ 2 อลูมิเนียมฉาก 41.500 ตลาด/Spot    -             40.00  1,660│
│                        ยอดรวม PO / PO Total        27,075.00 │
│                        ยอดรวม Spot / Spot Total     1,660.00 │
│ ══════════════════════════════════════════════════════════════│
│                    ยอดรวมทั้งหมด / Grand Total   ฿ 28,735.00 │
├──────────────────────────────────────────────────────────────┤
│  ผู้ขาย / Supplier               พนักงานบัญชี / Accountant       │
└──────────────────────────────────────────────────────────────┘
```

**ล็อคราคา / PO** = ราคาที่ตกลงล่วงหน้า · **ตลาด / Spot** = ราคาวันนั้น
**PO** = a rate agreed in advance. **Spot** = the day's rate.

---

### 3.8 ใบคัดแยก / Sorting Report (A4)

**ของอะไร:** ผลการคัดแยก — ของดีเท่าไหร่ ของที่ไม่ต้องการเท่าไหร่ เพราะอะไร และน้ำหนักตรงกับใบส่งมอบไหม
**For:** the sorting outcome — how much good material, how much rejected and why, and whether the total reconciles with the Drop-off
**กระดาษ:** A4 · **พิมพ์เมื่อ:** พิมพ์เองจากหลังบ้าน

```
┌──────────────────────────────────────────────────────────────┐
│ ใบคัดแยก / Sorting Report                DFL-260718-00003    │
│                                          ─── Completed ───   │
├──────────────────────────────────────────────────────────────┤
│ ใบส่งมอบ DO-260718-00012  │ ผู้ขาย ร้านรับซื้อของเก่า           │
│ ทะเบียนรถ 70-1234         │ สถานะตรวจสอบ ─Verified─          │
├──────────────────────────────────────────────────────────────┤
│ สินค้าดี / Good Items                                         │
│ 1 ทองแดงปอก        Kg              92.300                    │
│ 2 อลูมิเนียมฉาก     Kg              38.700                    │
│        รวมสินค้าดี / Good Total    131.000                    │
├──────────────────────────────────────────────────────────────┤
│ ของที่ไม่ต้องการ / Unwanted Items                              │
│ 1 ทองแดงปอก   ปนเปื้อน   Kg          5.500                    │
│   รวมของที่ไม่ต้องการ / Unwanted Total 5.500                   │
├──────────────────────────────────────────────────────────────┤
│ สรุปค่าเบี่ยงเบน / Variance Summary                            │
│ น้ำหนักจาก Dropoff        136.500 kg                          │
│ น้ำหนักตรวจสอบรวม          136.500 kg                          │
│ ค่าเบี่ยงเบน / Variance      0.000 kg (0.00%)                 │
│ ผลการตรวจ / Result        ✓ ผ่าน / Pass                       │
├──────────────────────────────────────────────────────────────┤
│  ผู้คัดแยก / Sorter              ผู้ตรวจสอบ / Reviewer           │
└──────────────────────────────────────────────────────────────┘
```

---

## 4. Walkthrough: printing a bag sticker / พิมพ์สติ๊กเกอร์

**สถานการณ์ / Scenario:** รถของ *ร้านรับซื้อของเก่า* ทะเบียน 70-1234 มาถึงแล้ว คุณกำลังชั่งถุงทองแดงปอกถุงที่สาม น้ำหนัก 275.0 กก.
A truck from *ร้านรับซื้อของเก่า*, plate 70-1234, has arrived. You are weighing the third bag of ทองแดงปอก at 275.0 kg.

1. **เลือกใบส่งมอบ / Select the Drop-off** — สแกน QR หรือพิมพ์ `DO-260821-013` ในช่องค้นหา
   → หน้าจอโหลดใบส่งมอบ พร้อมรายการถุงที่ชั่งไปแล้วทางขวา
   → The Drop-off loads, with the bags already weighed listed on the right.

2. **เลือกเกรด / Tap the grade** — แตะ **ทองแดงปอก** ในแผงซ้าย
   → ชื่อเกรดขึ้นบนการ์ดชั่ง / The grade appears on the weighing card.

3. **วางถุงบนตราชั่ง / Put the bag on the scale**
   → ตัวเลขน้ำหนักวิ่งขึ้นแล้วนิ่งที่ `275.0`
   → The weight climbs and settles at `275.0`.

4. **ตรวจก่อนกด / Check before you press** — เกรดถูกไหม? น้ำหนักนิ่งแล้วหรือยัง?
   ถ้าพิมพ์น้ำหนักเอง ตัวเลขจะไม่ถูกทับด้วยค่าจากตราชั่ง
   If you typed the weight by hand, the scale will not overwrite it.

5. **กด Save & Print Sticker** (บันทึก & พิมพ์สติ๊กเกอร์)
   → ข้อความเขียว **เพิ่มภาชนะแล้ว** ขึ้นมา
   → แถวใหม่โผล่ในรายการถุงทางขวา
   → **สติ๊กเกอร์พิมพ์ออกมาเอง** ไม่มีหน้าต่างให้เลือกอะไร
   → A green **container added** toast appears, a new row joins the journal, and **the sticker prints by itself** — no dialog.

6. **ติดสติ๊กเกอร์บนถุงทันที / Stick it on the bag immediately** — ก่อนหยิบถุงถัดไป
   Before you touch the next bag.

**เสร็จแล้วได้อะไร / Result:** ถุงมีป้าย `CTN-2608-00003` ติดอยู่ สแกน QR แล้วกลับมาที่ถุงใบนี้ได้ตลอด
The bag now carries `CTN-2608-00003`. Scanning its QR will always bring you back to it.

> **ถ้าสติ๊กเกอร์ไม่ออก / If no sticker comes out:** ข้อมูลถูกบันทึกแล้ว — แถวขึ้นในรายการแปลว่าเซฟสำเร็จ ให้พิมพ์ซ้ำตามข้อ 5 ด้านล่าง **อย่ากด Save ซ้ำ** เพราะจะได้ถุงซ้ำสองใบ
> The data is already saved — the row in the journal proves it. Reprint using §5. **Do not press Save again**, or you will create a duplicate bag.

---

## 5. Walkthrough: reprinting / พิมพ์ซ้ำ

### 5.1 พิมพ์สติ๊กเกอร์ถุงซ้ำ / Reprint one bag's sticker

**สถานการณ์:** สติ๊กเกอร์ของถุง `CTN-2608-00003` ฉีกขาด / The sticker on bag `CTN-2608-00003` is torn.

1. หาแถวของถุงนั้นในรายการทางขวา / Find its row in the journal on the right.
2. กดปุ่ม **พิมพ์สติ๊กเกอร์ / Print Sticker** ในแถวนั้น
   → สติ๊กเกอร์ใบใหม่พิมพ์ออกมา เนื้อหาเหมือนเดิมทุกอย่าง
   → An identical sticker prints.

**พิมพ์ซ้ำได้ไม่จำกัด** ไม่สร้างถุงใหม่ ไม่เปลี่ยนน้ำหนัก / Reprint as often as you like — it creates nothing and changes nothing.

**อีกทางหนึ่ง / Alternative:** สแกน QR บนสติ๊กเกอร์เก่า (ถ้ายังอ่านได้) แล้วเลือก **พิมพ์สติ๊กเกอร์** จากเมนู — ดูข้อ 6
Scan the old sticker's QR (if still readable) and pick **Print Sticker** from the menu — see §6.

### 5.2 พิมพ์ใบชั่งสินค้าซ้ำ / Reprint the customer receipt

**สถานการณ์:** ลูกค้าทำใบเสร็จหาย หรือกระดาษติดตอนพิมพ์
The customer lost the receipt, or the paper jammed.

1. ให้แน่ใจว่าใบส่งมอบที่ถูกต้องเปิดอยู่บนหน้าจอ / Make sure the right Drop-off is loaded.
2. กดปุ่ม **🖶 Print** ที่แถบด้านบนขวา / Press the **🖶 Print** button in the top bar.
   → ระบบดึงใบล่าสุดที่ยังใช้งานอยู่ของใบส่งมอบนี้มาพิมพ์
   → The system fetches the current active receipt for this Drop-off and prints it.

**ระบบพิมพ์ใบล่าสุดเสมอ** ถ้าเคยเปิดใบส่งมอบกลับมาแก้ ระบบจะพิมพ์ **ฉบับแก้ไข** ไม่ใช่ใบเก่าที่ยกเลิกไปแล้ว
It always prints the *current* receipt. If the Drop-off was reopened, you get the **AMENDED** version, never the cancelled one.

| ข้อความที่อาจขึ้น / Message you may see | แปลว่า / Means |
|---|---|
| *Select a dropoff first* | ยังไม่ได้เลือกใบส่งมอบ / No Drop-off loaded |
| *No active receipt yet — finish weighing first* | ยังไม่ได้กด Finish Container Weighing / Weighing not finished yet |

### 5.3 พิมพ์ใบชั่งรถซ้ำ / Reprint a truck ticket

ที่หน้าจอชั่งรถ กดปุ่ม **🖶 Print** ที่แถบบน — พิมพ์ใบล่าสุดที่ชั่งไป
On the truck terminal, press **🖶 Print** in the top bar — it reprints the last ticket weighed.

### 5.4 พิมพ์เอกสาร A4 ซ้ำ / Reprint an A4 document

1. เปิดเอกสารในหน้าจอหลังบ้าน (Desk) / Open the record in the desk.
2. กดปุ่ม **Print** ที่มุมขวาบน / Press **Print**, top right.
3. แบบฟอร์มที่ถูกต้องถูกเลือกไว้ให้แล้ว — กด Print ในหน้าต่างเบราว์เซอร์
   The correct format is already selected — press Print in the browser dialog.

---

## 6. Walkthrough: scanning a QR code / สแกน QR

QR ทุกอันในระบบเก็บ **ลิงก์ไปยังเอกสารนั้น** สแกนด้วยมือถือจะเปิดเอกสารในเบราว์เซอร์ สแกนด้วยหน้าจอหน้าลานจะเปิดงานนั้นในระบบ
Every QR in the system holds **a link to that document**. Scanned with a phone it opens the record in a browser; scanned at the terminal it loads the job.

### 6.1 QR ไหนอยู่ที่ไหน / Which QR is where

| เอกสาร / Document | QR ที่มี / QR codes on it |
|---|---|
| สติ๊กเกอร์ภาชนะ | 1 อัน — ของถุงใบนั้น / one — the bag itself |
| ใบชั่งสินค้า | 2 อัน — ใบส่งมอบ + ใบชั่งสินค้า / two — the Drop-off and the receipt |
| ใบชั่งรถ | 2 อัน — ใบส่งมอบ + ใบชั่งรถ / two — the Drop-off and the ticket |

### 6.2 สแกนที่หน้าจอหน้าลาน / Scanning at the terminal

1. กดปุ่ม **สแกน / Scan** — กล้องเปิดขึ้น / The camera opens.
2. เล็งไปที่ QR → มีเสียงบี๊บเมื่ออ่านสำเร็จ / Aim at the QR; a beep confirms the read.
3. ระบบตัดสินใจให้เองว่าเป็นเอกสารอะไร / The system works out what it is:

| สแกนอะไร / What you scanned | เกิดอะไรขึ้น / What happens |
|---|---|
| QR ใบส่งมอบ (`DO-…`) | โหลดใบส่งมอบนั้นขึ้นมา พร้อมทำงานต่อ / Loads that Drop-off, ready to work |
| QR สติ๊กเกอร์ถุง (`CTN-…`) | โหลด **ใบส่งมอบแม่** ของถุงนั้น แล้วไฮไลต์แถวถุงใบนั้นให้เห็น / Loads the bag's **parent Drop-off** and flashes that bag's row |
| QR ใบชั่งสินค้า / ใบชั่งรถ | ⚠️ ใช้ไม่ได้ที่หน้าจอนี้ — จะขึ้น *ไม่พบใบส่งมอบ* ให้สแกน QR ใบส่งมอบบนใบเดียวกันแทน / Not usable here — you get *Dropoff not found*. Scan the Drop-off QR on the same receipt instead. |

### 6.3 พิมพ์เลขเองแทนการสแกน / Typing instead of scanning

ถ้ากล้องเสียหรือ QR อ่านไม่ออก พิมพ์เลขเอกสารลงในช่องค้นหาได้เลย ระบบรู้จักทั้งสองแบบ:
If the camera is broken or the QR is unreadable, type the document number into the search box. The system recognises both:

- ขึ้นต้น `DO-` หรือ `DROP-` → ใบส่งมอบ / a Drop-off
- ขึ้นต้น `CTN-` → ภาชนะ / a container

พิมพ์ตัวพิมพ์เล็กก็ได้ / Lower case works too.

### 6.4 สแกนถุงเพื่อทำงานกับถุงนั้น / Scanning a bag to act on it

จากแถบเครื่องมือของแผงภาชนะ กด **สแกน** แล้วสแกนสติ๊กเกอร์ถุง → เมนูขึ้นมาให้เลือก:
From the container action bar, press **Scan** and scan a bag sticker → a menu appears:

```
CTN-2608-00003 (ทองแดงปอก, 275.00 Kg)
1) ชั่งใหม่ / Reweigh
2) พิมพ์สติ๊กเกอร์ / Print Sticker
3) ยกเลิก / Void
```

พิมพ์หมายเลข 1–3 แล้วกดตกลง / Type 1–3 and confirm.

### 6.5 สแกนด้วยมือถือ / Scanning with a phone

QR เก็บ **ลิงก์เต็มพร้อมชื่อเซิร์ฟเวอร์** สแกนด้วยกล้องมือถือจะเปิดเอกสารในเบราว์เซอร์ ต้องล็อกอินก่อนถึงจะเห็นข้อมูล
The QR holds a **full link including the server name**. A phone camera opens the record in a browser — you must be logged in to see it.

> **หมายเหตุ / Note:** QR ที่พิมพ์จากเครื่องทดสอบจะชี้ไปที่เครื่องทดสอบ ใช้กับมือถือไม่ได้ ให้ใช้เฉพาะเอกสารที่พิมพ์จากระบบจริง
> QRs printed from a test site point at that test site and will not open on a phone. Only production printouts work.

---

## 7. What can go wrong / ปัญหาที่พบบ่อย

| อาการ / Symptom | สาเหตุ / Cause | แก้ยังไง / Fix |
|---|---|---|
| **ตัวหนังสือจาง อ่านไม่ออก โดยเฉพาะภาษาไทย**<br>Faint, hard-to-read text, worst in Thai | ตั้งแต่ 21/08/2026 แบบฟอร์มถูกแก้ให้เป็นตัวดำล้วนและตัวใหญ่ขึ้นแล้ว ถ้ายังจาง = **ตั้งค่าความเข้มเครื่องพิมพ์ต่ำ หรือกระดาษเสื่อม** ไม่ใช่แบบฟอร์ม<br>Templates were fixed on 2026-08-21. Remaining faintness is printer darkness or old paper, not the template | เพิ่มค่า darkness/density ที่เครื่องพิมพ์ · เปลี่ยนม้วนกระดาษใหม่ · **ถ่ายรูปแล้วแจ้งทีม**<br>Turn up darkness, change the roll, **photograph it and report** |
| **สติ๊กเกอร์ไม่ออกหลังกด Save**<br>No sticker after Save | ผู้จัดการปิดสวิตช์พิมพ์อัตโนมัติในโปรไฟล์ · หรือเบราว์เซอร์บล็อกการพิมพ์<br>Auto-print switched off in the profile, or the browser blocked it | ข้อมูล**บันทึกแล้ว** (มีแถวในรายการ) — พิมพ์ซ้ำตามข้อ 5.1 · **ห้ามกด Save ซ้ำ** · แจ้งผู้จัดการให้เปิด Enable Sticker Print<br>Data is saved. Reprint per §5.1. **Never press Save twice.** Ask a manager to switch Enable Sticker Print back on |
| **ใบเสร็จพิมพ์ออกเครื่องสติ๊กเกอร์ (หรือกลับกัน)**<br>Receipt comes out of the sticker printer | เครื่องพิมพ์ตั้งต้นของเบราว์เซอร์ตั้งผิด<br>Wrong default printer in the browser | ตั้ง default printer ของเบราว์เซอร์ให้ตรงกับกระดาษของสถานีนั้น — เป็นการตั้งค่าเบราว์เซอร์ ไม่ใช่ในระบบ<br>Fix the browser's default printer. This is a browser setting, not an app setting |
| **สติ๊กเกอร์พิมพ์เลยขอบ / ข้อความขาด**<br>Sticker overflows or is cut off | ใส่กระดาษผิดขนาด — สติ๊กเกอร์ต้องเป็น **50 × 80 มม.** เท่านั้น<br>Wrong label stock — must be **50 × 80 mm** | เปลี่ยนกระดาษให้ถูกขนาด · ตรวจว่าไดรเวอร์ตั้ง paper size เป็น 50×80 ไม่ใช่ A4<br>Load the right labels; check the driver's paper size |
| **ขึ้น "Printer not found" / ไม่มีหน้าต่างพิมพ์**<br>Printer not found, or no dialog | เครื่องพิมพ์ออฟไลน์ สาย USB หลุด หรือคิวงานค้าง<br>Printer offline, cable out, or a stuck queue | ตรวจไฟและสาย · ล้างคิวงานใน OS · รีเฟรชหน้าจอแล้วพิมพ์ซ้ำ<br>Check power and cable, clear the OS queue, refresh and reprint |
| **ขึ้น "Not allowed to print cancelled documents"**<br>Cannot print cancelled document | พยายามพิมพ์ใบที่ถูกยกเลิกไปแล้ว (เกิดหลังการ Reopen)<br>Trying to print a cancelled receipt after a Reopen | ใช้ปุ่ม **🖶 Print** บนแถบบนแทน — ปุ่มนี้ดึงใบล่าสุดที่ใช้งานอยู่เสมอ<br>Use the top-bar **🖶 Print** button — it always fetches the current receipt |
| **ขึ้น "Document not found" ตอนพิมพ์ใบเสร็จ**<br>Document not found while printing a receipt | ใบส่งมอบที่ผูกอยู่ถูกลบไปแล้ว — ใบเสร็จพิมพ์ไม่ได้ทั้งใบ (ข้อผิดพลาดที่ทราบแล้ว)<br>The linked Drop-off was deleted; the whole receipt fails. Known bug | แจ้งทีมพัฒนา — แก้ที่หน้าลานไม่ได้<br>Report it. There is no operator-side workaround |
| **ช่องวันที่-เวลาแถว "ชั่งสินค้า" ขึ้น `-` บนใบส่งสินค้า A4**<br>Scrap row's Date-Time shows `-` | ข้อผิดพลาดที่ทราบแล้ว / Known bug | ดูวันที่จากใบชั่งสินค้าโดยตรง / Read the date off the Scrap Weight receipt |
| **สแกนสติ๊กเกอร์แล้วขึ้น "ไม่พบใบส่งมอบ"**<br>Scanning gives "Dropoff not found" | สแกน QR ผิดอัน — เผลอสแกน QR ของใบชั่งสินค้า/ใบชั่งรถ<br>Scanned the wrong QR — the receipt's own QR, not the Drop-off's | สแกน QR ที่มีคำว่า **Drop-off** อยู่ใต้ภาพ · หรือพิมพ์เลข `DO-…` เอง<br>Scan the QR labelled **Drop-off**, or type the `DO-…` number |
| **สแกน QR ด้วยมือถือแล้วเปิดไม่ได้**<br>Phone scan does not open | ใบนั้นพิมพ์จากเครื่องทดสอบ QR จึงชี้ไปเครื่องทดสอบ · หรือยังไม่ได้ล็อกอิน<br>Printed from a test site, or you are not logged in | ใช้เฉพาะเอกสารจากระบบจริง · ล็อกอินก่อน<br>Use production printouts; log in first |
| **ชื่อสินค้าขึ้นเป็นภาษาอังกฤษ**<br>Item name printed in English | ผิดกฎเหล็กของระบบ / Violates the cardinal rule | **แจ้งทีมพัฒนาทันที** พร้อมรูปถ่าย / **Report immediately** with a photo |
| **ปุ่ม Print ยังเป็นภาษาอังกฤษทั้งที่สลับเป็นไทยแล้ว**<br>Print button stays English in Thai mode | ข้อผิดพลาดเล็กน้อยที่ทราบแล้ว / Known cosmetic bug | ปุ่มยังใช้งานได้ปกติ ไม่ต้องทำอะไร / The button still works; ignore it |

---

## 8. Quick reference / สรุป

**ปุ่มที่เกี่ยวกับการพิมพ์ / Print buttons**

| ปุ่ม / Button | อยู่ที่ไหน / Where | ทำอะไร / Does |
|---|---|---|
| **Save & Print Sticker** | การ์ดชั่ง / weighing card | บันทึกถุง + พิมพ์สติ๊กเกอร์ / saves the bag and prints its sticker |
| **พิมพ์สติ๊กเกอร์ / Print Sticker** | แต่ละแถวในรายการถุง / each journal row | พิมพ์สติ๊กเกอร์ใบนั้นซ้ำ / reprints that one sticker |
| **🖶 Print** | แถบบน POS Terminal | พิมพ์ใบชั่งสินค้าล่าสุดซ้ำ / reprints the current customer receipt |
| **🖶 Print** | แถบบน Truck Terminal | พิมพ์ใบชั่งรถล่าสุดซ้ำ / reprints the last truck ticket |
| **Finish Container Weighing** | แถบเครื่องมือภาชนะ | จบการชั่ง + พิมพ์ใบชั่งสินค้า / finishes weighing and prints the receipt |
| **Print** | มุมขวาบนของหน้าจอหลังบ้าน / desk, top right | พิมพ์เอกสาร A4 / prints the A4 document |

**เอกสารทั้ง 8 แบบ / All eight documents**

| เอกสาร | กระดาษ | อัตโนมัติ? |
|---|---|---|
| สติ๊กเกอร์ภาชนะ / Container Sticker | สติ๊กเกอร์ 50×80 มม. | ✅ ใช่ / Yes |
| ใบชั่งสินค้า / Scrap Weight | ใบเสร็จ 80 มม. | ✅ ใช่ / Yes |
| ใบชั่งรถ / Truck Weight | ใบเสร็จ 80 มม. | ✅ ใช่ / Yes |
| ใบส่งสินค้า / Drop-off Receipt | A4 | ❌ พิมพ์เอง / Manual |
| ใบสรุปการส่งมอบ / Fulfillment Summary | A4 | ❌ พิมพ์เอง / Manual |
| ใบยืนยันราคา / Price Lock | A4 | ❌ พิมพ์เอง / Manual |
| ใบสั่งซื้อ / Purchase Order | A4 | ❌ พิมพ์เอง / Manual |
| ใบคัดแยก / Sorting Report | A4 | ❌ พิมพ์เอง / Manual |

**เลขเอกสาร / Document numbers**

| ขึ้นต้นด้วย / Starts with | คือ / Is a |
|---|---|
| `DO-` | ใบส่งมอบ / Drop-off |
| `CTN-` | ภาชนะ (ถุง) / Container |
| `WGT-` หรือ `SW-` | ใบชั่งสินค้า / Scrap Weight |
| `TW-` | ใบชั่งรถ / Truck Weight |
| `DFL-` | ใบคัดแยก / Sorting Report |
| `PL-` | ใบยืนยันราคา / Price Lock |
| `ORD-` | คำสั่งซื้อ / POS Order |

**กฎที่ต้องจำ / Rules to remember**

1. **ชื่อสินค้าเป็นภาษาไทยเสมอ** — เห็นเป็นอังกฤษเมื่อไหร่ ให้แจ้ง
   **Item names are always Thai** — report any English one.
2. **ติดสติ๊กเกอร์ทันทีที่พิมพ์** ก่อนหยิบถุงถัดไป
   **Stick the label on immediately**, before the next bag.
3. **สติ๊กเกอร์ไม่ออก ≠ ไม่ได้บันทึก** — ดูว่ามีแถวขึ้นในรายการไหม แล้วพิมพ์ซ้ำ อย่ากด Save ซ้ำ
   **No sticker ≠ not saved** — check the journal row, then reprint. Never Save twice.
4. **พิมพ์ซ้ำได้เสมอ ไม่เสียหาย** — ไม่สร้างข้อมูลใหม่
   **Reprinting is always safe** — it creates nothing.
5. **ใบชั่งสินค้าให้ลูกค้า สติ๊กเกอร์ใช้ภายใน**
   **The receipt goes to the customer; the sticker stays in the yard.**

---

## เอกสารที่เกี่ยวข้อง / Related

- [12 — Drop-off & Container Weighing](12-dropoff-receiving.md) — ขั้นตอนการรับของทั้งหมด / the full receiving flow
- [11 — Truck Terminal](11-truck-terminal.md) — การชั่งรถ / weighbridge operation
- [90 — Troubleshooting](90-troubleshooting.md) — ปัญหาอื่น ๆ ทุกโมดูล / all other symptoms
- [admin/40-printing.md](../admin/40-printing.md) — สำหรับผู้ดูแลระบบ / for developers and admins
