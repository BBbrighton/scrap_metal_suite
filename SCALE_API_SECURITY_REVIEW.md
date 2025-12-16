# Scale Integration API Security Review

## Executive Summary

This document reviews the security posture of all Scale Integration APIs and provides recommendations for hardening them against common vulnerabilities.

**Review Date**: 2025-12-17
**Reviewer**: Security Analysis
**Scope**: All `@frappe.whitelist()` APIs in Scale Integration Plan

---

## Understanding `@frappe.whitelist()`

### What It Does
- Makes a Python method callable via HTTP API
- **Requires user authentication** (logged-in session)
- Does NOT automatically check permissions
- Does NOT validate input data
- Vulnerable to CSRF attacks if not properly configured (Frappe handles this automatically)

### What It Doesn't Do
- ❌ Doesn't restrict by role
- ❌ Doesn't validate input types/ranges
- ❌ Doesn't prevent SQL injection (you must use ORM)
- ❌ Doesn't sanitize output

**Security Rule**: Always add explicit permission checks and input validation in whitelisted methods.

---

## API Security Analysis

### 1. `verify_weight_override_pin(pin)`

**Purpose**: Verify user's PIN and check weight override permission

#### Current Implementation
```python
@frappe.whitelist()
def verify_weight_override_pin(pin):
    """Verify PIN and check if user has weight override permission"""
    user = frappe.session.user

    # Get POS Authority Code for current user
    authority = frappe.get_value("POS Authority Code",
        {"user": user},
        ["name", "pin_code", "can_override_weight"],
        as_dict=1)

    if not authority:
        frappe.throw(_("No authority code found for user"))

    if not authority.can_override_weight:
        frappe.throw(_("User does not have weight override permission"))

    # Verify PIN (compare hashed values)
    from frappe.utils.password import check_password
    if not check_password(authority.name, pin, "pin_code"):
        frappe.throw(_("Invalid PIN"))

    return {
        "success": True,
        "user": user,
        "user_full_name": frappe.get_value("User", user, "full_name")
    }
```

#### Security Assessment

| Aspect | Status | Notes |
|--------|--------|-------|
| Authentication | ✅ Good | Uses `frappe.session.user` |
| Authorization | ✅ Good | Checks `can_override_weight` permission |
| Input Validation | ⚠️ Needs Improvement | No PIN format validation |
| Rate Limiting | ❌ Missing | Vulnerable to brute force |
| Audit Logging | ❌ Missing | No log of failed attempts |
| Session Management | ✅ Good | User can only verify own PIN |

#### Vulnerabilities

**HIGH: Brute Force Attack**
- No rate limiting on PIN verification
- Attacker could try thousands of PINs
- No account lockout mechanism

**MEDIUM: No Audit Trail**
- Failed PIN attempts not logged
- Cannot detect brute force attempts
- No forensic evidence

**LOW: No Input Validation**
- PIN could be empty string
- PIN could be extremely long (DoS)
- No format validation

#### Recommended Fixes

```python
@frappe.whitelist()
def verify_weight_override_pin(pin):
    """Verify PIN and check if user has weight override permission

    Security: Rate limited to 5 attempts per 15 minutes
    """
    user = frappe.session.user

    # Rate limiting check
    from frappe.utils import now_datetime, add_to_date
    cache_key = f"pin_attempts:{user}"
    attempts = frappe.cache().get(cache_key) or []

    # Remove attempts older than 15 minutes
    cutoff_time = add_to_date(now_datetime(), minutes=-15)
    recent_attempts = [a for a in attempts if a > cutoff_time]

    if len(recent_attempts) >= 5:
        # Log security event
        frappe.logger().security(f"PIN brute force detected for user {user}")
        frappe.throw(_("Too many failed attempts. Please try again in 15 minutes."))

    # Input validation
    if not pin or not isinstance(pin, str):
        frappe.throw(_("Invalid PIN format"))

    if len(pin) < 4 or len(pin) > 10:
        frappe.throw(_("PIN must be between 4 and 10 characters"))

    # Get POS Authority Code for current user
    authority = frappe.get_value("POS Authority Code",
        {"user": user},
        ["name", "pin_code", "can_override_weight"],
        as_dict=1)

    if not authority:
        frappe.throw(_("No authority code found for user"))

    if not authority.can_override_weight:
        frappe.throw(_("User does not have weight override permission"))

    # Verify PIN (compare hashed values)
    from frappe.utils.password import check_password
    pin_valid = check_password(authority.name, pin, "pin_code")

    if not pin_valid:
        # Record failed attempt
        recent_attempts.append(now_datetime())
        frappe.cache().set(cache_key, recent_attempts, expires_in_sec=900)  # 15 min

        # Log failed attempt
        frappe.logger().security(f"Failed PIN attempt for user {user}")

        frappe.throw(_("Invalid PIN"))

    # Success - clear attempts
    frappe.cache().delete(cache_key)

    # Log successful verification
    frappe.logger().info(f"PIN verified successfully for user {user}")

    return {
        "success": True,
        "user": user,
        "user_full_name": frappe.get_value("User", user, "full_name")
    }
```

