# Plan: Universal Document Share System

## Goal
Create a generic document sharing system that allows users to generate shareable links for **configured documents** in Frappe. The shared link displays the document using Frappe's existing Print Format system.

## Key Features
- **Configurable DocTypes** - Settings page to enable/disable per DocType (like QR Foundry pattern)
- **Role-based permissions** - Only users with allowed roles can create share links
- **Configurable link duration** - Default expiry settings per DocType
- Button in Frappe Desk to generate share link (only for enabled DocTypes)
- Uses existing Print Formats for rendering
- Three access modes: Public / Password Protected / Login Required
- View tracking

---

## Architecture

```
+------------------------------------------------------------------+
|                   Document Share Settings                         |
|  +------------------------------------------------------------+  |
|  |  Enabled DocTypes:                                          |  |
|  |  +------------------------------------------------------+   |  |
|  |  | DocType        | Default Expiry | Roles Allowed      |   |  |
|  |  +------------------------------------------------------+   |  |
|  |  | Sales Invoice  | 30 days        | Sales Manager      |   |  |
|  |  | Purchase Order | 7 days         | Purchase User      |   |  |
|  |  | POS Order      | Never          | POS Operator       |   |  |
|  |  | Quotation      | 14 days        | Sales User         |   |  |
|  |  +------------------------------------------------------+   |  |
|  +------------------------------------------------------------+  |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                        FRAPPE DESK                                |
|  +------------------------------------------------------------+  |
|  |  Document Form (only if DocType is enabled)                 |  |
|  |                                                             |  |
|  |  [Print] [Email] [Share Link v]  <-- Button appears         |  |
|  |                    |                if user has role        |  |
|  |                    +-> Public Link                          |  |
|  |                    +-> Password Protected                   |  |
|  |                    +-> Login Required                       |  |
|  +------------------------------------------------------------+  |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                    Document Share Record                          |
|  +------------------------------------------------------------+  |
|  |  reference_doctype: "Sales Invoice"                         |  |
|  |  reference_name: "SINV-00001"                               |  |
|  |  share_token: "abc123xyz..."                                |  |
|  |  access_type: "Public" | "Password" | "Login"               |  |
|  |  print_format: "Standard" | "Custom Format"                 |  |
|  |  expires_at: datetime (from settings default)               |  |
|  +------------------------------------------------------------+  |
+------------------------------------------------------------------+
                              |
                              v
+------------------------------------------------------------------+
|                    Public View Page                               |
|                                                                   |
|  URL: /share/view?token=abc123xyz                                |
|                                                                   |
|  1. Validate token (exists, active, not expired)                 |
|  2. Check access (public/password/login)                          |
|  3. Render using Frappe get_print() with selected format         |
|  4. Display as HTML or offer PDF download                         |
+------------------------------------------------------------------+
```

---

## Components

### 1. DocType: Document Share Settings (Single)

Configuration for the entire share system.

| Field | Type | Description |
|-------|------|-------------|
| `enabled_doctypes` | Table: Document Share DocType | Which DocTypes can be shared |

### 2. DocType: Document Share DocType (Child Table)

Per-DocType configuration.

| Field | Type | Description |
|-------|------|-------------|
| `document_type` | Link: DocType | The DocType to enable |
| `default_expiry_days` | Int | Default link expiry (0 = never) |
| `allowed_roles` | Table MultiSelect | Roles that can create shares |
| `default_print_format` | Link: Print Format | Default format for this DocType |
| `allow_public` | Check | Allow public (no auth) shares |
| `allow_password` | Check | Allow password-protected shares |
| `allow_login` | Check | Allow login-required shares |

### 3. DocType: Document Share

Individual share link record.

| Field | Type | Description |
|-------|------|-------------|
| `reference_doctype` | Link: DocType | The DocType being shared |
| `reference_name` | Dynamic Link | The specific document |
| `share_token` | Data | Unique URL token (auto-generated) |
| `access_type` | Select | Public / Password / Login Required |
| `password` | Password | Hashed password (if password protected) |
| `print_format` | Link: Print Format | Which format to use |
| `letterhead` | Link: Letter Head | Optional letterhead |
| `expires_at` | Datetime | Expiration (from settings or custom) |
| `is_active` | Check | Enable/disable |
| `view_count` | Int | Times viewed |
| `last_viewed` | Datetime | Last view timestamp |
| `created_by` | Link: User | Who created |

