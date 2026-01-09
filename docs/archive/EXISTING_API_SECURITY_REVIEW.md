# Existing API Security Review

## Executive Summary

This document reviews the security posture of **currently implemented** APIs in the Scrap Metal Suite application.

**Review Date**: 2025-12-17
**Scope**: Existing `@frappe.whitelist()` APIs only (not planned features)

**Files Reviewed**:
- `scrap_metal_suite/api/v1/__init__.py` (2 APIs)
- `scrap_metal_suite/api/v1/pos.py` (18 APIs)

---

## API Inventory

### api/v1/__init__.py (2 APIs)
1. `get_countries()` - Line 11 - Guest accessible
2. `debug_supplier_link()` - Line 22 - Auth required

### api/v1/pos.py (18 APIs)
1. `get_pos_profile()` - Line 42
2. `get_active_session()` - Line 70
3. `open_session()` - Line 103
4. `close_session()` - Line 142
5. `lookup_order()` - Line 165
6. `get_order_details()` - Line 241
7. `load_scrap_weight()` - Line 321
8. **`create_scrap_weight()` - Line 354** ⚠️ Security concerns
9. `get_session_weights()` - Line 481
10. `get_session_summary()` - Line 516
11. **`record_truck_weight()` - Line 549** ⚠️ Security concerns
12. `save_truck_remarks()` - Line 617
13. `update_total_scrap_weight()` - Line 645
14. `mark_reweighed()` - Line 684
15. `get_scales()` - Line 717
16. `get_scale_by_id()` - Line 748
17. `set_session_scale()` - Line 799
18. `get_weight_verification()` - Line 865

---

## Critical Findings

### 1. `create_scrap_weight()` - MEDIUM RISK

**Location**: `scrap_metal_suite/api/v1/pos.py:354-478`

#### Security Issues

**Issue 1: No Weight Validation** (Line 409)
```python
item_data = {
    "item_code": item.get("item_code"),
    "weight": flt(item.get("weight")),  # ❌ No validation
    "uom": item.get("uom", "Kg")
}
```

**Problems**:
- Negative weights accepted: `-100 kg`
- Zero weights accepted: `0 kg`
- Extremely large values: `999999999 kg`
- `flt()` returns 0 for invalid input silently

**Impact**: Data integrity issues, potential business logic errors

**Issue 2: XSS Vulnerability in Remarks** (Lines 430, 444)
```python
scrap_weight.remarks = remarks  # ❌ No sanitization
```

**Problems**:
- `remarks` parameter stored without sanitization
- Could contain malicious JavaScript
- Will execute when displayed in UI or reports

**Impact**: Cross-site scripting attack vector

**Issue 3: Weak Session Validation** (Lines 384-391)
```python
session_data = frappe.db.get_value(
    "POS Session",
    session,
    ["status", "scale", "pos_profile"],
    as_dict=True
)
if not session_data or session_data.status != "Open":
    frappe.throw(_("Session {0} is not open").format(session))
# ❌ Doesn't verify session.operator == current_user
```

**Problems**:
- Validates session exists and is open
- Does NOT verify the session belongs to current user
- User A could create weights in User B's session

**Impact**: Session hijacking, data manipulation

#### Recommended Fixes