---

### 2. `get_scale_config(scale_name)`

**Purpose**: Retrieve WebSerial configuration for a scale

#### Current Implementation
```python
@frappe.whitelist()
def get_scale_config(scale_name):
    """Get WebSerial configuration for a scale

    Used by:
    - POS interface to connect to pre-configured scales
    - Scale config page to load current settings
    """
    scale = frappe.get_doc("Scale", scale_name)

    return {
        "baudRate": scale.baud_rate or 1200,
        "dataBits": int(scale.data_bits or 8),
        "parity": scale.parity or "none",
        "stopBits": int(scale.stop_bits or 1),
        "flowControl": scale.flow_control or "none",
        "bufferSize": scale.buffer_size or 255,
        "delimiter": scale.delimiter or "lf",
        "fixedLen": scale.fixed_length or 17,
        "rawLog": False
    }
```

#### Security Assessment

| Aspect | Status | Notes |
|--------|--------|-------|
| Authentication | ✅ Good | Requires login |
| Authorization | ❌ **Critical** | **ANY logged-in user can access** |
| Input Validation | ❌ Missing | No validation of `scale_name` |
| Data Exposure | ⚠️ Medium | Config data not sensitive but should be restricted |
| SQL Injection | ⚠️ Potential | If `scale_name` not sanitized |

#### Vulnerabilities

**CRITICAL: No Authorization Check**
- Suppliers can read scale configs
- Manager portal users can access
- Anyone logged in can enumerate all scales

**HIGH: Potential SQL Injection**
- `frappe.get_doc("Scale", scale_name)` trusts input
- If Frappe ORM doesn't sanitize, vulnerable
- Could read arbitrary Scale documents

**MEDIUM: Information Disclosure**
- Attackers can map all scales
- Learn system topology
- Prepare targeted attacks

**LOW: No Error Handling**
- If scale doesn't exist, error reveals system info
- Stack traces could leak paths

#### Recommended Fixes

```python
@frappe.whitelist()
def get_scale_config(scale_name):
    """Get WebSerial configuration for a scale

    Security: Restricted to System Manager and POS User roles

    Used by:
    - POS interface to connect to pre-configured scales
    - Scale config page to load current settings

    Args:
        scale_name: Name of the Scale document (e.g., 'SCALE-001')

    Returns:
        dict: WebSerial configuration

    Raises:
        PermissionError: If user doesn't have required role
        DoesNotExistError: If scale not found
    """
    # Authorization check
    user_roles = frappe.get_roles()
    allowed_roles = ["System Manager", "POS User", "POS Manager"]

    if not any(role in user_roles for role in allowed_roles):
        frappe.logger().security(
            f"Unauthorized scale config access attempt by {frappe.session.user} "
            f"for scale {scale_name}"
        )
        frappe.throw(
            _("You do not have permission to access scale configuration"),
            frappe.PermissionError
        )

    # Input validation
    if not scale_name or not isinstance(scale_name, str):
        frappe.throw(_("Invalid scale name"))

    # Sanitize input (prevent injection)
    scale_name = frappe.db.escape(scale_name.strip())

    # Check if scale exists
    if not frappe.db.exists("Scale", scale_name):
        frappe.logger().warning(
            f"Scale not found: {scale_name} requested by {frappe.session.user}"
        )
        frappe.throw(_("Scale {0} not found").format(scale_name), frappe.DoesNotExistError)

    # Additional authorization: POS Users can only access scales from their assigned location
    if "POS User" in user_roles and "System Manager" not in user_roles:
        # Get user's assigned POS Profile/Location
        user_location = get_user_pos_location(frappe.session.user)  # Implement this
        scale_location = frappe.db.get_value("Scale", scale_name, "location")

        if user_location and scale_location and user_location != scale_location:
            frappe.logger().security(
                f"POS User {frappe.session.user} attempted to access "
                f"scale {scale_name} from different location"
            )
            frappe.throw(_("You can only access scales from your assigned location"))

    try:
        scale = frappe.get_doc("Scale", scale_name)

        # Check if scale is active
        if not scale.is_active:
            frappe.throw(_("Scale {0} is not active").format(scale_name))

    except Exception as e:
        frappe.logger().error(f"Error retrieving scale config: {str(e)}")
        frappe.throw(_("Error retrieving scale configuration"))

    # Return sanitized configuration
    return {
        "baudRate": int(scale.baud_rate or 1200),
        "dataBits": int(scale.data_bits or 8),
        "parity": str(scale.parity or "none"),
        "stopBits": int(scale.stop_bits or 1),
        "flowControl": str(scale.flow_control or "none"),
        "bufferSize": int(scale.buffer_size or 255),
        "delimiter": str(scale.delimiter or "lf"),
        "fixedLen": int(scale.fixed_length or 17),
        "rawLog": False
    }
```