### 4. API Endpoints (`api/v1/share.py`)

```python
@frappe.whitelist()
def get_share_settings(doctype):
    """Get share settings for a DocType (if enabled, user has role)"""
    # Returns: {enabled, allowed_access_types, default_expiry, print_formats}

@frappe.whitelist()
def create_share(doctype, docname, access_type, print_format=None,
                 password=None, expires_days=None):
    """Create a share link for a document"""
    # Validates: DocType enabled, user has role, access_type allowed

@frappe.whitelist()
def get_share_links(doctype, docname):
    """Get all active share links for a document"""

@frappe.whitelist()
def revoke_share(share_name):
    """Deactivate a share link"""

@frappe.whitelist(allow_guest=True)
def verify_access(token, password=None):
    """Verify access to shared document"""

@frappe.whitelist(allow_guest=True)
def get_document_html(token, password=None):
    """Get rendered document HTML for display"""

@frappe.whitelist(allow_guest=True)
def get_document_pdf(token, password=None):
    """Get document as PDF download"""
```

### 5. Public View Page (`/share/view`)

```
www/share/view.html  - Guest-accessible page
www/share/view.py    - Context handler
```

**Flow:**
1. Extract token from URL (`/share/view?token=xxx`)
2. Look up Document Share record
3. Validate: exists, is_active, not expired
4. Check access:
   - **Public**: Render immediately
   - **Password**: Show password form -> verify -> render
   - **Login**: Redirect to `/login?redirect-to=/share/view?token=xxx`
5. Render document using `frappe.get_print()`
6. Increment view count

### 6. Share Link Button (via Document Share DocType form)

**No custom client script needed.** The Document Share DocType form IS the share dialog.

**How it works:**

1. User opens a document (e.g., Sales Invoice SINV-00001)
2. User clicks Menu > Links > Document Share (or creates new from list)
3. Opens Document Share form with `reference_doctype` and `reference_name` pre-filled
4. User selects access type, print format, expiry
5. On save, token is auto-generated and share URL is displayed

**To create a share from any document:**
- Navigate to: `/app/document-share/new?reference_doctype=Sales%20Invoice&reference_name=SINV-00001`
- Or use the Links section in the document sidebar

### 7. Document Share Form Layout

The Document Share DocType form serves as the share UI:

```
+------------------------------------------------------------------+
| Document Share                                      [Save] [Menu] |
+------------------------------------------------------------------+
|                                                                   |
| Reference Document                                                |
| -----------------------------------------------------------------|
| DocType: [Sales Invoice v]     Document: [SINV-00001 v]          |
|                                                                   |
| Share Settings                                                    |
| -----------------------------------------------------------------|
| Access Type: [Public v]                                           |
|              ( ) Public - Anyone with link                        |
|              ( ) Password - Requires password                     |
|              ( ) Login - Requires user login                      |
|                                                                   |
| Password: [______________]  (visible only if Password selected)   |
|                                                                   |
| Print Format: [Standard v]                                        |
| Letterhead:   [Company Letterhead v]                              |
|                                                                   |
| Expires At: [2025-01-12 00:00]  (auto-set from settings default) |
|                                                                   |
| Share Link (read-only, shown after save)                          |
| -----------------------------------------------------------------|
| +-------------------------------------------------------------+  |
| | https://yoursite.com/share/view?token=abc123xyz789...  [copy]|  |
| +-------------------------------------------------------------+  |
|                                                                   |
| Statistics (read-only)                                            |
| -----------------------------------------------------------------|
| Status: [x] Active                                                |
| View Count: 5          Last Viewed: 2025-12-10 14:30              |
| Created By: admin      Created: 2025-12-01 10:00                  |
|                                                                   |
+------------------------------------------------------------------+
```

### 8. Viewing Existing Shares

From any document, users can see existing shares via:

1. **Links sidebar** - Shows linked Document Share records
2. **Document Share List** - Filter by `reference_doctype` and `reference_name`
3. **API** - `get_share_links(doctype, docname)` for programmatic access

### 9. Quick Share Button (Optional Enhancement)

For convenience, add a custom button to enabled DocTypes via `hooks.py`:

```python
# hooks.py
doctype_js = {
    "Sales Invoice": "public/js/share_button.js",
    "Purchase Order": "public/js/share_button.js",
    # ... other enabled doctypes
}
```

```javascript
// share_button.js - Simple redirect to new Document Share form
frappe.ui.form.on(cur_frm.doctype, {
    refresh: function(frm) {
        if (!frm.is_new()) {
            frm.add_custom_button(__('Share Link'), () => {
                frappe.set_route('Form', 'Document Share', 'new', {
                    reference_doctype: frm.doctype,
                    reference_name: frm.docname
                });
            }, __('Actions'));
        }
    }
});
```

This is optional - users can always create shares via the Document Share list or links sidebar.

---

## File Structure

```
scrap_metal_suite/
|-- scrap_metal_suite/doctype/
|   |-- document_share_settings/
|   |   |-- document_share_settings.json    # Single DocType (settings)
|   |   +-- document_share_settings.py
|   |
|   |-- document_share_doctype/
|   |   +-- document_share_doctype.json     # Child table for settings
|   |
|   +-- document_share/
|       |-- document_share.json             # Share record + form UI
|       +-- document_share.py               # Token generation, validation
|
|-- api/v1/
|   +-- share.py                            # Guest APIs for viewing
|
|-- www/share/
|   |-- view.html                           # Public view page
|   +-- view.py                             # View context
|
+-- public/css/
    +-- document_share.css                  # Share page styling
```

---

## Implementation Steps

### Step 1: Create Settings DocTypes
- `Document Share Settings` (Single) - Global config
- `Document Share DocType` (Child) - Per-DocType settings with roles, expiry, access types

### Step 2: Create Document Share DocType
- Form-based UI for creating/managing shares
- Fields: reference_doctype, reference_name, access_type, password, print_format, expires_at
- Read-only fields: share_token, share_url, view_count, last_viewed
- Auto-generate secure token on insert (`before_insert`)
- Hash password if provided
- Validate against settings (DocType enabled, user has role, access_type allowed)
- Set default expiry from settings
- Generate share URL field (computed)

### Step 3: Create Guest APIs (`api/v1/share.py`)
- `verify_access(token, password)` - Check token + password (guest)
- `get_document_html(token, password)` - Render document (guest)
- `get_document_pdf(token, password)` - Return PDF (guest)

### Step 4: Create Public View Page (`/share/view`)
- Guest-accessible
- Password form handling
- Login redirect handling
- PDF download option
- Clean, printable layout

### Step 5: Add Links Configuration
- Configure Document Share to appear in Links sidebar of enabled DocTypes
- This is done via the `links` property in Document Share DocType JSON

---

## Security

1. **Token**: 32-byte URL-safe random token (`secrets.token_urlsafe(32)`)
2. **Password**: Hashed with `werkzeug.security.generate_password_hash`
3. **Role Check**: User must have allowed role to create shares
4. **Access Type Control**: Admin controls which access types are allowed per DocType
5. **Expiration**: Configurable default, checked on every access
6. **Audit**: Track creator, views, last accessed
7. **Revocation**: Instant deactivation via `is_active` flag

---

## Example Configuration

### Document Share Settings

| DocType | Default Expiry | Allowed Roles | Access Types |
|---------|----------------|---------------|--------------|
| Sales Invoice | 30 days | Sales Manager, Accounts User | Public, Password, Login |
| Purchase Order | 7 days | Purchase Manager | Password, Login |
| POS Order | Never | POS Operator, System Manager | Public, Password |
| Quotation | 14 days | Sales User | Public, Password |
| Scrap Weight | 30 days | POS Operator | Public |

---

## Notes

- Document state (cancelled, revised, etc.) is handled by the source document - the share just renders whatever print format shows
- Print formats already handle field visibility, so no need to add field-level control here
- Multiple shares can exist for the same document (different access types, different users)
