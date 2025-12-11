# คู่มือผู้จัดการ - ระบบ POS รับซื้อเศษโลหะ


## สารบัญ

1. ภาพรวมระบบ
2. สิ่งที่ต้องเตรียมก่อนใช้งาน
3. การตั้งค่าระบบ
4. ความสามารถของระบบ
5. การติดตามและรายงาน
6. การแก้ไขปัญหาเบื้องต้น


---


## 1. ภาพรวมระบบ

ระบบ POS รับซื้อเศษโลหะ ออกแบบมาสำหรับธุรกิจรับซื้อเศษโลหะโดยเฉพาะ ประกอบด้วย 2 หน้าจอหลัก:

**หน้าจอชั่งเศษ (Scrap Terminal)**
- เลือกประเภทเศษ
- บันทึกน้ำหนัก
- จัดการตะกร้า

**หน้าจอชั่งรถ (Truck Terminal)**
- ค้นหาใบสั่งซื้อ
- บันทึกน้ำหนักรถเข้า
- บันทึกน้ำหนักรถออก
- ตรวจสอบส่วนต่าง


### คุณสมบัติหลัก

**ระบบ Session**
ติดตามการทำงานของพนักงานแต่ละกะ

**ผูกเครื่องชั่ง**
แต่ละ Session ผูกกับเครื่องชั่งเฉพาะ

**ตรวจสอบน้ำหนัก**
เปรียบเทียบน้ำหนักรถกับน้ำหนักเศษ

**รองรับ 2 ภาษา**
ไทย / อังกฤษ

**Responsive**
ใช้งานได้ทั้ง PC, Tablet, มือถือ

**Dark/Light Mode**
เลือกธีมได้ตามต้องการ


---


## 2. สิ่งที่ต้องเตรียมก่อนใช้งาน

### Checklist สำหรับผู้จัดการ

ก่อนเปิดใช้งานระบบ POS ต้องตั้งค่าสิ่งเหล่านี้ให้ครบถ้วน:

1. รายการสินค้า (Item) - สร้างรายการเศษโลหะทุกประเภท
2. รายการราคา (Price List) - กำหนดราคารับซื้อแต่ละรายการ
3. เครื่องชั่ง (Scale) - ลงทะเบียนเครื่องชั่งทุกตัว
4. โปรไฟล์ POS - สร้าง POS Profile Scrap
5. ผู้ใช้งาน (User) - สร้าง User และให้ Role
6. Supplier - สร้างรายชื่อผู้ขาย
7. POS Order - สร้างใบสั่งซื้อสำหรับรถที่เข้ามา


---


## 3. การตั้งค่าระบบ


### ขั้นตอนที่ 1: สร้างรายการสินค้า (Item)

**เส้นทาง:** Stock > Item > New

สร้างรายการสินค้าสำหรับเศษโลหะแต่ละประเภท:

**ตัวอย่างรายการสินค้า:**

ทองแดง
- สายทองแดง (Copper Wire)
- ท่อทองแดง (Copper Pipe)
- ทองแดงผสม (Mixed Copper)

อลูมิเนียม
- อลูมิเนียมเศษ (Aluminum Scrap)
- กระป๋องอลูมิเนียม (Aluminum Cans)
- อลูมิเนียมแผ่น (Aluminum Sheet)

เหล็ก
- เหล็กหนา (Heavy Steel)
- เหล็กบาง (Light Steel)
- เหล็กหล่อ (Cast Iron)

สแตนเลส
- สแตนเลส 304
- สแตนเลส 316


**การตั้งค่า Item:**

Item Code: รหัสสินค้า (ตัวอย่าง: COPPER-WIRE)
Item Name: ชื่อสินค้า (ตัวอย่าง: สายทองแดง)
Item Group: กลุ่มสินค้า (ตัวอย่าง: Scrap Metal)
Default UOM: หน่วยวัด (ตัวอย่าง: Kg)
Is Stock Item: เป็นสต็อก (ติ๊ก Yes)