```python
@frappe.whitelist()
def create_scrap_weight(session, pos_order, items, remarks=None,
                        existing_scrap_weight=None, reweight_reason=None):
    """Record or update scrap weight for a POS Order."""
    check_pos_operator()
    import json

    if isinstance(items, str):
        items = json.loads(items)

    if not items:
        frappe.throw(_("At least one item is required"))

    # FIX 1: Validate session ownership
    session_data = frappe.db.get_value(
        "POS Session",
        session,
        ["status", "scale", "pos_profile", "operator"],  # Added operator
        as_dict=True
    )

    if not session_data or session_data.status != "Open":
        frappe.throw(_("Session {0} is not open").format(session))

    # NEW: Verify session belongs to current user
    if session_data.operator != frappe.session.user:
        # Allow System Manager to override
        if "System Manager" not in frappe.get_roles():
            frappe.throw(_("You can only create weights in your own session"))

    # Validate POS Order exists
    order_data = frappe.db.get_value(
        "POS Order",
        pos_order,
        ["name", "supplier", "status", "license_plate"],
        as_dict=True
    )

    if not order_data:
        frappe.throw(_("POS Order {0} not found").format(pos_order))

    # FIX 2: Validate and sanitize items
    weight_items = []
    for item in items:
        # Validate weight
        try:
            weight = float(item.get("weight", 0))
        except (ValueError, TypeError):
            frappe.throw(_("Invalid weight value for item {0}").format(item.get("item_code")))

        if weight <= 0:
            frappe.throw(_("Weight must be greater than zero for item {0}").format(item.get("item_code")))

        if weight > 100000:  # 100 tons max
            frappe.throw(_("Weight exceeds maximum allowed value for item {0}").format(item.get("item_code")))

        item_data = {
            "item_code": item.get("item_code"),
            "weight": weight,
            "uom": item.get("uom", "Kg")
        }
        weight_items.append(item_data)

    # FIX 3: Sanitize remarks
    if remarks:
        from frappe.utils import sanitize_html
        remarks = sanitize_html(remarks.strip())

        if len(remarks) > 1000:  # Reasonable limit
            frappe.throw(_("Remarks exceed maximum length"))

    is_reweight = False

    if existing_scrap_weight:
        # UPDATE existing document
        scrap_weight = frappe.get_doc("Scrap Weight", existing_scrap_weight)

        # Clear existing items and add new ones
        scrap_weight.items = []
        for item_data in weight_items:
            scrap_weight.append("items", item_data)

        # Mark as reweight
        scrap_weight.is_reweight = 1
        scrap_weight.reweight_reason = reweight_reason
        scrap_weight.reweight_at = frappe.utils.now_datetime()
        scrap_weight.reweight_by = frappe.session.user
        scrap_weight.remarks = remarks  # Now sanitized

        scrap_weight.save()
        is_reweight = True
    else:
        # CREATE new document
        scrap_weight = frappe.get_doc({
            "doctype": "Scrap Weight",
            "pos_order": pos_order,
            "supplier": order_data.supplier,
            "posting_date": nowdate(),
            "session": session,
            "pos_profile": session_data.pos_profile,
            "scale": session_data.scale,
            "remarks": remarks,  # Now sanitized
            "is_reweight": 0,
            "items": weight_items
        })
        scrap_weight.insert()

    # Update POS Order (rest of the code remains the same)
    order_doc = frappe.get_doc("POS Order", pos_order)
    order_doc.status = "Processed"
    order_doc.processed_by = frappe.session.user
    order_doc.processed_time = frappe.utils.now_datetime()

    total_scrap = frappe.db.sql("""
        SELECT COALESCE(SUM(total_weight), 0) as total
        FROM `tabScrap Weight`
        WHERE pos_order = %s
    """, pos_order, as_dict=True)[0].total
    order_doc.total_scrap_weight = flt(total_scrap)

    if order_doc.net_truck_weight:
        _calculate_variance(order_doc)

    order_doc.save()

    return {
        "scrap_weight": scrap_weight.name,
        "total_weight": scrap_weight.total_weight,
        "order_id": pos_order,
        "is_reweight": is_reweight,
        "total_scrap_weight": order_doc.total_scrap_weight,
        "weight_variance": order_doc.weight_variance,
        "weight_variance_percent": order_doc.weight_variance_percent
    }
```

---

### 2. `record_truck_weight()` - MEDIUM RISK

**Location**: `scrap_metal_suite/api/v1/pos.py:549-614`

#### Security Issues

**Issue 1: Basic Weight Validation Only** (Lines 569-571)
```python
weight = flt(weight)
if weight <= 0:
    frappe.throw(_("Weight must be greater than 0"))
```

**Problems**:
- Only checks for positive value
- No maximum value validation
- Could accept unrealistic weights like 999999999 kg

**Issue 2: No XSS Sanitization on Remarks** (Line 589)
```python
if remarks and hasattr(order, 'truck_weight_remarks'):
    order.truck_weight_remarks = remarks  # ❌ No sanitization
```

