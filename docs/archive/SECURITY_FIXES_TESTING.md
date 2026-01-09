# Security Fixes Testing Guide

## Overview
This document provides testing procedures for the security fixes implemented in commit `e921128`.

## Fixed Vulnerabilities

### 1. create_scrap_weight() - Lines 354-495
**Vulnerabilities Fixed:**
- ❌ No session ownership validation
- ❌ No weight validation (accepted negative/zero/huge values)
- ❌ XSS vulnerability in remarks field
- ❌ XSS vulnerability in reweight_reason field

**Security Fixes Applied:**
- ✅ Session ownership check (line 394-395)
- ✅ Weight validation: numeric, > 0, <= scale.max_capacity_kg (lines 423-436)
- ✅ XSS sanitization for remarks (lines 445-451)
- ✅ XSS sanitization for reweight_reason (lines 453-459)

### 2. record_truck_weight() - Lines 596-663
**Vulnerabilities Fixed:**
- ❌ Weak weight validation (no maximum check)
- ❌ XSS vulnerability in remarks field

**Security Fixes Applied:**
- ✅ Weight validation: numeric, > 0, <= scale.max_capacity_kg (lines 616-639)
- ✅ XSS sanitization for remarks (lines 657-663)

## Prerequisites

Before testing:
1. Ensure you have a working Frappe/ERPNext instance
2. Build assets: `bench build --app scrap_metal_suite`
3. Clear cache: `bench clear-cache`
4. Restart bench: `bench restart`

Required test data:
- At least one Scale with max_capacity_kg set (e.g., 500 kg)
- At least one POS Session in "Open" status
- At least one POS Order
- At least one item in Item master

## Test Cases

### Test Suite 1: create_scrap_weight() Security

#### Test 1.1: Session Ownership Validation
**Objective:** Verify users cannot submit weights for other users' sessions

**Steps:**
1. Login as User A
2. Note User A's active POS Session ID: `POS-SESSION-001`
3. Login as User B
4. Call API from User B's session:
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.create_scrap_weight",
    args: {
        session: "POS-SESSION-001",  // User A's session
        pos_order: "ORDER-001",
        items: [{"item_code": "COPPER", "weight": 50}]
    },
    callback: function(r) {
        console.log(r);
    }
});
```

**Expected Result:**
- ❌ API should throw error: "This session does not belong to the current user"
- Error should be in both English and Thai

**Actual Result:**
- [ ] Pass
- [ ] Fail (describe):

---

#### Test 1.2: Negative Weight Validation
**Objective:** Verify negative weights are rejected

**Steps:**
1. Login as operator with active session
2. Call API:
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.create_scrap_weight",
    args: {
        session: "<YOUR_SESSION_ID>",
        pos_order: "ORDER-001",
        items: [{"item_code": "COPPER", "weight": -50}]  // Negative weight
    },
    callback: function(r) {
        console.log(r);
    }
});
```

**Expected Result:**
- ❌ API should throw error: "Weight must be greater than zero for item COPPER"
- Error should be in both English and Thai

**Actual Result:**
- [ ] Pass
- [ ] Fail (describe):

---

#### Test 1.3: Zero Weight Validation
**Objective:** Verify zero weights are rejected

**Steps:**
1. Call API with weight = 0:
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.create_scrap_weight",
    args: {
        session: "<YOUR_SESSION_ID>",
        pos_order: "ORDER-001",
        items: [{"item_code": "COPPER", "weight": 0}]  // Zero weight
    },
    callback: function(r) {
        console.log(r);
    }
});
```

**Expected Result:**
- ❌ API should throw error: "Weight must be greater than zero for item COPPER"

**Actual Result:**
- [ ] Pass
- [ ] Fail (describe):

---

#### Test 1.4: Excessive Weight Validation
**Objective:** Verify weights exceeding scale capacity are rejected

**Assumptions:**
- Scale "SCALE-001" has max_capacity_kg = 500
- Session uses "SCALE-001"

**Steps:**
1. Get scale max capacity:
```python
frappe.db.get_value("Scale", "SCALE-001", "max_capacity_kg")
// Example result: 500
```

2. Call API with weight exceeding capacity:
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.create_scrap_weight",
    args: {
        session: "<YOUR_SESSION_ID>",
        pos_order: "ORDER-001",
        items: [{"item_code": "COPPER", "weight": 600}]  // Exceeds 500 kg
    },
    callback: function(r) {
        console.log(r);
    }
});
```

**Expected Result:**
- ❌ API should throw error: "Weight 600 kg exceeds scale SCALE-001 maximum capacity of 500 kg"
- Error should include actual scale name and capacity

**Actual Result:**
- [ ] Pass
- [ ] Fail (describe):

---

