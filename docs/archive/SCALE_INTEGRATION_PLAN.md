# Scale Integration Implementation Plan

## Overview
Integrate WebSerial API-based weight reader into POS system with auto-scale and manual override capabilities.

## Current System Analysis

### Existing DocTypes
1. **Scale** - Physical scale configuration (fixtures: SCALE-001, SCALE-002, TRUCK-001, TRUCK-002)
2. **POS Authority Code** - User PIN system (already has `can_override_rate` permission)
3. **Scrap Weight** - Weighing transaction record
4. **Scrap Weight Item** - Individual item weights in a transaction
5. **POS Order** - Order management
6. **POS Session** - Session tracking with scale assignment

### Key Finding
- **POS Authority Code** already exists with PIN system
- Need to add `can_override_weight` permission
- Weight entry mode and override tracking should be at **Scrap Weight Item** level (not POS Order)

## Implementation Plan

### Phase 1: Data Model Updates

#### 1.1 Update POS Authority Code DocType
**File**: `scrap_metal_suite/doctype/pos_authority_code/pos_authority_code.json`

Add new permission field:
```json
{
  "fieldname": "can_override_weight",
  "fieldtype": "Check",
  "label": "Can Override Weight (Manual Entry)",
  "default": "0",
  "description": "Allow manual weight entry instead of using scale"
}
```

#### 1.2 Update Scrap Weight Item DocType
**File**: `scrap_metal_suite/doctype/scrap_weight_item/scrap_weight_item.json`

Add new fields:
```json
{
  "fieldname": "weight_entry_mode",
  "fieldtype": "Select",
  "label": "Weight Entry Mode",
  "options": "Auto Scale\nManual Override",
  "default": "Auto Scale",
  "read_only": 1
},
{
  "fieldname": "manual_override_by",
  "fieldtype": "Link",
  "label": "Manual Override By",
  "options": "User",
  "read_only": 1,
  "depends_on": "eval:doc.weight_entry_mode=='Manual Override'"
},
{
  "fieldname": "manual_override_time",
  "fieldtype": "Datetime",
  "label": "Manual Override Time",
  "read_only": 1,
  "depends_on": "eval:doc.weight_entry_mode=='Manual Override'"
},
{
  "fieldname": "manual_override_reason",
  "fieldtype": "Small Text",
  "label": "Manual Override Reason",
  "depends_on": "eval:doc.weight_entry_mode=='Manual Override'"
}
```

#### 1.3 Add Scale Configuration to Scale DocType
**File**: `scrap_metal_suite/doctype/scale/scale.json`

Add WebSerial configuration fields:
```json
{
  "fieldname": "section_break_webserial",
  "fieldtype": "Section Break",
  "label": "WebSerial Configuration",
  "collapsible": 1
},
{
  "fieldname": "baud_rate",
  "fieldtype": "Int",
  "label": "Baud Rate",
  "default": 1200
},
{
  "fieldname": "data_bits",
  "fieldtype": "Select",
  "label": "Data Bits",
  "options": "7\n8",
  "default": "8"
},
{
  "fieldname": "parity",
  "fieldtype": "Select",
  "label": "Parity",
  "options": "none\neven\nodd",
  "default": "none"
},
{
  "fieldname": "stop_bits",
  "fieldtype": "Select",
  "label": "Stop Bits",
  "options": "1\n2",
  "default": "1"
},
{
  "fieldname": "column_break_webserial",
  "fieldtype": "Column Break"
},
{
  "fieldname": "flow_control",
  "fieldtype": "Select",
  "label": "Flow Control",
  "options": "none\nhardware",
  "default": "none"
},
{
  "fieldname": "buffer_size",
  "fieldtype": "Int",
  "label": "Buffer Size",
  "default": 255
},
{
  "fieldname": "delimiter",
  "fieldtype": "Select",
  "label": "Delimiter",
  "options": "lf\ncr\ncrlf\nfixed",
  "default": "lf"
},
{
  "fieldname": "fixed_length",
  "fieldtype": "Int",
  "label": "Fixed Length",
  "default": 17
}
```