---

### 3. `save_scale_config(scale_name, config)`

**Purpose**: Save auto-detected scale configuration to database

#### Current Implementation
```python
@frappe.whitelist()
def save_scale_config(scale_name, config):
    """Save auto-detected or manually entered scale configuration

    Called from /scale-config page after successful auto-detection
    Requires System Manager role
    """
    # Check permissions
    if "System Manager" not in frappe.get_roles():
        frappe.throw(_("Only System Managers can update scale configuration"))

    # Validate scale exists
    if not frappe.db.exists("Scale", scale_name):
        frappe.throw(_("Scale {0} not found").format(scale_name))

    # Get scale document
    scale = frappe.get_doc("Scale", scale_name)

    # Update WebSerial configuration fields
    scale.baud_rate = config.get("baudRate")
    scale.data_bits = str(config.get("dataBits"))
    scale.parity = config.get("parity")
    scale.stop_bits = str(config.get("stopBits"))
    scale.flow_control = config.get("flowControl")
    scale.buffer_size = config.get("bufferSize")
    scale.delimiter = config.get("delimiter")
    scale.fixed_length = config.get("fixedLength")

    # Save
    scale.save()
    frappe.db.commit()

    return {
        "success": True,
        "message": _("Configuration saved for {0}").format(scale_name),
        "config": config
    }
```

#### Security Assessment

| Aspect | Status | Notes |
|--------|--------|-------|
| Authentication | ✅ Good | Requires login |
| Authorization | ✅ Good | Requires System Manager role |
| Input Validation | ❌ **Critical** | **No validation of config values** |
| Type Safety | ❌ Missing | Type coercion without validation |
| Range Validation | ❌ Missing | Invalid values could be saved |
| Audit Logging | ❌ Missing | Config changes not logged |

#### Vulnerabilities

**CRITICAL: No Input Validation**
- Could save invalid baud rates (e.g., 999999)
- Could save negative values
- Could save wrong data types
- Database could be corrupted

**HIGH: Type Confusion**
- Converting to string/int without validation
- TypeError exceptions not handled
- Could crash application

**MEDIUM: No Audit Trail**
- Config changes not logged
- Cannot track who changed what
- No rollback capability

**LOW: No Atomic Operations**
- `save()` then `commit()` could fail partially
- Could leave database in inconsistent state

#### Recommended Fixes