**Impact**: XSS vulnerability

#### Recommended Fixes

```python
@frappe.whitelist()
def record_truck_weight(pos_order, weight_type, weight, scale=None, remarks=None):
    """Record truck gross or tare weight for a POS Order."""
    check_pos_operator()

    if weight_type not in ['gross', 'tare']:
        frappe.throw(_("weight_type must be 'gross' or 'tare'"))

    # FIX: Enhanced weight validation
    try:
        weight = float(weight)
    except (ValueError, TypeError):
        frappe.throw(_("Invalid weight value"))

    if weight <= 0:
        frappe.throw(_("Weight must be greater than 0"))

    # Maximum weight for truck scale (adjust as needed)
    if weight > 100000:  # 100 tons
        frappe.throw(_("Weight exceeds maximum capacity"))

    order = frappe.get_doc("POS Order", pos_order)

    # Record the weight with timestamp and scale
    if weight_type == 'gross':
        order.gross_weight = weight
        order.gross_weight_time = frappe.utils.now_datetime()
        if scale:
            order.gross_weight_scale = scale
    else:
        order.tare_weight = weight
        order.tare_weight_time = frappe.utils.now_datetime()
        if scale:
            order.tare_weight_scale = scale

    # FIX: Sanitize remarks
    if remarks and hasattr(order, 'truck_weight_remarks'):
        from frappe.utils import sanitize_html
        remarks = sanitize_html(remarks.strip())

        if len(remarks) > 1000:
            frappe.throw(_("Remarks exceed maximum length"))

        order.truck_weight_remarks = remarks

    # Calculate net truck weight if both weights are available
    if order.gross_weight and order.tare_weight:
        order.net_truck_weight = flt(order.gross_weight) - flt(order.tare_weight)

        # Calculate variance if scrap weight exists
        if order.total_scrap_weight:
            _calculate_variance(order)

    order.save()

    return {
        "order_id": order.name,
        "gross_weight": order.gross_weight,
        "gross_weight_time": order.gross_weight_time,
        "gross_weight_scale": getattr(order, 'gross_weight_scale', None),
        "tare_weight": order.tare_weight,
        "tare_weight_time": order.tare_weight_time,
        "tare_weight_scale": getattr(order, 'tare_weight_scale', None),
        "net_truck_weight": order.net_truck_weight,
        "total_scrap_weight": getattr(order, 'total_scrap_weight', None),
        "weight_variance": getattr(order, 'weight_variance', None),
        "weight_variance_percent": getattr(order, 'weight_variance_percent', None),
        "truck_weight_remarks": getattr(order, 'truck_weight_remarks', None)
    }
```

---

### 3. `debug_supplier_link()` - LOW RISK (Information Disclosure)

**Location**: `scrap_metal_suite/api/v1/__init__.py:22-66`

#### Security Issues

**Issue: Information Disclosure**
```python
@frappe.whitelist()
def debug_supplier_link():
    """Debug endpoint to check User → Contact → Supplier linking"""
    user = frappe.session.user
    result = {
        "user": user,
        "user_roles": frappe.get_roles(user),  # Exposes user roles
        # ... more internal data
    }
    return result
```

**Problems**:
- ANY logged-in user can call this
- Exposes internal system structure
- Shows user roles (security information)
- Shows database relationships

**Impact**:
- Information disclosure
- Could help attacker understand system architecture
- Not critical but shouldn't be in production

#### Recommended Fix

**Option 1**: Remove in production
```python
# Delete this function or comment it out in production
```

**Option 2**: Restrict to System Managers only
```python
@frappe.whitelist()
def debug_supplier_link():
    """Debug endpoint to check User → Contact → Supplier linking"""

    # Restrict to System Managers only
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Access Denied"), frappe.PermissionError)

    # Rest of the code...
```

**Option 3**: Move to development-only
```python
import frappe

@frappe.whitelist()
def debug_supplier_link():
    """Debug endpoint - Development only"""

    # Only allow in development mode
    if not frappe.conf.developer_mode:
        frappe.throw(_("This endpoint is only available in developer mode"))

    # Rest of the code...
```

---

## Other APIs - Security Status