---


### ขั้นตอนที่ 2: สร้างรายการราคา (Price List)

**เส้นทาง:** Stock > Price List > New


**2.1 สร้าง Price List:**

Price List Name: Standard Buying
Buying: ติ๊ก Yes
Currency: THB


**2.2 กำหนดราคาสินค้า:**

**เส้นทาง:** Stock > Item Price > New

COPPER-WIRE - Standard Buying - 280.00 บาท/Kg
COPPER-PIPE - Standard Buying - 270.00 บาท/Kg
ALUMINUM-SCRAP - Standard Buying - 55.00 บาท/Kg
ALUMINUM-CANS - Standard Buying - 45.00 บาท/Kg
STEEL-HEAVY - Standard Buying - 12.00 บาท/Kg
STAINLESS-304 - Standard Buying - 45.00 บาท/Kg


**หมายเหตุ:** สามารถสร้าง Price List หลายรายการสำหรับลูกค้าแต่ละระดับ เช่น:
- Standard Buying - ราคาปกติ
- VIP Buying - ราคาสำหรับลูกค้าประจำ
- Premium Buying - ราคาสำหรับลูกค้า VIP


---


### ขั้นตอนที่ 3: สร้างเครื่องชั่ง (Scale)

**เส้นทาง:** Scrap Metal Suite > Scale > New


**3.1 เครื่องชั่งสำหรับชั่งเศษ (Scrap Scale)**

Scale Name: SCALE-001
Scale Type: Platform (ตั้งพื้น)
Usage Type: Scrap
Location: โรงเก็บหลัก
Is Active: ติ๊ก Yes
Max Capacity: 500 kg


**3.2 เครื่องชั่งสำหรับชั่งรถ (Truck Scale / Weighbridge)**

Scale Name: WEIGHBRIDGE-001
Scale Type: Weighbridge (สะพานชั่ง)
Usage Type: Truck
Location: ประตูทางเข้า
Is Active: ติ๊ก Yes
Max Capacity: 60000 kg


**ประเภทเครื่องชั่ง (Scale Type):**

Platform - เครื่องชั่งตั้งพื้น - ใช้สำหรับ Scrap
Floor - เครื่องชั่งฝังพื้น - ใช้สำหรับ Scrap
Bench - เครื่องชั่งตั้งโต๊ะ - ใช้สำหรับ Scrap
Hanging - เครื่องชั่งแขวน - ใช้สำหรับ Scrap
Weighbridge - สะพานชั่งรถ - ใช้สำหรับ Truck


**ข้อมูลการสอบเทียบ (Calibration):**

Last Calibration Date: วันที่สอบเทียบล่าสุด
Next Calibration Date: วันที่ต้องสอบเทียบครั้งถัดไป
Calibration Certificate: ไฟล์ใบรับรองการสอบเทียบ


---


### ขั้นตอนที่ 4: สร้างโปรไฟล์ POS

**เส้นทาง:** Scrap Metal Suite > POS Profile Scrap > New

Profile Name: เคาน์เตอร์หลัก
Default Price List: Standard Buying
Warehouse: Stores - YC
Show Price to Operator: ติ๊ก Yes
Is Active: ติ๊ก Yes


**รายการสินค้าที่จะแสดง (Items to Display):**

COPPER-WIRE - Display Order: 1 - Category: ทองแดง
COPPER-PIPE - Display Order: 2 - Category: ทองแดง
ALUMINUM-SCRAP - Display Order: 3 - Category: อลูมิเนียม
ALUMINUM-CANS - Display Order: 4 - Category: อลูมิเนียม
STEEL-HEAVY - Display Order: 5 - Category: เหล็ก
STEEL-LIGHT - Display Order: 6 - Category: เหล็ก
STAINLESS-304 - Display Order: 7 - Category: สแตนเลส