```python
@frappe.whitelist()
def save_scale_config(scale_name, config):
    """Save auto-detected or manually entered scale configuration

    Security:
    - Requires System Manager role
    - Validates all input values
    - Logs configuration changes

    Args:
        scale_name: Name of Scale document
        config: Dictionary with WebSerial configuration

    Returns:
        dict: Success message and saved config
    """
    # Authorization check
    if "System Manager" not in frappe.get_roles():
        frappe.logger().security(
            f"Unauthorized scale config save attempt by {frappe.session.user}"
        )
        frappe.throw(
            _("Only System Managers can update scale configuration"),
            frappe.PermissionError
        )

    # Input validation - scale_name
    if not scale_name or not isinstance(scale_name, str):
        frappe.throw(_("Invalid scale name"))

    scale_name = frappe.db.escape(scale_name.strip())

    if not frappe.db.exists("Scale", scale_name):
        frappe.throw(_("Scale {0} not found").format(scale_name))

    # Input validation - config must be dict
    if not isinstance(config, dict):
        frappe.throw(_("Invalid configuration format"))

    # Validate and sanitize each configuration value
    valid_baud_rates = [300, 600, 1200, 2400, 4800, 9600, 14400, 19200, 28800, 38400, 57600, 115200]
    valid_data_bits = [7, 8]
    valid_parity = ["none", "even", "odd"]
    valid_stop_bits = [1, 2]
    valid_flow_control = ["none", "hardware"]
    valid_delimiters = ["lf", "cr", "crlf", "fixed"]

    try:
        # Validate baud rate
        baud_rate = int(config.get("baudRate", 1200))
        if baud_rate not in valid_baud_rates:
            frappe.throw(_("Invalid baud rate. Must be one of: {0}").format(", ".join(map(str, valid_baud_rates))))

        # Validate data bits
        data_bits = int(config.get("dataBits", 8))
        if data_bits not in valid_data_bits:
            frappe.throw(_("Data bits must be 7 or 8"))

        # Validate parity
        parity = str(config.get("parity", "none")).lower()
        if parity not in valid_parity:
            frappe.throw(_("Parity must be one of: {0}").format(", ".join(valid_parity)))

        # Validate stop bits
        stop_bits = int(config.get("stopBits", 1))
        if stop_bits not in valid_stop_bits:
            frappe.throw(_("Stop bits must be 1 or 2"))

        # Validate flow control
        flow_control = str(config.get("flowControl", "none")).lower()
        if flow_control not in valid_flow_control:
            frappe.throw(_("Flow control must be one of: {0}").format(", ".join(valid_flow_control)))

        # Validate buffer size
        buffer_size = int(config.get("bufferSize", 255))
        if buffer_size < 1 or buffer_size > 65536:
            frappe.throw(_("Buffer size must be between 1 and 65536"))

        # Validate delimiter
        delimiter = str(config.get("delimiter", "lf")).lower()
        if delimiter not in valid_delimiters:
            frappe.throw(_("Delimiter must be one of: {0}").format(", ".join(valid_delimiters)))

        # Validate fixed length
        fixed_length = int(config.get("fixedLength", 17))
        if fixed_length < 1 or fixed_length > 1024:
            frappe.throw(_("Fixed length must be between 1 and 1024"))

    except ValueError as e:
        frappe.throw(_("Invalid configuration values: {0}").format(str(e)))
    except TypeError as e:
        frappe.throw(_("Invalid configuration types: {0}").format(str(e)))

    # Get scale document
    scale = frappe.get_doc("Scale", scale_name)

    # Store old values for audit log
    old_config = {
        "baudRate": scale.baud_rate,
        "dataBits": scale.data_bits,
        "parity": scale.parity,
        "stopBits": scale.stop_bits,
        "flowControl": scale.flow_control,
        "bufferSize": scale.buffer_size,
        "delimiter": scale.delimiter,
        "fixedLength": scale.fixed_length
    }

    # Update fields with validated values
    scale.baud_rate = baud_rate
    scale.data_bits = str(data_bits)
    scale.parity = parity
    scale.stop_bits = str(stop_bits)
    scale.flow_control = flow_control
    scale.buffer_size = buffer_size
    scale.delimiter = delimiter
    scale.fixed_length = fixed_length

    try:
        # Save in transaction
        scale.save()
        frappe.db.commit()

        # Log configuration change (audit trail)
        frappe.logger().info(
            f"Scale configuration updated for {scale_name} by {frappe.session.user}\n"
            f"Old config: {old_config}\n"
            f"New config: {config}"
        )

        # Create audit log entry (optional: create a custom DocType for this)
        create_scale_config_audit_log(
            scale_name=scale_name,
            user=frappe.session.user,
            old_config=old_config,
            new_config=config,
            timestamp=frappe.utils.now()
        )

    except Exception as e:
        frappe.db.rollback()
        frappe.logger().error(f"Failed to save scale configuration: {str(e)}")
        frappe.throw(_("Failed to save configuration: {0}").format(str(e)))

    return {
        "success": True,
        "message": _("Configuration saved for {0}").format(scale_name),
        "config": {
            "baudRate": baud_rate,
            "dataBits": data_bits,
            "parity": parity,
            "stopBits": stop_bits,
            "flowControl": flow_control,
            "bufferSize": buffer_size,
            "delimiter": delimiter,
            "fixedLength": fixed_length
        }
    }


def create_scale_config_audit_log(scale_name, user, old_config, new_config, timestamp):
    """Create audit log entry for scale configuration changes

    This could be stored in a custom DocType or Error Log
    """
    try:
        # Option 1: Use Error Log (simple)
        frappe.log_error(
            title=f"Scale Config Change: {scale_name}",
            message=f"""
User: {user}
Timestamp: {timestamp}
Scale: {scale_name}

Old Configuration:
{frappe.as_json(old_config, indent=2)}

New Configuration:
{frappe.as_json(new_config, indent=2)}
            """
        )

        # Option 2: Create custom audit log DocType (better for reporting)
        # frappe.get_doc({
        #     "doctype": "Scale Config Audit Log",
        #     "scale": scale_name,
        #     "user": user,
        #     "old_config": frappe.as_json(old_config),
        #     "new_config": frappe.as_json(new_config),
        #     "timestamp": timestamp
        # }).insert(ignore_permissions=True)

    except Exception as e:
        frappe.logger().error(f"Failed to create audit log: {str(e)}")
```

