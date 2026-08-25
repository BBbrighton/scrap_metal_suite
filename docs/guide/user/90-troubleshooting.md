# Troubleshooting / แก้ปัญหา

> **Status:** Production
> **Who / ใคร:** ทุกคน / everyone
> **Last verified:** 2026-08-25 — ทดสอบทุกข้อกับระบบจริง / every entry re-tested against a live site

หาอาการที่ตรงกับปัญหาของคุณ ถ้าไม่เจอ ดูคู่มือของงานนั้นโดยตรง
Find your symptom below. If it isn't here, check the "What can go wrong" section in your module's guide.

**🐞 = ข้อผิดพลาดที่ทราบแล้ว รอแก้ไข / a known bug awaiting a fix.** ไม่ใช่ความผิดของคุณ — ใช้วิธีแก้ชั่วคราวที่ให้ไว้
Not something you did wrong. Use the workaround given and report it.

---

## 0. ลองสามอย่างนี้ก่อน / Try these three first

ปัญหาส่วนใหญ่จบที่นี่ ลองเรียงจากบนลงล่าง
Most problems end here. Work down the list.

| | ลองอะไร / Try this | แก้อาการอะไรได้ / Fixes |
|---|---|---|
| **1** | กด **Ctrl + Shift + R** | หน้าจอไม่อัปเดต · ปุ่มใหม่ไม่ขึ้น · หน้าตาเพี้ยน |
| **2** | **ปิดกะแล้วเปิดใหม่** จากหน้า `/pos` | ต่อตาชั่งไม่ติด · ไปหน้าจอผิด · ตาชั่งถูกจองค้าง |
| **3** | **พิมพ์น้ำหนักเองแทน** ไม่ต้องรอตาชั่ง | ตาชั่งเสีย สายหลุด เบราว์เซอร์ไม่รองรับ |