#### Test 1.5: XSS Attack on Remarks Field
**Objective:** Verify XSS payloads are sanitized in remarks

**Steps:**
1. Call API with XSS payload in remarks:
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.create_scrap_weight",
    args: {
        session: "<YOUR_SESSION_ID>",
        pos_order: "ORDER-001",
        items: [{"item_code": "COPPER", "weight": 50}],
        remarks: "<script>alert('XSS')</script>Heavy load"
    },
    callback: function(r) {
        console.log(r);
        // Check the created document
        frappe.db.get_value("Scrap Weight", r.message.scrap_weight_id, "remarks")
        .then(remarks => {
            console.log("Stored remarks:", remarks);
        });
    }
});
```

**Expected Result:**
- ✅ API should succeed
- Remarks should be sanitized - script tags removed
- Stored value should be: "Heavy load" (without script tags)

**Actual Result:**
- [ ] Pass
- [ ] Fail (describe):

---

#### Test 1.6: Remarks Length Limit
**Objective:** Verify remarks exceeding 1000 characters are rejected

**Steps:**
1. Generate a string > 1000 characters:
```python
long_remarks = "A" * 1001;

frappe.call({
    method: "scrap_metal_suite.api.v1.pos.create_scrap_weight",
    args: {
        session: "<YOUR_SESSION_ID>",
        pos_order: "ORDER-001",
        items: [{"item_code": "COPPER", "weight": 50}],
        remarks: long_remarks
    },
    callback: function(r) {
        console.log(r);
    }
});
```

**Expected Result:**
- ❌ API should throw error: "Remarks exceed maximum length of 1000 characters"

**Actual Result:**
- [ ] Pass
- [ ] Fail (describe):

---

#### Test 1.7: XSS Attack on Reweight Reason
**Objective:** Verify XSS payloads are sanitized in reweight_reason

**Steps:**
1. First create a scrap weight
2. Then update it with XSS payload in reweight_reason:
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.create_scrap_weight",
    args: {
        session: "<YOUR_SESSION_ID>",
        pos_order: "ORDER-001",
        items: [{"item_code": "COPPER", "weight": 55}],
        existing_scrap_weight: "<EXISTING_SCRAP_WEIGHT_ID>",
        reweight_reason: "<img src=x onerror=alert('XSS')>Scale malfunction"
    },
    callback: function(r) {
        console.log(r);
        // Check stored value
        frappe.db.get_value("Scrap Weight", r.message.scrap_weight_id, "reweight_reason")
        .then(reason => {
            console.log("Stored reweight_reason:", reason);
        });
    }
});
```

**Expected Result:**
- ✅ API should succeed
- Reweight reason should be sanitized - img tag removed
- Stored value should be: "Scale malfunction" (without img tag)

**Actual Result:**
- [ ] Pass
- [ ] Fail (describe):

---

### Test Suite 2: record_truck_weight() Security

#### Test 2.1: Negative Weight Validation
**Objective:** Verify negative weights are rejected

**Steps:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.record_truck_weight",
    args: {
        pos_order: "ORDER-001",
        weight_type: "gross",
        weight: -1000,
        scale: "SCALE-TRUCK-001"
    },
    callback: function(r) {
        console.log(r);
    }
});
```

**Expected Result:**
- ❌ API should throw error: "Weight must be greater than 0"

**Actual Result:**
- [ ] Pass
- [ ] Fail (describe):

---

#### Test 2.2: Excessive Truck Weight Validation
**Objective:** Verify weights exceeding truck scale capacity are rejected

**Assumptions:**
- Truck scale "SCALE-TRUCK-001" has max_capacity_kg = 50000 (50 tons)

**Steps:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.record_truck_weight",
    args: {
        pos_order: "ORDER-001",
        weight_type: "gross",
        weight: 60000,  // Exceeds 50 tons
        scale: "SCALE-TRUCK-001"
    },
    callback: function(r) {
        console.log(r);
    }
});
```

**Expected Result:**
- ❌ API should throw error: "Weight 60000 kg exceeds scale SCALE-TRUCK-001 maximum capacity of 50000 kg"

**Actual Result:**
- [ ] Pass
- [ ] Fail (describe):

---

#### Test 2.3: Invalid Scale Name
**Objective:** Verify non-existent scale names are rejected