---

### 4. `create_weight_entry(scrap_weight, item_code, weight, weight_entry_mode, override_user, override_reason)`

**Purpose**: Create weight entry for scrap items (auto or manual)

#### Current Implementation
```python
@frappe.whitelist()
def create_weight_entry(scrap_weight, item_code, weight, weight_entry_mode,
                       override_user=None, override_reason=None):
    """Create a weight entry (auto or manual)"""

    # Validate inputs
    if weight_entry_mode == "Manual Override":
        if not override_user or not override_reason:
            frappe.throw(_("Override user and reason required for manual entry"))

    # Create Scrap Weight Item
    weight_item = frappe.get_doc({
        "doctype": "Scrap Weight Item",
        "parent": scrap_weight,
        "parenttype": "Scrap Weight",
        "parentfield": "items",
        "item_code": item_code,
        "weight": weight,
        "weight_entry_mode": weight_entry_mode,
        "manual_override_by": override_user if weight_entry_mode == "Manual Override" else None,
        "manual_override_time": frappe.utils.now() if weight_entry_mode == "Manual Override" else None,
        "manual_override_reason": override_reason if weight_entry_mode == "Manual Override" else None
    })

    return weight_item.as_dict()
```

#### Security Assessment

| Aspect | Status | Notes |
|--------|--------|-------|
| Authentication | ✅ Good | Requires login |
| Authorization | ❌ **CRITICAL** | **NO permission check** |
| Input Validation | ❌ **CRITICAL** | **NO validation** |
| User Impersonation | ❌ **CRITICAL** | **Can fake override_user** |
| Session Validation | ❌ **CRITICAL** | **No session ownership check** |
| XSS Prevention | ❌ Missing | `override_reason` not sanitized |
| Audit Logging | ⚠️ Partial | Logs override but not auto entries |

#### Vulnerabilities

**CRITICAL: No Authorization Check**
- ANY logged-in user can create weight entries
- Suppliers could create fake entries
- Manager portal users could manipulate data

**CRITICAL: User Impersonation**
- Attacker can pass any `override_user`
- Can frame another user for manual overrides
- Audit trail is meaningless

**CRITICAL: No Session Validation**
- User can modify other sessions' weight entries
- No check if `scrap_weight` belongs to user's session
- Session hijacking possible

**CRITICAL: No Input Validation**
- Weight could be negative
- Weight could be zero
- Weight could be extremely large (overflow)
- Item code not validated

**HIGH: XSS Vulnerability**
- `override_reason` stored without sanitization
- Could contain malicious JavaScript
- Could execute when displayed in UI

**MEDIUM: No Transaction Safety**
- Direct document creation without parent validation
- Could create orphaned records

#### Recommended Fixes