**ยังไม่หาย?** หาอาการของคุณในตารางข้างล่าง แล้วแจ้งหัวหน้าพร้อม **เลขเอกสาร** — ดู [ข้อ 6](#6-เมื่อไหร่ควรแจ้งต่อ--when-to-escalate)

---

## 1. การชั่งและบันทึก / Weighing and saving

| อาการ / Symptom | สาเหตุ / Cause | แก้ยังไง / Fix |
|---|---|---|
| น้ำหนักบนหน้าจอไม่ขยับ / The weight on screen doesn't move | ตาชั่งยังไม่เชื่อมต่อ (จุดสีแดง) / scale not connected — red dot | กดที่ชื่อตาชั่งบนแถบด้านบน แล้วอนุญาตในเบราว์เซอร์ / click the scale name in the header and grant the browser permission |
| ต่อตาชั่งไม่ได้เลย / Cannot connect the scale at all | สายหลุด, พอร์ตถูกใช้โดยกะอื่น, หรือเบราว์เซอร์ไม่รองรับ / cable, port held by another session, or unsupported browser | ตรวจสาย → ปิดกะที่ค้างอยู่ → ใช้ Chrome หรือ Edge / check the cable, close any stale session holding that scale, use Chrome or Edge |
| น้ำหนักเพี้ยนไป 10 เท่า หรือ 1000 เท่า / Weight is out by a factor of 10 or 1000 | ค่าแปลงหน่วยของตาชั่งตั้งผิด / the scale's unit conversion factor is wrong | หยุดใช้ตาชั่งตัวนั้น แจ้งผู้ดูแลระบบทันที / stop using that scale and tell an admin immediately — do not "correct" it by typing a different number |
| กดบันทึกแล้วขึ้นว่า **น้ำหนักเกินพิกัดตาชั่ง** / *"exceeds scale capacity"* | น้ำหนักเกินพิกัดที่ตั้งไว้กับตาชั่งตัวนั้น — **ระบบกันไว้ถูกแล้ว** / the weight is over that scale's rated limit; the block is correct | ชั่งใหม่ให้ถูก ถ้าน้ำหนักถูกต้องจริงแปลว่าพิกัดตาชั่งตั้งไว้ผิด — แจ้งผู้ดูแล / reweigh. If the number really is right, the scale's rated capacity is set wrong — tell an admin |

---

## 2. กะและหน้าจอ / Sessions and screens

| อาการ / Symptom | สาเหตุ / Cause | แก้ยังไง / Fix |
|---|---|---|
| เปิดกะแล้วไปหน้าจอผิด / Opened a session and landed on the wrong terminal | เลือกตาชั่งผิดประเภท — Scrap ไป `/pos/terminal`, Truck ไป `/pos/truck` / wrong scale type | ปิดกะ แล้วเปิดใหม่โดยเลือกตาชั่งให้ถูกประเภท / close the session and reopen with the right scale |
| 🐞 **กะปิดเองระหว่างชั่งเข้ากับชั่งออก** / The session closed itself between weigh-in and weigh-out | ระบบปิดกะที่ไม่มีการ *บันทึก* เกิน 90 นาที — การเปิดหน้าจอค้างไว้ไม่นับ / the idle sweep measures time since the last **save**, not since you last touched the screen | เปิดกะใหม่แล้วทำต่อ งานที่บันทึกไว้แล้วไม่หาย / open a new session and continue — saved work is safe. On long jobs, save something periodically. |
| "This session belongs to another operator" | กะนั้นเป็นของคนอื่น / it is someone else's session | เปิดกะของตัวเอง — อย่าใช้กะคนอื่น เพราะชื่อผู้ชั่งจะผิด / open your own; using someone else's misattributes every weight |
| หน้าจอขึ้น "Session not found" | เลขกะผิด หรือกะถูกปิดไปแล้ว / bad or closed session id | กลับไปที่ `/pos` แล้วเปิดกะใหม่ / go back to `/pos` and open a new session |
| **มีกะค้างอยู่ เปิดกะใหม่ไม่ได้** / You already have an open session and cannot start another | 1 คนเปิดได้ 1 กะ / one session per person | กลับไป `/pos` — หน้านั้นจะบอกว่ามีกะค้างอยู่ และมีปุ่ม **ปิดกะ / Close Session** ให้กดได้เลย ไม่ต้องเรียกผู้ดูแล / `/pos` now detects it and offers a **Close Session** button. You can clear it yourself |
| กดปุ่มย้อนกลับของเบราว์เซอร์แล้วหน้าจอค้าง กดอะไรไม่ได้ / The screen freezes after pressing the browser Back button | เคยเป็นปัญหา — **แก้แล้ว** / this was a real bug, now **fixed** | ถ้ายังเจออยู่ กด **Ctrl + Shift + R** หนึ่งครั้ง เบราว์เซอร์ยังใช้ไฟล์เก่าอยู่ / press Ctrl+Shift+R once — your browser is still on the old files |
| แก้ CSS/หน้าจอแล้วไม่เปลี่ยน / A visual change doesn't appear | เบราว์เซอร์เก็บไฟล์เก่าไว้ได้ถึง 12 ชั่วโมง / the browser caches assets for up to 12 hours | กด **Ctrl + Shift + R** / hard-refresh. `/pos/terminal` แก้แล้ว แต่หน้าอื่นยังต้องกดเอง / `/pos/terminal` is fixed; other pages still need this |

---

## 3. งานรับของ / Drop-offs

| อาการ / Symptom | สาเหตุ / Cause | แก้ยังไง / Fix |
|---|---|---|
| เพิ่มถุงไม่ได้ เพราะงานปิดแล้ว / Cannot add a bag — the drop-off is Completed | งานถูกปิดไปแล้ว / it was completed | กด **เปิดงานใหม่ / Reopen**, เพิ่มถุง, แล้วกดปิดงานอีกครั้ง — ระบบจะออกใบชั่งฉบับแก้ไขให้ / Reopen, add, finish again. A fresh amended receipt is issued. |
| 🐞 **งานพักอยู่ แต่ยังเพิ่มถุงได้** / A Paused drop-off still accepts bags | ระบบไม่ได้กันไว้ / the pause is not enforced on add | กด **กลับมาทำต่อ / Resume** ก่อนชั่ง เพื่อให้สถานะตรงกับความจริง / press Resume before weighing so the status matches reality |
| ชั่งผิด อยากแก้น้ำหนักถุง / Wrong weight on a bag | — | ใช้ **ชั่งซ้ำ / Reweigh** — ห้ามลบ ระบบจะเก็บใบเดิมไว้เป็นประวัติและออกใบใหม่ / use Reweigh. Never delete. The old bag is retired and a new one replaces it, keeping the audit trail. |
| สแกน QR ถุงแล้วเปิดงานอื่น / Scanning a bag QR opens a different drop-off | ถูกต้องแล้ว — ถุงนั้นอยู่ในงานนั้น / this is correct behaviour | ระบบเปิดงานที่ถุงนั้นสังกัด และไฮไลต์แถวให้ / it loads the bag's own drop-off and highlights the row |

---

## 4. การพิมพ์ / Printing

| อาการ / Symptom | สาเหตุ / Cause | แก้ยังไง / Fix |
|---|---|---|
| พิมพ์ออกมาจาง อ่านภาษาไทยไม่ออก / Printing is faint, Thai unreadable | เคยเป็นปัญหาของแบบฟอร์ม แก้แล้ว / was a template problem, now fixed | กด Ctrl+Shift+R ก่อน ถ้ายังจาง = ตั้งค่าความเข้มเครื่องพิมพ์ หรือกระดาษเสื่อม / hard-refresh first. Still faint means printer darkness or old paper, not the template. Report with a photo. |
| 🐞 **สั่งพิมพ์แล้วไม่มีอะไรเกิดขึ้น** / Printing does nothing at all | งานรับของที่ผูกกับใบนั้นถูกลบไปแล้ว → QR สร้างไม่ได้ → พิมพ์ล้มทั้งใบ / the linked drop-off was deleted, so the QR cannot be built and the whole print aborts | แจ้งผู้ดูแลระบบพร้อมเลขเอกสาร / report with the document number |
| 🐞 **ใบคิวขึ้นเวลาเป็น `-`** / The queue slip shows `-` instead of a time | ระบบดึงข้อมูลเวลาไม่ครบ / the timestamp field isn't fetched by the query | ใช้เวลาจากใบชั่งแทน / read the time off the weight receipt instead |
| 🐞 **ใบคิวขึ้นค่าความต่างเป็น 10200%** / Variance prints as 10200% | คูณเกินไป 100 เท่า / the value is multiplied by 100 twice | หารด้วย 100 เพื่ออ่านค่าจริง (10200% = 102%) / divide by 100 to read the real figure |
| สติ๊กเกอร์ไม่ออก / No sticker prints | เครื่องพิมพ์สติ๊กเกอร์ยังไม่ตั้งค่า หรือเลือกเครื่องผิดตอนสั่งพิมพ์ / label printer not set up, or the wrong printer chosen in the dialog | ตรวจว่าเลือกเครื่องพิมพ์สติ๊กเกอร์ (50×80mm) ไม่ใช่เครื่องพิมพ์ใบเสร็จ (80mm) / make sure the 50×80mm label printer is selected, not the 80mm receipt printer |

---

## 5. ราคาและการจ่ายเงิน / Pricing and settlement

> ⚠️ ส่วนนี้มีข้อผิดพลาดที่ทราบแล้วหลายจุด **อย่าใช้ตัวเลขจากระบบจ่ายเงินจริงโดยไม่ตรวจสอบ**
> ⚠️ This area has several confirmed defects. **Do not pay against these figures without checking them by hand.**

| อาการ / Symptom | สาเหตุ / Cause | แก้ยังไง / Fix |
|---|---|---|
| 🐞 **ใบยืนยันราคาแสดงยอดที่ชำระแล้ว = 0.00 ทั้งที่ปิดยอดแล้ว** / The price confirmation prints a settled value of 0.00 even when fully settled | ค่านี้ไม่เคยถูกคำนวณจริง / the field is never recomputed | คำนวณยอดเองจากใบชั่งจริง อย่าใช้ตัวเลขบนใบนี้ / compute from the actual weight receipts. Do not rely on this number. |
| ใบสั่งซื้อยังขึ้น "Pending" ทั้งที่ส่งของครบแล้ว / An order still says Pending at 100% fulfilled | เคยเป็นปัญหา — **แก้แล้ว** ตรวจกับข้อมูลจริง 127 ใบ ตรงกันทุกใบ / was a real bug, now **fixed** — checked against all 127 live orders, all agree | ถ้ายังเจอ ให้เปิดใบนั้นแล้วกด Save หนึ่งครั้ง / if you still see it, open the order and press Save once |
| 🐞 **งานค้างที่ "In Progress" ปิดไม่ได้** / A final settlement is stuck at In Progress with no way to close it | ไม่มีปุ่มหรือคำสั่งให้ปิด / no exit path exists in the code | แจ้งผู้ดูแลระบบ — ต้องแก้ที่ระบบ / needs an admin and a code fix |
| ราคาบนหน้าจอผู้จัดการดูไม่ถูก / Prices on the manager screen look wrong | 🐞 หน้าจอนั้นยังไม่เสร็จ บางค่าเป็นตัวอย่างที่ใส่ไว้ / that screen is unfinished and some values are hardcoded samples | **อย่าใช้ตัวเลขจากหน้าจอนั้น** / do not use figures from that screen — see [80 — Portals (Preview)](80-portals-preview.md) |

---

## 6. เมื่อไหร่ควรแจ้งต่อ / When to escalate

แจ้งทันที ถ้า / Escalate immediately if:

- ตัวเลขน้ำหนักดูผิดปกติอย่างชัดเจน / a weight is obviously wrong — a wrong weight paid out is not recoverable
- ระบบยอมให้บันทึกสิ่งที่ไม่ควรยอม / the system accepts something it clearly should have rejected
- ตัวเลขบนเอกสารที่ให้ผู้ขาย ไม่ตรงกับในระบบ / a number on a document given to a supplier disagrees with the system

**แจ้งอะไรบ้าง / Include when you report:**

1. **เลขเอกสาร / The document number** — `DO-…`, `CTN-…`, `SW-…`, `PLO-…` (สำคัญที่สุด / this matters most)
2. รูปหน้าจอ / a screenshot
3. สิ่งที่กดก่อนเกิดปัญหา / what you clicked just before it happened
4. เวลาโดยประมาณ / roughly when

เลขเอกสารทำให้ตามเรื่องได้ในไม่กี่วินาที คำอธิบายอย่างเดียวใช้เวลาเป็นชั่วโมง
A document number finds the record in seconds. A description alone can take an hour.

## 5b. การคัดแยก / Production Sorting

| อาการ / Symptom | สาเหตุ / Cause | วิธีแก้ / Fix |
|---|---|---|
| 🐞 **เปิดหน้าคัดแยกแล้วกดบันทึกไม่ได้เลย** / The sorting screen cannot save anything | คุณอยู่ผิดหน้า — `/production/terminal` เป็นหน้าเก่าที่ใช้ไม่ได้แล้ว / you are on `/production/terminal`, the old screen, which no longer works | ไปที่ **`/pos/production`** แทน (เข้าจาก `/pos` แล้วกดการ์ด **Production Sorting**) / use **`/pos/production`** — enter from `/pos` and click the **Production Sorting** card |
| กด **✚ Add Item** แล้วขึ้น *"Select a container first"* | การคัดแยกทำทีละถุง / sorting is per bag | กด CTN ในรายการถุงทางซ้ายก่อน / click a CTN in the worklist first |
| สแกน CTN แล้วขึ้นสีจาง กดไม่ได้ | ถุงถูกยกเลิกตอนรับเข้า / the bag was voided at receiving | ถุงนั้นถูกตัดออกแล้ว ไม่ต้องคัดแยก / it was written off; it is not sorted |
| สแกน CTN แล้วไม่เจอ | ใบส่งของยังไม่ *Completed* | คัดแยกได้เฉพาะใบที่ปิดงานแล้ว / only Completed drop-offs can be sorted |
| ถุงขึ้นเขียว + *"sorted earlier"* | คัดแยกครบไปแล้ว / already fully sorted | ปกติ — ทำซ้ำจะบวกน้ำหนักเพิ่ม / normal; redoing adds the weight again |
| Submit แล้วขึ้น *"has already been sorted"* | ใบนี้ Submit ไปแล้ว / already submitted | กด **↺ Reopen** ใส่เหตุผล — ใบเดิมจะถูกยกเลิก / **↺ Reopen** with a reason; the old sorting is cancelled |
| ใบคัดแยกไม่พิมพ์ออก | กล่องพิมพ์ถูกปิด หรือกระดาษหมด | กด **🖶 Print** บนแถบบนเพื่อพิมพ์ซ้ำ / **🖶 Print** in the header reprints the last slip |
| ยอด **รับเข้า** ในใบคัดแยกดูสูงผิดปกติ | ใบสรุปที่สร้างก่อน 2026-08-25 / a Dropoff Final built before 2026-08-25 | เปิดใบสรุปแล้วกด Save เพื่อสร้างใหม่ / open the Dropoff Final and save it to rebuild |