### ✅ Good Security (No Issues Found)

These APIs have proper security controls:

1. **`get_pos_profile()`** - Line 42
   - ✅ Has `check_pos_operator()`
   - ✅ No user input stored
   - ✅ Read-only operation

2. **`get_active_session()`** - Line 70
   - ✅ Has `check_pos_operator()`
   - ✅ Filters by current user automatically
   - ✅ Read-only operation

3. **`close_session()`** - Line 142
   - ✅ Has `check_pos_operator()`
   - ✅ Verifies session ownership (line 157-160)
   - ✅ Proper authorization check

4. **`get_session_weights()`** - Line 481
   - ✅ Has `check_pos_operator()`
   - ✅ Verifies session ownership (line 494-501)
   - ✅ Read-only operation

5. **`set_session_scale()`** - Line 799
   - ✅ Has `check_pos_operator()`
   - ✅ Verifies session ownership (line 818-821)
   - ✅ Validates scale exists and is active

### ⚠️ Minor Issues (Low Priority)

6. **`save_truck_remarks()`** - Line 617
   - ⚠️ No XSS sanitization on remarks
   - ✅ Has permission check
   - **Fix**: Add `sanitize_html()` on line 636

7. **`lookup_order()`** - Line 165
   - ⚠️ Uses SQL with LIKE (potential SQL injection)
   - ✅ Parameters are escaped by frappe
   - ✅ Limited to 10 results
   - **Status**: Acceptable (Frappe handles escaping)

---

## Summary of Vulnerabilities

| Severity | Count | APIs Affected |
|----------|-------|---------------|
| **CRITICAL** | 0 | None |
| **HIGH** | 0 | None |
| **MEDIUM** | 2 | `create_scrap_weight()`, `record_truck_weight()` |
| **LOW** | 2 | `debug_supplier_link()`, `save_truck_remarks()` |
| **TOTAL** | 4 | 4 out of 20 APIs |

---

## Recommendations Priority

### Immediate (Deploy This Week)
1. ✅ Fix `create_scrap_weight()` - Add weight validation and XSS sanitization
2. ✅ Fix `record_truck_weight()` - Add max weight limit and XSS sanitization
3. ✅ Fix `create_scrap_weight()` - Add session ownership verification

### Short Term (Deploy Within 2 Weeks)
4. ✅ Fix `save_truck_remarks()` - Add XSS sanitization
5. ✅ Restrict or remove `debug_supplier_link()` - Remove information disclosure

### Best Practices for Future APIs

When creating new `@frappe.whitelist()` APIs:

1. **Always validate numeric inputs**:
   ```python
   weight = float(input)
   if weight <= 0 or weight > MAX_VALUE:
       frappe.throw("Invalid weight")
   ```

2. **Always sanitize text inputs**:
   ```python
   from frappe.utils import sanitize_html
   text = sanitize_html(input.strip())
   ```

3. **Always verify ownership**:
   ```python
   if doc.owner != frappe.session.user and "System Manager" not in frappe.get_roles():
       frappe.throw("Access denied")
   ```

4. **Use helper function for common checks**:
   ```python
   def validate_weight(weight, max_value=100000):
       try:
           weight = float(weight)
       except (ValueError, TypeError):
           frappe.throw("Invalid weight")

       if weight <= 0:
           frappe.throw("Weight must be positive")

       if weight > max_value:
           frappe.throw(f"Weight exceeds maximum of {max_value}")

       return weight
   ```

---

## Conclusion

The existing API codebase has **good overall security** with proper permission checks throughout. The main issues are:

1. **Input validation** - Weight values need min/max validation
2. **XSS prevention** - Text fields need sanitization
3. **Session ownership** - One API needs stricter ownership check
4. **Debug endpoint** - Should be removed or restricted

**Overall Risk**: **MEDIUM** - Issues are fixable with straightforward code changes. No critical vulnerabilities that would allow data breach or system compromise.

**Recommended Action**: Implement the fixes for `create_scrap_weight()` and `record_truck_weight()` before adding new scale integration features.

---

**Document Version**: 1.0
**Last Updated**: 2025-12-17
**Next Review**: After implementing fixes