```python
@frappe.whitelist()
def create_weight_entry(scrap_weight, item_code, weight, weight_entry_mode,
                       override_user=None, override_reason=None):
    """Create a weight entry (auto or manual)

    Security:
    - Requires POS User role
    - Validates session ownership
    - Prevents user impersonation
    - Validates all inputs
    - Sanitizes text fields

    Args:
        scrap_weight: Name of Scrap Weight document
        item_code: Item code being weighed
        weight: Weight value in kg
        weight_entry_mode: "Auto Scale" or "Manual Override"
        override_user: User performing override (must match current user)
        override_reason: Reason for manual override (sanitized)

    Returns:
        dict: Created Scrap Weight Item
    """
    current_user = frappe.session.user

    # Authorization check
    user_roles = frappe.get_roles()
    if "POS User" not in user_roles:
        frappe.logger().security(
            f"Unauthorized weight entry attempt by {current_user}"
        )
        frappe.throw(
            _("You do not have permission to create weight entries"),
            frappe.PermissionError
        )

    # Validate scrap_weight parameter
    if not scrap_weight or not isinstance(scrap_weight, str):
        frappe.throw(_("Invalid Scrap Weight document"))

    if not frappe.db.exists("Scrap Weight", scrap_weight):
        frappe.throw(_("Scrap Weight {0} not found").format(scrap_weight))

    # Session ownership validation
    scrap_doc = frappe.get_doc("Scrap Weight", scrap_weight)

    # Verify this Scrap Weight belongs to current user's POS Session
    if hasattr(scrap_doc, 'pos_session'):
        session_user = frappe.db.get_value("POS Session", scrap_doc.pos_session, "user")
        if session_user != current_user:
            frappe.logger().security(
                f"User {current_user} attempted to modify "
                f"Scrap Weight {scrap_weight} from session owned by {session_user}"
            )
            frappe.throw(_("You can only modify weight entries from your own session"))

    # Verify document is not submitted/cancelled
    if scrap_doc.docstatus != 0:
        frappe.throw(_("Cannot modify submitted or cancelled Scrap Weight"))

    # Validate item_code
    if not item_code or not isinstance(item_code, str):
        frappe.throw(_("Invalid item code"))

    if not frappe.db.exists("Item", item_code):
        frappe.throw(_("Item {0} not found").format(item_code))

    # Validate weight
    try:
        weight_float = float(weight)
    except (ValueError, TypeError):
        frappe.throw(_("Invalid weight value"))

    if weight_float <= 0:
        frappe.throw(_("Weight must be greater than zero"))

    if weight_float > 100000:  # 100 tons max (adjust as needed)
        frappe.throw(_("Weight exceeds maximum allowed value"))

    # Validate weight_entry_mode
    valid_modes = ["Auto Scale", "Manual Override"]
    if weight_entry_mode not in valid_modes:
        frappe.throw(_("Invalid weight entry mode"))

    # Manual Override specific validation
    if weight_entry_mode == "Manual Override":
        # Validate override_user is provided
        if not override_user:
            frappe.throw(_("Override user is required for manual entry"))

        # CRITICAL: Verify override_user matches current user
        # Prevent user impersonation
        if override_user != current_user:
            frappe.logger().security(
                f"User impersonation attempt: {current_user} tried to "
                f"create override as {override_user}"
            )
            frappe.throw(
                _("You can only create manual overrides for yourself"),
                frappe.PermissionError
            )

        # Validate override_reason is provided
        if not override_reason or not isinstance(override_reason, str):
            frappe.throw(_("Override reason is required for manual entry"))

        # Sanitize override_reason (prevent XSS)
        from frappe.utils import sanitize_html
        override_reason = sanitize_html(override_reason.strip())

        if len(override_reason) < 10:
            frappe.throw(_("Override reason must be at least 10 characters"))

        if len(override_reason) > 500:
            frappe.throw(_("Override reason is too long (max 500 characters)"))

        # Verify user has override permission
        authority = frappe.get_value("POS Authority Code",
            {"user": current_user},
            ["can_override_weight"],
            as_dict=1)

        if not authority or not authority.can_override_weight:
            frappe.logger().security(
                f"User {current_user} attempted manual override without permission"
            )
            frappe.throw(_("You do not have permission for manual weight override"))

    # Create Scrap Weight Item in transaction
    try:
        weight_item = frappe.get_doc({
            "doctype": "Scrap Weight Item",
            "parent": scrap_weight,
            "parenttype": "Scrap Weight",
            "parentfield": "items",
            "item_code": item_code,
            "weight": weight_float,
            "weight_entry_mode": weight_entry_mode,
            "manual_override_by": override_user if weight_entry_mode == "Manual Override" else None,
            "manual_override_time": frappe.utils.now() if weight_entry_mode == "Manual Override" else None,
            "manual_override_reason": override_reason if weight_entry_mode == "Manual Override" else None
        })

        weight_item.insert()
        frappe.db.commit()

        # Audit logging
        log_message = (
            f"Weight entry created: {weight_float}kg of {item_code} "
            f"in {scrap_weight} by {current_user} "
            f"(mode: {weight_entry_mode})"
        )

        if weight_entry_mode == "Manual Override":
            log_message += f" - Reason: {override_reason}"
            frappe.logger().info(log_message)

    except Exception as e:
        frappe.db.rollback()
        frappe.logger().error(f"Failed to create weight entry: {str(e)}")
        frappe.throw(_("Failed to create weight entry: {0}").format(str(e)))

    return weight_item.as_dict()
```