### Phase 2: JavaScript Scale Reader Module

#### 2.1 Create Scale Reader Module
**File**: `scrap_metal_suite/public/js/scale_reader.js`

Core functionality:
- WebSerial API integration
- HP-05 scale protocol decoder
- Auto-detection of scale configuration
- Connection state management
- Stable weight detection
- Event emitter for weight updates

Key features from example:
- Port management (authorized ports list)
- Auto-detect configuration
- Frame extraction (LF/CR/CRLF/Fixed length)
- HP-05 specific decoding (17-byte frames starting with 0x82 0x28)
- Stability indicator
- Connection status tracking

#### 2.2 Create Translation-aware UI Components
**File**: `scrap_metal_suite/public/js/scale_ui.js`

Components:
- Connection status indicator
- Weight display with stability indicator
- Connection log viewer
- Manual override modal with PIN entry
- Permission-based "Configure Scale" button for POS

### Phase 3: Dedicated Scale Configuration Page (NEW DESIGN)

**Decision**: Separate scale configuration from POS operations for better security and UX.

#### 3.1 Create `/scale-config` Admin Page
**Location**: `www/scale-config/`
**Access**: System Managers and authorized administrators only

**Purpose**:
- Configure WebSerial settings for each scale
- Auto-detect scale configurations
- Test connections without affecting POS operations
- Troubleshoot scale connection issues

**Page Components**:
1. **Scale Selector**: Dropdown to select scale (SCALE-001, SCALE-002, etc.)
2. **Current Configuration Display**: Show saved settings from Scale DocType
3. **Auto-Detect Button**: Triggers WebSerial auto-detection process
4. **Test Connection Button**: Test current config with live data preview
5. **Connection Log**: Real-time log of detection/connection attempts
6. **Live Data Stream**: Shows raw scale data when connected
7. **Save Configuration Button**: Saves detected/manual config to Scale DocType

**UI Flow**:
```
Manager visits /scale-config
  ↓
Select scale from dropdown (e.g., SCALE-001)
  ↓
View current configuration (if any)
  ↓
Click "Auto-Detect Configuration"
  ↓
Browser prompts for serial port selection
  ↓
System tests multiple baud rates/configs (shows progress in log)
  ↓
Displays detected config + live weight readings
  ↓
Manager reviews and clicks "Save Configuration"
  ↓
Scale DocType updated with working configuration
  ↓
POS operators can now connect instantly using saved config
```

**Benefits of Dedicated Page**:
- ✅ Operators never see complex connection settings
- ✅ Configuration is one-time setup by admins
- ✅ Permission control (only admins access this page)
- ✅ Better testing/debugging environment
- ✅ Centralized config stored in database
- ✅ Can test without disrupting POS operations

#### 3.2 Simplified POS Integration
Location: POS interface

**UI Components in POS**:
1. **Connect to Scale** button - For operators to connect using saved config
2. **⚙️ Configure Scale** button (Manager/IT only) - Links to `/scale-config` page

**Permission-Based Button Display**:
```javascript
// Show "Configure Scale" button only for managers/IT
if (has_role("System Manager") || has_role("POS Manager")) {
    show_configure_scale_button();  // Links to /scale-config page
}
```

**POS UI Mockup**:
```
┌─────────────────────────────────────────────────────────┐
│  POS - Scrap Metal                    👤 Operator Name  │
├─────────────────────────────────────────────────────────┤
│  Session: POS-001  |  Scale: SCALE-001                  │
│                                                          │
│  Scale Status: ⚪ Disconnected                          │
│                                                          │
│  [🔗 Connect to Scale]  [⚙️ Configure Scale]   <-- Manager only
│                                                          │
│  ─────────────────────────────────────────────────────  │
│  ... (rest of POS interface)                            │
└─────────────────────────────────────────────────────────┘

Operator View (no "Configure Scale" button):
│  [🔗 Connect to Scale]                                  │

Manager View (shows both buttons):
│  [🔗 Connect to Scale]  [⚙️ Configure Scale]           │

When manager clicks "Configure Scale":
  → Opens /scale-config?scale=SCALE-001 in new tab
  → Manager runs auto-detect
  → Saves configuration
  → Closes tab and returns to POS
  → Clicks "Connect to Scale" → Works instantly
```