**หมายเหตุเรื่อง Category:**
- ใส่ชื่อหมวดหมู่เหมือนกันสำหรับสินค้าที่ต้องการจัดกลุ่ม
- หน้าจอ POS จะแสดงแท็บตามหมวดหมู่
- ช่วยให้พนักงานค้นหาสินค้าได้เร็วขึ้น


---


### ขั้นตอนที่ 5: สร้างผู้ใช้งานและกำหนดสิทธิ์


**5.1 สร้าง Role "POS Operator"**

เส้นทาง: Setup > Role > New

Role Name: POS Operator
Desk Access: ติ๊ก Yes


**5.2 สร้างผู้ใช้งาน**

เส้นทาง: Setup > User > New

Email: operator1@example.com
First Name: สมชาย
Last Name: ใจดี
Send Welcome Email: ติ๊ก Yes

Roles: ติ๊ก POS Operator


**5.3 สิทธิ์การใช้งาน**

POS Operator: เปิด/ปิด Session, บันทึกน้ำหนัก, ค้นหา Order
System Manager: ทุกอย่าง + ตั้งค่าระบบ


---


## 4. ความสามารถของระบบ


### 4.1 ระบบ Session

ตัวอย่าง POS Session:

Session ID: SES-2025-00001
Operator: สมชาย ใจดี
POS Profile: เคาน์เตอร์หลัก
Scale: SCALE-001 (Platform)
Opening Time: 08:00:00
Status: Open
Total Weights: 15 รายการ
Total Weight: 2,450.5 kg


**กฎของ Session:**
- พนักงาน 1 คน เปิดได้ 1 Session เท่านั้น
- ต้องเลือกเครื่องชั่งเมื่อเข้าหน้าจอ
- เครื่องชั่งที่ถูกเลือกจะถูกล็อคไว้กับ Session นั้น
- เมื่อปิด Session เครื่องชั่งจะถูกปลดล็อค


### 4.2 ระบบตรวจสอบน้ำหนัก (Weight Verification)

ตัวอย่างการตรวจสอบ:

น้ำหนักรถเข้า (Gross): 15,000 kg
น้ำหนักรถออก (Tare): 5,000 kg
น้ำหนักสุทธิจากรถ (Net): 10,000 kg
น้ำหนักเศษรวม: 9,850 kg
ส่วนต่าง (Variance): 150 kg (1.5%)
สถานะ: ผ่าน (ไม่เกิน 2%)


**เกณฑ์ส่วนต่าง:**
- น้อยกว่าหรือเท่ากับ 2% = ผ่าน (สีเขียว)
- มากกว่า 2% = ไม่ผ่าน (สีแดง) - อาจต้องชั่งใหม่

**สาเหตุที่อาจมีส่วนต่าง:**
- ความชื้นในเศษโลหะ
- เศษดินหรือวัสดุอื่นปนมา
- ความคลาดเคลื่อนของเครื่องชั่ง


### 4.3 ระบบชั่งซ้ำ (Re-weigh)

เมื่อส่วนต่างเกินเกณฑ์ ระบบรองรับการชั่งซ้ำ:

- Truck Reweigh: ชั่งรถใหม่อีกครั้ง
- Scrap Reweigh: ชั่งเศษใหม่อีกครั้ง

ระบบจะบันทึกประวัติการชั่งซ้ำไว้ทั้งหมด


### 4.4 การจัดกลุ่มสินค้าตามหมวดหมู่

หน้าจอ POS จะแสดงแท็บหมวดหมู่:
[ทั้งหมด] [ทองแดง] [อลูมิเนียม] [เหล็ก] [สแตนเลส]

เมื่อกดแท็บ จะแสดงเฉพาะสินค้าในหมวดหมู่นั้น


---


## 5. การติดตามและรายงาน


### รายงานที่สามารถดูได้