---

## Additional Security Recommendations

### 1. Implement Rate Limiting Globally

```python
# scrap_metal_suite/utils/rate_limiter.py

import frappe
from frappe.utils import now_datetime, add_to_date

def check_rate_limit(key, max_attempts, window_minutes):
    """Generic rate limiter

    Args:
        key: Unique key (e.g., f"api:{user}:{method}")
        max_attempts: Maximum attempts allowed
        window_minutes: Time window in minutes

    Returns:
        bool: True if within limit, raises exception if exceeded
    """
    cache_key = f"rate_limit:{key}"
    attempts = frappe.cache().get(cache_key) or []

    # Remove old attempts
    cutoff_time = add_to_date(now_datetime(), minutes=-window_minutes)
    recent_attempts = [a for a in attempts if a > cutoff_time]

    if len(recent_attempts) >= max_attempts:
        frappe.throw(
            _("Rate limit exceeded. Please try again later."),
            frappe.RateLimitExceededError
        )

    # Record this attempt
    recent_attempts.append(now_datetime())
    frappe.cache().set(cache_key, recent_attempts, expires_in_sec=window_minutes * 60)

    return True
```

### 2. Create Custom Permission Checker

```python
# scrap_metal_suite/utils/permissions.py

import frappe

def require_role(*roles):
    """Decorator to require specific roles

    Usage:
        @frappe.whitelist()
        @require_role("System Manager", "POS Manager")
        def my_api():
            ...
    """
    def decorator(fn):
        def wrapper(*args, **kwargs):
            user_roles = frappe.get_roles()
            if not any(role in user_roles for role in roles):
                frappe.throw(
                    _("Insufficient permissions"),
                    frappe.PermissionError
                )
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def require_pos_session(fn):
    """Decorator to verify user has active POS session

    Usage:
        @frappe.whitelist()
        @require_pos_session
        def create_weight_entry(...):
            ...
    """
    def wrapper(*args, **kwargs):
        user = frappe.session.user
        active_session = frappe.db.exists("POS Session", {
            "user": user,
            "status": "Open"
        })

        if not active_session:
            frappe.throw(_("No active POS session found"))

        return fn(*args, **kwargs)
    return wrapper
```

### 3. Input Validation Utilities

```python
# scrap_metal_suite/utils/validators.py

import frappe
import re

def validate_positive_number(value, field_name, max_value=None):
    """Validate positive numeric input"""
    try:
        num = float(value)
    except (ValueError, TypeError):
        frappe.throw(_(f"{field_name} must be a number"))

    if num <= 0:
        frappe.throw(_(f"{field_name} must be greater than zero"))

    if max_value and num > max_value:
        frappe.throw(_(f"{field_name} exceeds maximum value of {max_value}"))

    return num


def validate_enum(value, field_name, allowed_values):
    """Validate value is in allowed list"""
    if value not in allowed_values:
        frappe.throw(
            _(f"Invalid {field_name}. Must be one of: {', '.join(allowed_values)}")
        )
    return value


def sanitize_user_input(text, max_length=500):
    """Sanitize and validate user text input"""
    if not isinstance(text, str):
        frappe.throw(_("Invalid text input"))

    # Remove dangerous characters
    from frappe.utils import sanitize_html
    text = sanitize_html(text.strip())

    # Check length
    if len(text) > max_length:
        frappe.throw(_(f"Text exceeds maximum length of {max_length} characters"))

    return text
```

### 4. Audit Logging System

```python
# scrap_metal_suite/utils/audit.py

import frappe

def log_security_event(event_type, description, user=None, severity="INFO"):
    """Log security-related events

    Args:
        event_type: Type of event (e.g., "UNAUTHORIZED_ACCESS", "RATE_LIMIT")
        description: Detailed description
        user: User involved (defaults to current user)
        severity: INFO, WARNING, ERROR, CRITICAL
    """
    user = user or frappe.session.user

    frappe.log_error(
        title=f"[SECURITY] {event_type}",
        message=f"""
Severity: {severity}
User: {user}
Timestamp: {frappe.utils.now()}
IP Address: {frappe.local.request_ip if hasattr(frappe.local, 'request_ip') else 'Unknown'}
User Agent: {frappe.request.headers.get('User-Agent', 'Unknown') if frappe.request else 'Unknown'}

Description:
{description}
        """
    )

    # Send alert for critical events
    if severity == "CRITICAL":
        send_security_alert(event_type, description, user)


def send_security_alert(event_type, description, user):
    """Send email alert for critical security events"""
    # Get system managers
    system_managers = frappe.get_all("User",
        filters={"role": "System Manager", "enabled": 1},
        fields=["email"])

    if system_managers:
        frappe.sendmail(
            recipients=[sm.email for sm in system_managers],
            subject=f"Security Alert: {event_type}",
            message=f"Critical security event detected:\n\n{description}\n\nUser: {user}\nTime: {frappe.utils.now()}"
        )
```