**Operator Connection Flow** (normal users):
1. POS loads → Gets assigned scale from POS Session
2. Click "Connect to Scale" button
3. System retrieves saved config via `get_scale_config` API
4. Auto-connects using saved configuration
5. Status indicator shows: Connected ✓

**Manager/IT Configuration Flow**:
1. Manager notices scale not working
2. Clicks "⚙️ Configure Scale" button in POS
3. Redirected to `/scale-config` page
4. Runs auto-detection
5. Saves working configuration
6. Returns to POS
7. Operators can now connect instantly

**Item Weighing Flow** (unchanged):
1. Select item to weigh
2. Modal shows live weight from scale
3. Wait for stable weight indicator
4. Click "Add to Basket"

**Manual Override Flow** (unchanged):
1. Click "Manual Override" button (if scale disconnected/broken)
2. Enter PIN
3. Enter weight manually + reason
4. System records override audit trail

**Connection Failure Handling**:
- **For Operators**: Show message "Scale connection failed. Please contact your manager."
- **For Managers/IT**: Show message "Scale connection failed. Click 'Configure Scale' to set up."

#### 3.3 Implementation Details for "Configure Scale" Button

**JavaScript Implementation in POS** (`pos_scrap.js`):
```javascript
// Check if user has permission to configure scales
function show_scale_config_button() {
    const user_roles = frappe.user_roles;
    const can_configure = user_roles.includes("System Manager") ||
                         user_roles.includes("POS Manager");

    if (can_configure) {
        // Add "Configure Scale" button next to "Connect to Scale"
        const config_button = `
            <button class="btn btn-sm btn-secondary" id="configure-scale-btn">
                <i class="fa fa-cog"></i> Configure Scale
            </button>
        `;

        $('#scale-buttons-container').append(config_button);

        // Button click handler
        $('#configure-scale-btn').on('click', function() {
            const scale_name = get_current_session_scale();  // From POS Session

            // Open scale config page in new tab with scale pre-selected
            window.open(`/scale-config?scale=${scale_name}`, '_blank');

            // Show tooltip
            frappe.show_alert({
                message: __("Opening scale configuration page..."),
                indicator: "blue"
            });
        });
    }
}

// Get scale assigned to current POS session
function get_current_session_scale() {
    // Assuming POS Session has a "scale" field
    return frappe.ui.form.get_value("POS Session", "scale") || "SCALE-001";
}
```

**Scale Config Page Pre-Selection** (`www/scale-config/index.py`):
```python
def get_context(context):
    """Get context for scale config page

    Supports URL parameter ?scale=SCALE-001 to pre-select scale
    """
    # Check permissions
    if "System Manager" not in frappe.get_roles() and \
       "POS Manager" not in frappe.get_roles():
        frappe.throw("Access Denied")

    # Get all scales
    context.scales = frappe.get_all("Scale",
        fields=["name", "scale_name", "location", "baud_rate",
                "data_bits", "parity", "stop_bits", "delimiter"],
        order_by="name")

    # Pre-select scale from URL parameter
    selected_scale = frappe.form_dict.get("scale")
    if selected_scale and frappe.db.exists("Scale", selected_scale):
        context.selected_scale = selected_scale

    context.active_page = "scale-config"
    return context
```

**Scale Config Page JavaScript** (`www/scale-config/scale_config.js`):
```javascript
// On page load, check if scale is pre-selected from URL
$(document).ready(function() {
    const urlParams = new URLSearchParams(window.location.search);
    const selectedScale = urlParams.get('scale');

    if (selectedScale) {
        // Pre-select the scale in dropdown
        $('#scale-selector').val(selectedScale);

        // Auto-load its configuration
        load_scale_config(selectedScale);

        // Highlight that this was the POS scale
        show_info_banner(`Configuring scale from POS: ${selectedScale}`);
    }
});

function show_info_banner(message) {
    const banner = `
        <div class="alert alert-info" role="alert">
            <i class="fa fa-info-circle"></i> ${message}
        </div>
    `;
    $('#info-banner-container').html(banner);
}
```