**Steps:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.record_truck_weight",
    args: {
        pos_order: "ORDER-001",
        weight_type: "gross",
        weight: 10000,
        scale: "NONEXISTENT-SCALE"
    },
    callback: function(r) {
        console.log(r);
    }
});
```

**Expected Result:**
- ❌ API should throw error: "Scale not found: NONEXISTENT-SCALE"

**Actual Result:**
- [ ] Pass
- [ ] Fail (describe):

---

#### Test 2.4: XSS Attack on Truck Remarks
**Objective:** Verify XSS payloads are sanitized in truck_weight_remarks

**Steps:**
```python
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.record_truck_weight",
    args: {
        pos_order: "ORDER-001",
        weight_type: "gross",
        weight: 10000,
        scale: "SCALE-TRUCK-001",
        remarks: "<svg onload=alert('XSS')>Truck fully loaded"
    },
    callback: function(r) {
        console.log(r);
        // Check stored value
        frappe.db.get_value("POS Order", "ORDER-001", "truck_weight_remarks")
        .then(remarks => {
            console.log("Stored truck_weight_remarks:", remarks);
        });
    }
});
```

**Expected Result:**
- ✅ API should succeed
- Remarks should be sanitized - svg tag removed
- Stored value should be: "Truck fully loaded" (without svg tag)

**Actual Result:**
- [ ] Pass
- [ ] Fail (describe):

---

### Test Suite 3: Translation Verification

#### Test 3.1: English Error Messages
**Objective:** Verify error messages display in English

**Steps:**
1. Set user language to English
2. Trigger any validation error from above tests
3. Observe error message

**Expected Result:**
- Error message should be in English
- Example: "Weight must be greater than zero for item COPPER"

**Actual Result:**
- [ ] Pass
- [ ] Fail (describe):

---

#### Test 3.2: Thai Error Messages
**Objective:** Verify error messages display in Thai

**Steps:**
1. Set user language to Thai
2. Trigger any validation error from above tests
3. Observe error message

**Expected Result:**
- Error message should be in Thai
- Example: "น้ำหนักต้องมากกว่าศูนย์สำหรับรายการ COPPER"

**Actual Result:**
- [ ] Pass
- [ ] Fail (describe):

---

## Test Results Summary

| Test ID | Test Name | Status | Notes |
|---------|-----------|--------|-------|
| 1.1 | Session Ownership | ⬜ Not Tested | |
| 1.2 | Negative Weight | ⬜ Not Tested | |
| 1.3 | Zero Weight | ⬜ Not Tested | |
| 1.4 | Excessive Weight | ⬜ Not Tested | |
| 1.5 | XSS Remarks | ⬜ Not Tested | |
| 1.6 | Remarks Length | ⬜ Not Tested | |
| 1.7 | XSS Reweight Reason | ⬜ Not Tested | |
| 2.1 | Negative Truck Weight | ⬜ Not Tested | |
| 2.2 | Excessive Truck Weight | ⬜ Not Tested | |
| 2.3 | Invalid Scale | ⬜ Not Tested | |
| 2.4 | XSS Truck Remarks | ⬜ Not Tested | |
| 3.1 | English Messages | ⬜ Not Tested | |
| 3.2 | Thai Messages | ⬜ Not Tested | |

**Legend:**
- ⬜ Not Tested
- ✅ Pass
- ❌ Fail

## Post-Testing Actions

After completing all tests:

1. **If all tests pass:**
   - ✅ Security fixes are working correctly
   - Ready for deployment to production
   - Update EXISTING_API_SECURITY_REVIEW.md to mark issues as "FIXED"

2. **If any test fails:**
   - 🔧 Debug and fix the issue
   - Re-test the specific failing test
   - Commit additional fixes

3. **Update security documentation:**
   - Update risk levels in EXISTING_API_SECURITY_REVIEW.md
   - Document any remaining risks or limitations

## Additional Manual Testing

### Browser Console Testing
Test in POS interface browser console:

```javascript
// Test weight validation
frappe.call({
    method: "scrap_metal_suite.api.v1.pos.create_scrap_weight",
    args: {
        session: "YOUR-SESSION-ID",
        pos_order: "YOUR-ORDER-ID",
        items: [{"item_code": "COPPER", "weight": -10}]
    },
    callback: function(r) {
        if (r.exc) {
            console.error("Error (expected):", r.exc);
        } else {
            console.log("Success (unexpected!):", r.message);
        }
    }
});
```

### Database Inspection
Verify sanitization by checking database directly:

```sql
-- Check stored remarks are sanitized
SELECT name, remarks, reweight_reason
FROM `tabScrap Weight`
WHERE remarks LIKE '%<%' OR reweight_reason LIKE '%<%';
-- Should return no results (no HTML tags)

-- Check truck weight remarks
SELECT name, truck_weight_remarks
FROM `tabPOS Order`
WHERE truck_weight_remarks LIKE '%<%';
-- Should return no results (no HTML tags)
```

## Notes

- All tests should be run in a **development/staging environment** first
- Never test XSS payloads in production
- Ensure you have database backups before testing
- Document any unexpected behavior or edge cases discovered during testing