**POS Session**
เส้นทาง: Scrap Metal Suite > POS Session
ข้อมูล: รายการ Session ทั้งหมด

**POS Order**
เส้นทาง: Scrap Metal Suite > POS Order
ข้อมูล: ใบสั่งซื้อทั้งหมด

**Scrap Weight**
เส้นทาง: Scrap Metal Suite > Scrap Weight
ข้อมูล: รายการชั่งน้ำหนักทั้งหมด

**Scale**
เส้นทาง: Scrap Metal Suite > Scale
ข้อมูล: สถานะเครื่องชั่ง


### ตัวกรองที่มีประโยชน์

**POS Session:**
- Status = Open (ดู Session ที่ยังเปิดอยู่)
- Operator = [ชื่อพนักงาน] (ดูตามพนักงาน)

**POS Order:**
- Status = Pending (ดู Order ที่ยังไม่ได้ชั่ง)
- Order Date = Today (ดูเฉพาะวันนี้)

**Scrap Weight:**
- Is Re-weight = Yes (ดูรายการที่ชั่งซ้ำ)
- Session = [Session ID] (ดูตาม Session)


---


## 6. การแก้ไขปัญหาเบื้องต้น


### ปัญหาที่ 1: พนักงานเปิด Session ไม่ได้

**สาเหตุ:** มี Session เก่าค้างอยู่

**วิธีแก้:**
1. ไปที่ Scrap Metal Suite > POS Session
2. ค้นหา Session ของพนักงานที่ Status = Open
3. เปลี่ยน Status เป็น Closed
4. Save


### ปัญหาที่ 2: เครื่องชั่งแสดงว่า "In Use" แต่ไม่มีใครใช้

**สาเหตุ:** Session ถูกปิดแบบไม่ปกติ

**วิธีแก้:**
1. ไปที่ Scrap Metal Suite > Scale
2. เลือกเครื่องชั่งที่มีปัญหา
3. ยกเลิกเครื่องหมาย "In Use"
4. ลบค่าใน "In Use By Session"
5. Save


### ปัญหาที่ 3: ไม่เห็นสินค้าในหน้าจอ POS

**สาเหตุ:** ไม่ได้เพิ่มสินค้าใน POS Profile

**วิธีแก้:**
1. ไปที่ Scrap Metal Suite > POS Profile Scrap
2. เลือก Profile ที่ใช้งาน
3. เพิ่มสินค้าในตาราง "Items to Display"
4. Save


### ปัญหาที่ 4: ราคาไม่แสดงหรือแสดง 0

**สาเหตุ:** ไม่ได้ตั้งราคาใน Price List

**วิธีแก้:**
1. ไปที่ Stock > Item Price
2. สร้าง Item Price สำหรับสินค้านั้น
3. เลือก Price List ที่ตรงกับ POS Profile
4. ใส่ราคา
5. Save


### ปัญหาที่ 5: พนักงานไม่สามารถเข้าหน้า POS ได้

**สาเหตุ:** ไม่มี Role "POS Operator"

**วิธีแก้:**
1. ไปที่ Setup > User
2. เลือกผู้ใช้งาน
3. เพิ่ม Role "POS Operator"
4. Save


---


## คำสั่ง Bench ที่มีประโยชน์

ล้าง Cache (หลังแก้ไขการตั้งค่า):
bench clear-cache

Build CSS/JS ใหม่:
bench build --app scrap_metal_suite

รัน Migration (หลังอัพเดทระบบ):
bench migrate

Export ข้อมูลตั้งค่า:
bench export-fixtures --app scrap_metal_suite


---


## ติดต่อสอบถาม

หากพบปัญหาที่แก้ไขไม่ได้ กรุณาติดต่อ:
- ทีมพัฒนาระบบ
- แจ้งปัญหาพร้อม Screenshot และขั้นตอนที่ทำ


---

เอกสารนี้ปรับปรุงล่าสุด: ธันวาคม 2568