**Benefits of This Approach**:
1. ✅ Seamless workflow - Manager stays in context of POS problem
2. ✅ Scale auto-selected - No need to find which scale to configure
3. ✅ Opens in new tab - POS session remains open
4. ✅ Return flow is simple - Just close tab and reconnect

### Phase 4: API Endpoints

#### 4.1 PIN Verification API
**File**: `scrap_metal_suite/api/v1/__init__.py`

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

#### 4.2 Get Scale Configuration API
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

#### 4.3 Save Detected Configuration API (NEW)
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

#### 4.4 Create Weight Entry API
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

### Phase 5: Print Format Updates

#### 5.1 Update Thermal Receipt Print Format
**File**: Print format for Scrap Weight

Add override indicator:
```jinja2
{% for item in doc.items %}
  <div class="item-row">
    <div>{{ item.item_name }}</div>
    <div>{{ item.weight }} kg</div>
    {% if item.weight_entry_mode == "Manual Override" %}
      <div class="override-badge">
        ⚠️ Manual Override
        <small>By: {{ frappe.get_value("User", item.manual_override_by, "full_name") }}</small>
      </div>
    {% endif %}
  </div>
{% endfor %}
```

### Phase 6: Translation Support

#### 6.1 Add Scale-related Translations
**File**: `scrap_metal_suite/translations/th.csv`

```csv
# Scale Integration
"Connect to Scale","เชื่อมต่อเครื่องชั่ง",""
"Configure Scale","ตั้งค่าเครื่องชั่ง",""
"Opening scale configuration page...","กำลังเปิดหน้าตั้งค่าเครื่องชั่ง...",""
"Configuring scale from POS: {0}","กำลังตั้งค่าเครื่องชั่งจาก POS: {0}",""
"Disconnect","ตัดการเชื่อมต่อ",""
"Connected","เชื่อมต่อแล้ว",""
"Disconnected","ตัดการเชื่อมต่อ",""
"Connecting","กำลังเชื่อมต่อ",""
"Finding port...","กำลังค้นหาพอร์ต...",""
"Testing configuration...","กำลังทดสอบการตั้งค่า...",""
"Connected successfully!","เชื่อมต่อสำเร็จ!",""
"Connection failed","การเชื่อมต่อล้มเหลว",""
"Scale connection failed. Please contact your manager.","การเชื่อมต่อเครื่องชั่งล้มเหลว กรุณาติดต่อผู้จัดการ",""
"Scale connection failed. Click 'Configure Scale' to set up.","การเชื่อมต่อเครื่องชั่งล้มเหลว คลิก 'ตั้งค่าเครื่องชั่ง' เพื่อตั้งค่า",""
"Stable","เสถียร",""
"Weighing...","กำลังชั่ง...",""
"Weight is stable","น้ำหนักเสถียร",""
"Manual Override","ป้อนด้วยตนเอง",""
"Enter PIN","ใส่รหัส PIN",""
"Enter PIN to manually enter weight","ใส่รหัส PIN เพื่อป้อนน้ำหนักด้วยตนเอง",""
"Enter Weight Manually","ป้อนน้ำหนักด้วยตนเอง",""
"Override Reason","เหตุผลการป้อนด้วยตนเอง",""
"Auto Scale","ชั่งอัตโนมัติ",""
"Weight Entry Mode","โหมดการป้อนน้ำหนัก",""
"Manual Override By","ป้อนด้วยตนเองโดย",""
"Manual Override Time","เวลาป้อนด้วยตนเอง",""
"Manual Override Reason","เหตุผลการป้อนด้วยตนเอง",""
"Invalid PIN","รหัส PIN ไม่ถูกต้อง",""
"No permission for manual override","ไม่มีสิทธิ์ป้อนน้ำหนักด้วยตนเอง",""
"Request Port","ขอพอร์ต",""
"Auto-Detect Configuration","ตรวจหาการตั้งค่าอัตโนมัติ",""
"Previously Authorized Ports","พอร์ตที่ได้รับอนุญาตก่อนหน้า",""
"Scale connection log","บันทึกการเชื่อมต่อเครื่องชั่ง",""
```

