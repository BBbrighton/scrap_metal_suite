<!--
COPY ME to user/NN-<module>.md when adding a module.

Rules for this tier:
  - Bilingual. Thai first in every heading and every step, English after.
  - Task-shaped, not feature-shaped. Sections are things an operator DOES.
  - Every walkthrough: numbered steps, REAL values, and what appears on screen.
  - Never translate item names. They are canonical Thai (ทองแดงปอก) and are
    the identifier, not a label.
  - If you did not verify it, mark it: ⚠️ UNVERIFIED — reason
  - Delete these comments and every "<...>" placeholder before committing.
-->

# <Module Name> — Operator Guide / คู่มือผู้ใช้งาน

> **Status:** Production
> **Who / ใคร:** <roles, e.g. POS Operator, Production Manager>
> **Where / ที่ไหน:** <url or desk path>
> **Last verified:** <YYYY-MM-DD> against <branch or tag>

---

## 1. What this is for / งานนี้คืออะไร

<Two or three sentences, Thai then English. What job does this screen do, and
where does it sit in the yard's day? Name the physical thing it corresponds to
— a truck on the weighbridge, a bag on the scale.>

**เมื่อไหร่ที่ใช้ / When you use it:** <the trigger>
**ผลลัพธ์ / What you end up with:** <the document or state produced>

---

## 2. Before you start / เตรียมก่อนเริ่ม

| ต้องมี / You need | หมายเหตุ / Notes |
|---|---|
| <prerequisite> | <why, and what happens without it> |

---

## 3. The screen / หน้าจอ

<ASCII or mermaid sketch of the real layout — derive it from the actual HTML
and CSS, not from imagination.>

```
┌──────────────┬───────────────────┬──────────────┐
│ <pane>       │ <pane>            │ <pane>       │
└──────────────┴───────────────────┴──────────────┘
```

| ส่วน / Area | ทำอะไร / What it does |
|---|---|
| <element> | <plain-language purpose> |

---

## 4. Walkthrough: <the main happy path> / <ชื่อขั้นตอนภาษาไทย>

**สถานการณ์ / Scenario:** <a concrete situation with real numbers>

1. **<Action>** — <what to click or type, with a real value>
   → <what appears on screen>
2. …

**เสร็จแล้วได้อะไร / Result:** <the end state, and how to confirm it>

---

## 5. Walkthrough: <variant or edge case> / <ชื่อภาษาไทย>

<One section per real case an operator hits. Same numbered shape as above.
Do not merge cases to save space — a case the operator cannot find is a case
they will get wrong.>

---

## 6. What can go wrong / ปัญหาที่พบบ่อย

| อาการ / Symptom | สาเหตุ / Cause | แก้ยังไง / Fix |
|---|---|---|
| <what the operator sees, in their words> | <the real cause> | <the action that resolves it> |

---

## 7. Quick reference / สรุป

**ปุ่ม / Buttons**

| ปุ่ม / Button | ทำอะไร / Does |
|---|---|
| <label> | <action> |

**สถานะ / Statuses**

| สถานะ / Status | หมายความว่า / Means | ทำอะไรต่อได้ / What you can do next |
|---|---|---|
| <status> | <meaning> | <allowed actions> |
