# Production Sorting Module - Test Case

**Module:** Production Sorting (QA/QC)
**Date:** 2026-03-08
**Version:** Phase 1-5 Complete
**Test Environment:** http://smt.local:8000

---

## Prerequisites

### 1. Required Roles
User must have one of these roles:
- **Production Worker** (for operators)
- **Production Manager** (for supervisors)
- **System Manager** (for admins)

**Setup:**
1. Go to User List (http://smt.local:8000/app/user)
2. Edit your test user
3. Add role: "Production Worker" or "Production Manager"
4. Save

### 2. Required Data

#### A. Create a Supplier (if not exists)
1. Go to Supplier List (http://smt.local:8000/app/supplier)
2. Create new Supplier:
   - Supplier Name: "Test Supplier ABC"
   - Supplier Group: "All Supplier Groups"
   - Save

#### B. Create Items (Scrap Materials)
1. Go to Item List (http://smt.local:8000/app/item)
2. Create items:
   - **Item 1:**
     - Item Code: SCRAP-COPPER-01
     - Item Name: Copper Wire Scrap
     - Item Group: Raw Material
     - Stock UOM: Kg
   - **Item 2:**
     - Item Code: SCRAP-ALUMINUM-01
     - Item Name: Aluminum Scrap
     - Item Group: Raw Material
     - Stock UOM: Kg
   - **Item 3:**
     - Item Code: SCRAP-PLASTIC-01
     - Item Name: Plastic Contamination (Unwanted)
     - Item Group: Raw Material
     - Stock UOM: Kg

#### C. Create a Scale
1. Go to Scale List (http://smt.local:8000/app/scale)
2. Create new Scale:
   - Scale Name: Production Scale 01
   - Usage Type: **Scrap** (important!)
   - Location: Production Floor A
   - Save

#### D. Create a Dropoff (Received Material)
1. Go to Dropoff List (http://smt.local:8000/app/dropoff)
2. Create new Dropoff:
   - Supplier: Test Supplier ABC
   - Dropoff Date: Today
   - License Plate: ABC-1234
   - **Item Summary (what was received):**
     - Row 1: SCRAP-COPPER-01, Indicated Weight: 100 kg
     - Row 2: SCRAP-ALUMINUM-01, Indicated Weight: 50 kg
   - **Total Actual Weight:** 150 kg (from truck weighing)
   - Status: Received
   - **Submit the Dropoff** (important - must be submitted)

---

## Test Case 1: Access Production Terminal

### Steps:
1. Navigate to http://smt.local:8000/pos
2. Verify you see **3 terminal cards:**
   - Scrap Weighing (blue)
   - Truck Scale (purple/gray)
   - **Production Sorting (orange)** ← NEW
3. Click on "Production Sorting" card

### Expected Result:
- Page loads: http://smt.local:8000/pos/production
- Header shows: "🔧 Production Sorting"
- Orange color scheme throughout
- "No Session" badge visible
- "Start Session" section displayed with scale list

### Pass/Fail: ___

---

## Test Case 2: Start Production Session

### Steps:
1. On Production Terminal page
2. Verify scale list shows "Production Scale 01"
3. Click "Production Scale 01" button

### Expected Result:
- API call: `scrap_metal_suite.api.v1.production.open_session`
- Success message: "Session started with Production Scale 01"
- Page reloads automatically
- Session badge shows session ID (e.g., "PROD-SESS-2026-00001")
- "Close Session" button visible
- **Session setup disappears, Sorting Interface appears**
- 3 panels visible: Dropoff Selection | Item Weighing | Current Sorting

### Pass/Fail: ___

---

## Test Case 3: Select Dropoff for Sorting

### Steps:
1. In left panel "Select Dropoff"
2. Type the Dropoff ID (e.g., "DROPOFF-2026-00001") in search box
3. Wait for autocomplete results
4. Click on the dropoff from results

### Expected Result:
- Dropoff details card appears showing:
  - Dropoff ID: DROPOFF-2026-00001
  - Supplier: Test Supplier ABC
  - Total Weight: 150.000 kg
- Search box clears
- "Clear" button visible
- Middle panel (Item Weighing) becomes active

### Pass/Fail: ___

---

## Test Case 4: Add Good Items (Keep & Pay)

### Scenario: Worker sorts and finds 95kg of copper and 48kg of aluminum (good quality)

### Steps:

#### 4A. First Good Item - Copper
1. Verify "Good Items (Keep & Pay)" tab is active (green)
2. Click "Capture Weight" button
3. Enter weight: **95** (in prompt dialog - manual entry for testing)
4. Verify weight display shows: **95.000 kg**
5. Select Item: **SCRAP-COPPER-01 (Copper Wire Scrap)**
6. Enter Remarks (optional): "Good quality copper"
7. Click "Add Item" button

**Expected:**
- Item appears in right panel "Current Sorting" under "Good Items"
- Shows: "Copper Wire Scrap - 95.000 Kg"
- Good Items total updates: **95.000 kg**
- Total Sorted updates: **95.000 kg**
- Weight display resets to: **0.000 kg**
- Remarks field clears
- Remove button (×) appears next to item

#### 4B. Second Good Item - Aluminum
1. Click "Capture Weight" button
2. Enter weight: **48**
3. Verify weight display: **48.000 kg**
4. Select Item: **SCRAP-ALUMINUM-01 (Aluminum Scrap)**
5. Enter Remarks: "Clean aluminum"
6. Click "Add Item" button

**Expected:**
- Second item appears in right panel under "Good Items"
- Good Items total: **143.000 kg** (95 + 48)
- Total Sorted: **143.000 kg**
- Variance row appears showing: **-7.000 kg (-4.67%)** (143 - 150 = -7)

### Pass/Fail: ___

---

## Test Case 5: Add Unwanted Items (Return to Supplier)

### Scenario: Worker finds 7kg of plastic contamination to return

### Steps:

1. Click **"Unwanted Items (Return)"** tab
2. Verify tab turns red
3. Verify "Return Reason" dropdown appears
4. Click "Capture Weight"
5. Enter weight: **7**
6. Verify weight: **7.000 kg**
7. Select Item: **SCRAP-PLASTIC-01 (Plastic Contamination)**
8. Select Return Reason: **Contamination**
9. Enter Remarks: "Plastic bags mixed in"
10. Click "Add Item"

### Expected Result:
- Item appears under "Unwanted Items" section (red heading)
- Shows: "Plastic Contamination - 7.000 Kg - Contamination"
- Unwanted Items total: **7.000 kg**
- Good Items total: **143.000 kg** (unchanged)
- Total Sorted: **150.000 kg** (143 + 7)
- Variance: **0.000 kg (0.00%)** ← Perfect match!
- **Submit Sorting button becomes enabled** (no longer disabled)

### Pass/Fail: ___

---

## Test Case 6: Review and Submit Sorting

### Steps:
1. Review right panel summary:
   - Good Items: 143.000 kg
   - Unwanted: 7.000 kg
   - Total Sorted: 150.000 kg
   - Variance: 0.000 kg (0.00%)
2. Verify all items listed correctly
3. Click **"Submit Sorting"** button

### Expected Result:
- API call: `scrap_metal_suite.api.v1.production.create_sorting`
- Success message: "Sorting PROD-SORT-2026-00001 submitted successfully"
- Form resets:
  - Items list clears
  - Dropoff selection clears
  - Totals reset to 0.000 kg
  - Submit button disabled again
- Can select same or different dropoff for next sorting

### Pass/Fail: ___

---

## Test Case 7: Verify Production Sorting Record

### Steps:
1. Open new tab: http://smt.local:8000/app/production-sorting
2. Find the newly created record (e.g., PROD-SORT-2026-00001)
3. Open the record

### Expected Result:
**Header:**
- Status: Submitted (green badge)
- Dropoff: DROPOFF-2026-00001 (clickable link)
- Session: PROD-SESS-2026-00001
- Posting Date/Time: Today's date and time

**Good Items Table:**
| Item Code | Item Name | Weight | UOM | Remarks |
|-----------|-----------|--------|-----|---------|
| SCRAP-COPPER-01 | Copper Wire Scrap | 95.000 | Kg | Good quality copper |
| SCRAP-ALUMINUM-01 | Aluminum Scrap | 48.000 | Kg | Clean aluminum |

**Unwanted Items Table:**
| Item Code | Item Name | Weight | Return Reason | Remarks |
|-----------|-----------|--------|---------------|---------|
| SCRAP-PLASTIC-01 | Plastic Contamination | 7.000 | Contamination | Plastic bags mixed in |

**Totals:**
- Total Good Weight: 143.000 kg
- Total Unwanted Weight: 7.000 kg
- Total Weight: 150.000 kg

### Pass/Fail: ___

---

## Test Case 8: Verify Dropoff Final (Auto-Aggregation)

### Steps:
1. Open new tab: http://smt.local:8000/app/dropoff-final
2. Find record for DROPOFF-2026-00001
3. Open the record

### Expected Result:
**Header:**
- Dropoff: DROPOFF-2026-00001 (link)
- Status: **Completed** (auto-completed because variance OK)
- Dropoff Total Weight: 150.000 kg
- Total Verified Weight: 150.000 kg

**Good Items Table (Aggregated):**
| Item Code | Item Name | Weight | UOM |
|-----------|-----------|--------|-----|
| SCRAP-COPPER-01 | Copper Wire Scrap | 95.000 | Kg |
| SCRAP-ALUMINUM-01 | Aluminum Scrap | 48.000 | Kg |

**Unwanted Items Table (Aggregated):**
| Item Code | Item Name | Weight | Return Reason |
|-----------|-----------|--------|---------------|
| SCRAP-PLASTIC-01 | Plastic Contamination | 7.000 | Contamination |

**Verification:**
- Total Good Weight: 143.000 kg
- Total Unwanted Weight: 7.000 kg
- Weight Variance: 0.000 kg
- Variance Percent: 0.00%
- Variance OK: ✓ (checked)

**Summary Stats (from JavaScript):**
- Should display visual breakdown table
- Green row for good items
- Red row for unwanted items

### Pass/Fail: ___

---

## Test Case 9: Multiple Workers Scenario

### Scenario: Two workers sort the same dropoff simultaneously

### Steps:

#### Worker 1:
1. Open session with Production Scale 01
2. Select DROPOFF-2026-00002 (create a new dropoff first with 200kg total)
3. Add good items: 100kg copper
4. Submit sorting → Creates PROD-SORT-2026-00002

#### Worker 2 (different browser/user):
1. Open session with Production Scale 02 (create another scale)
2. Select **same dropoff** DROPOFF-2026-00002
3. Add good items: 95kg aluminum
4. Add unwanted: 5kg plastic
5. Submit sorting → Creates PROD-SORT-2026-00003

### Expected Result:
- Both sortings submitted successfully (no unique constraint error)
- Dropoff Final for DROPOFF-2026-00002 shows:
  - Total Good Weight: 195.000 kg (100 + 95)
  - Total Unwanted: 5.000 kg
  - Total Verified: 200.000 kg
  - Variance: 0.000 kg
  - Status: Completed

**This tests the key requirement:** Multiple Production Sorting sessions → One Dropoff Final

### Pass/Fail: ___

---

## Test Case 10: Remove Item Before Submit

### Steps:
1. Start session, select dropoff
2. Add 3 good items
3. Click **× (remove button)** on the 2nd item
4. Verify item disappears
5. Verify totals recalculate
6. Submit sorting

### Expected Result:
- Item removed successfully
- Totals update immediately
- Only 2 items (not 3) in submitted Production Sorting record

### Pass/Fail: ___

---

## Test Case 11: Variance Warning

### Scenario: Total sorted doesn't match dropoff weight

### Steps:
1. Select dropoff with 150kg total
2. Add only 100kg of good items
3. Observe variance row

### Expected Result:
- Variance row shows: **-50.000 kg (-33.33%)**
- Orange/yellow color for variance value
- Can still submit (variance check happens at Dropoff Final level)
- Dropoff Final status: **In Progress** (not auto-completed)

### Pass/Fail: ___

---

## Test Case 12: Close Production Session

### Steps:
1. Click "Close Session" button in header
2. Confirm dialog appears
3. Click "Yes" to confirm

### Expected Result:
- API call: `scrap_metal_suite.api.v1.production.close_session`
- Success message: "Session closed successfully"
- Redirect to: http://smt.local:8000/pos/production
- Shows session setup screen again
- Can start new session

### Pass/Fail: ___

---

## Test Case 13: Permission Check

### Steps:
1. Login as user **without** Production Worker/Manager role
2. Navigate to http://smt.local:8000/pos/production

### Expected Result:
- Page loads but shows error:
  - "Access Denied"
  - "You don't have permission to access the Production Sorting system."
  - "Back to POS" button visible

### Pass/Fail: ___

---

## Test Case 14: Form Validation

### Test invalid inputs:

#### A. No Dropoff Selected
1. Start session
2. Try to add item without selecting dropoff
3. Expected: Item select dropdown disabled

#### B. No Item Selected
1. Select dropoff
2. Capture weight
3. Don't select item
4. Expected: "Add Item" button disabled

#### C. Zero Weight
1. Select dropoff and item
2. Don't capture weight (weight = 0.000)
3. Expected: "Add Item" button disabled

#### D. No Items Added
1. Select dropoff
2. Don't add any items
3. Expected: "Submit Sorting" button disabled

### Pass/Fail: ___

---

## API Endpoints Tested

All endpoints in `scrap_metal_suite/api/v1/production.py`:

| Endpoint | Method | Test Case | Status |
|----------|--------|-----------|--------|
| `open_session` | POST | TC 2 | ☐ |
| `close_session` | POST | TC 12 | ☐ |
| `search_dropoff` | GET | TC 3 | ☐ |
| `create_sorting` | POST | TC 6 | ☐ |
| `get_dropoff_final_status` | GET | TC 8 | ☐ |
| `update_dropoff_final` | (helper) | TC 8 | ☐ |

---

## DocTypes Tested

| DocType | CRUD | Validation | Auto-Logic | Status |
|---------|------|------------|------------|--------|
| Production Sorting | ✓ | ✓ | Submit triggers | ☐ |
| Production Sorting Good Item | ✓ | ✓ | Weight validation | ☐ |
| Production Sorting Unwanted Item | ✓ | ✓ | Return reason required | ☐ |
| Dropoff Final | Read | ✓ | Auto-create/update | ☐ |
| Dropoff Final Good Item | Read | ✓ | Auto-aggregate | ☐ |
| Dropoff Final Unwanted Item | Read | ✓ | Auto-aggregate | ☐ |

---

## UI Components Tested

| Component | Functionality | Status |
|-----------|---------------|--------|
| POS Landing Page | Orange terminal card | ☐ |
| Production Header | Session info, close button | ☐ |
| Session Setup | Scale selection | ☐ |
| Dropoff Search | Autocomplete | ☐ |
| Dropoff Details | Display info, clear | ☐ |
| Weight Display | Show current weight | ☐ |
| Item Type Tabs | Switch good/unwanted | ☐ |
| Return Reason | Show/hide for unwanted | ☐ |
| Item Selection | Dropdown populate | ☐ |
| Capture Weight | Manual entry (scale integration pending) | ☐ |
| Add Item | Validation, list update | ☐ |
| Items List | Display, remove buttons | ☐ |
| Summary Totals | Real-time calculation | ☐ |
| Variance Display | Color-coded warnings | ☐ |
| Submit Button | Enable/disable logic | ☐ |

---

## Known Limitations (Current Phase)

1. **Scale Integration:** Weight capture uses manual prompt (scale_reader.js integration ready but not tested)
2. **Production Session DocType:** May not exist - API will need to create or use POS Session
3. **Production Sorting Settings:** DocType referenced but may not exist
4. **QR Scanning:** Not implemented in Production Terminal (can add later)
5. **Translations:** English only (Thai translations in pos-translations.js not integrated)

---

## Next Steps After Testing

1. **Fix any failing test cases**
2. **Create Production Session DocType** (if missing)
3. **Create Production Sorting Settings DocType** (if missing)
4. **Integrate real scale reading** (remove manual prompt)
5. **Add QR scanner** for dropoff selection
6. **Add Thai translations**
7. **Print format** for Production Sorting records
8. **Reports:** Production efficiency, variance analysis

---

## Test Summary

**Total Test Cases:** 14
**Passed:** ___
**Failed:** ___
**Blocked:** ___

**Tester:** _______________
**Date:** _______________
**Environment:** http://smt.local:8000
**Build Version:** Phase 5 Complete (2026-03-08)

---

## Bug Report Template

If you find bugs, document here:

### Bug #1
- **Test Case:** ___
- **Steps to Reproduce:** ___
- **Expected Result:** ___
- **Actual Result:** ___
- **Screenshot/Error:** ___
- **Severity:** Critical / High / Medium / Low