## File Structure (Updated for Dedicated Config Page)

```
scrap_metal_suite/
├── api/v1/
│   └── __init__.py                          # Add: get_scale_config(), save_scale_config(),
│                                            #      verify_weight_override_pin()
├── doctype/
│   ├── scale/
│   │   └── scale.json                       # Add WebSerial config fields
│   ├── pos_authority_code/
│   │   └── pos_authority_code.json          # Add can_override_weight field
│   ├── scrap_weight_item/
│   │   └── scrap_weight_item.json           # Add weight entry mode fields
├── www/
│   └── scale-config/                        # NEW: Dedicated config page
│       ├── index.html                       # Scale configuration UI
│       ├── index.py                         # Context provider + permission check
│       └── scale_config.js                  # Auto-detect logic + UI handlers
├── public/
│   ├── js/
│   │   ├── scale_reader.js                  # NEW: WebSerial scale reader (shared)
│   │   ├── scale_ui.js                      # NEW: UI components (for POS)
│   │   └── pos_scrap.js                     # UPDATE: Integrate scale (simplified)
│   └── css/
│       ├── scale.css                        # NEW: Scale UI styles (for POS)
│       └── scale_config.css                 # NEW: Scale config page styles
├── translations/
│   └── th.csv                               # UPDATE: Add scale translations
└── print_format/
    └── scrap_weight/
        └── scrap_weight_thermal.html        # UPDATE: Add override indicator
```

## Testing Checklist

### Unit Tests
- [ ] PIN verification API with valid/invalid PINs
- [ ] PIN verification with permission check
- [ ] Scale configuration retrieval
- [ ] Weight entry creation (auto and manual modes)

### Integration Tests
- [ ] WebSerial connection to real scale
- [ ] Auto-detect configuration for HP-05 scale
- [ ] Stable weight detection
- [ ] Manual override flow end-to-end
- [ ] Print format shows override info correctly

### UI/UX Tests
- [ ] Connection button shows correct states
- [ ] Connection log displays messages in correct language
- [ ] Weight modal shows stable/unstable indicator
- [ ] Manual override button only shows when connected
- [ ] PIN entry validates and shows errors
- [ ] Manual weight entry saves correctly
- [ ] Translations work in Thai and English

### Permission Tests
- [ ] Users without `can_override_weight` cannot override
- [ ] Users with `can_override_weight` can override
- [ ] Invalid PINs are rejected
- [ ] Override tracking is recorded correctly

## Migration Steps

1. Backup database
2. Add new fields to doctypes (bench migrate)
3. Update fixtures with sample data
4. Deploy JavaScript modules
5. Update print formats
6. Update translations (bench build --app scrap_metal_suite)
7. Test with real hardware
8. Train operators

## Security Considerations

1. **PIN Storage**: Use Frappe's Password field (hashed storage)
2. **PIN Verification**: Server-side validation only
3. **Audit Trail**: All manual overrides logged with user, time, reason
4. **Permission Model**: Separate permission for weight override
5. **WebSerial Security**: Works only in HTTPS contexts (or localhost)

## Browser Compatibility

WebSerial API requires:
- Chrome 89+ or Edge 89+
- HTTPS connection (or localhost for development)
- User gesture to trigger port request

## Hardware Compatibility

Currently supports:
- HP-05 scale protocol (17-byte frames, 0x82 0x28 header)
- Serial/USB connection via WebSerial API
- Configurable baud rates, parity, stop bits

To support other scales:
- Add decoder functions in `scale_reader.js`
- Add scale type field to Scale doctype
- Implement protocol detection