---

## Implementation Priority

### Phase 1: Critical Fixes (Deploy Immediately)
1. ✅ Fix `create_weight_entry()` - Add all security checks
2. ✅ Fix `get_scale_config()` - Add role authorization
3. ✅ Fix `save_scale_config()` - Add input validation

### Phase 2: High Priority (Deploy Within 1 Week)
4. ✅ Add rate limiting to `verify_weight_override_pin()`
5. ✅ Add audit logging to all APIs
6. ✅ Implement permission decorators
7. ✅ Add input validation utilities

### Phase 3: Medium Priority (Deploy Within 2 Weeks)
8. Create Security Audit Log DocType
9. Implement security monitoring dashboard
10. Add automated security testing

### Phase 4: Enhancements (Future)
11. Implement API usage analytics
12. Add machine learning anomaly detection
13. Implement advanced threat protection

---

## Testing Security Fixes

### Test Cases

1. **Authorization Testing**
   - [ ] Test API access with Supplier role (should fail)
   - [ ] Test API access with POS User role (should work for allowed APIs)
   - [ ] Test API access with System Manager role (should work for all)
   - [ ] Test API access without login (should fail)

2. **Input Validation Testing**
   - [ ] Test with negative weight values
   - [ ] Test with zero weight values
   - [ ] Test with extremely large values
   - [ ] Test with invalid data types
   - [ ] Test with SQL injection attempts
   - [ ] Test with XSS payloads in text fields

3. **User Impersonation Testing**
   - [ ] Try to create override with different user
   - [ ] Try to modify another session's data
   - [ ] Try to access another location's scale

4. **Rate Limiting Testing**
   - [ ] Verify PIN verification rate limit (5 attempts/15min)
   - [ ] Verify proper error messages
   - [ ] Verify rate limit resets after time window

5. **Audit Logging Testing**
   - [ ] Verify all security events are logged
   - [ ] Verify failed attempts are logged
   - [ ] Verify critical events trigger alerts

---

## Security Checklist for New APIs

When creating new `@frappe.whitelist()` APIs, ensure:

- [ ] **Authentication**: Requires user login
- [ ] **Authorization**: Explicit role/permission check
- [ ] **Input Validation**: All parameters validated
- [ ] **Type Safety**: Type checking and conversion
- [ ] **Range Validation**: Numeric values within expected range
- [ ] **Enum Validation**: String values from allowed list
- [ ] **XSS Prevention**: Text inputs sanitized
- [ ] **SQL Injection**: Using Frappe ORM, not raw SQL
- [ ] **Session Validation**: Verify data ownership
- [ ] **Rate Limiting**: Prevent abuse
- [ ] **Audit Logging**: Security events logged
- [ ] **Error Handling**: Graceful error messages (no stack traces)
- [ ] **Transaction Safety**: Rollback on error
- [ ] **Documentation**: Security requirements documented

---

## Conclusion

The current Scale Integration APIs have **multiple critical security vulnerabilities** that must be addressed before production deployment:

**Critical Issues:**
1. `create_weight_entry()` - No authorization, allows user impersonation
2. `get_scale_config()` - No authorization, information disclosure
3. `save_scale_config()` - No input validation, potential data corruption

**Recommended Action:**
- Implement all Phase 1 fixes immediately
- Add comprehensive security testing
- Deploy fixes to development environment first
- Conduct security audit before production

**Risk Assessment:**
- **Current State**: HIGH RISK - Vulnerabilities allow data manipulation and impersonation
- **After Phase 1 Fixes**: MEDIUM RISK - Basic security in place, needs monitoring
- **After Phase 2 Fixes**: LOW RISK - Comprehensive security controls

---

**Document Version**: 1.0
**Last Updated**: 2025-12-17
**Next Review**: After Phase 1 implementation
