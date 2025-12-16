# Thai Translation Guide for Scrap Metal Suite

## Overview

This guide explains how to translate both ERPNext core and your custom Scrap Metal Suite app into Thai, overriding the poor default ERPNext Thai translations.

## How Translation Works in Frappe/ERPNext

1. **Translation Priority** (highest to lowest):
   - Custom app translations (`scrap_metal_suite/translations/th.csv`)
   - ERPNext translations (`erpnext/translations/th.csv`)
   - Frappe translations (`frappe/translations/th.csv`)

2. **Your custom translations override everything**, so you can fix bad ERPNext translations!

## File Structure

```
scrap_metal_suite/
└── translations/
    └── th.csv          # All Thai translations
```

## Translation File Format

```csv
source,translation,context
"English text","ข้อความภาษาไทย",""
"Customer","ลูกค้า",""
```

- **source**: English text (must match exactly)
- **translation**: Thai translation
- **context**: Optional (leave empty or specify DocType name)

## Workflow

### 1. Find Untranslated Strings

```bash
# From bench directory
cd ~/frappe-bench

# Get all untranslated strings for your app
bench --site [your-site] get-untranslated th scrap_metal_suite

# Get untranslated from ERPNext too
bench --site [your-site] get-untranslated th erpnext
```

This outputs a CSV file with all untranslated strings.

### 2. Add Translations

Edit `scrap_metal_suite/translations/th.csv`:

```csv
source,translation,context
"Supplier Registration","ลงทะเบียนผู้ขาย",""
"Company Name","ชื่อบริษัท",""
"Tax ID","เลขประจำตัวผู้เสียภาษี",""
```

**Tips:**
- Keep translations natural, not literal
- Use proper Thai business terminology
- For technical terms, consider keeping English or use common Thai equivalents
- Add common ERPNext terms you want to override

### 3. Update Translations

```bash
# Import translations into database
bench --site [your-site] import-translations th scrap_metal_suite/translations/th.csv

# OR use the simpler command (recommended):
bench --site [your-site] build-translation-files scrap_metal_suite

# Clear cache to see changes
bench --site [your-site] clear-cache
```

### 4. Test

- Change language in User Settings to Thai
- Navigate through your app
- Check all labels, messages, and DocType fields
- Note any missing translations

## Override Bad ERPNext Translations

If ERPNext has bad translations, just add them to your `th.csv`:

```csv
source,translation,context
# Override ERPNext's poor translation of "Purchase Order"
"Purchase Order","ใบสั่งซื้อ",""

# Override incorrect "Sales Invoice" translation
"Sales Invoice","ใบแจ้งหนี้",""

# Fix "Item Code" translation
"Item Code","รหัสสินค้า",""
```

Your translations take priority!

## Common Thai Business Terms

| English | Thai | Notes |
|---------|------|-------|
| Supplier | ผู้ขาย | Vendor/seller |
| Customer | ลูกค้า | Client |
| Invoice | ใบแจ้งหนี้ | Bill |
| Receipt | ใบเสร็จรับเงิน | Payment receipt |
| Purchase Order | ใบสั่งซื้อ | PO |
| Sales Order | ใบสั่งขาย | SO |
| Quotation | ใบเสนอราคา | Quote |
| Item | สินค้า | Product |
| Price | ราคา | Cost/price |
| Quantity | จำนวน | Qty |
| Weight | น้ำหนัก | Mass |
| Tax | ภาษี | VAT/tax |
| Discount | ส่วนลด | Discount |
| Total | รวม | Sum/total |
| Submit | ส่ง | Submit/send |
| Approve | อนุมัติ | Approve |
| Reject | ปฏิเสธ | Deny/reject |

## Translating DocType Fields

DocType field labels are automatically translated from the CSV file.

Example - `Supplier Registration` DocType:

```json
// In supplier_registration_request.json
{
  "label": "Company Name",  // Will be translated to "ชื่อบริษัท"
  "fieldname": "company_name"
}
```

Just add to `th.csv`:
```csv
"Company Name","ชื่อบริษัท",""
```

## Translating Web Portal Pages

For portal HTML templates, use the translate function:

```html
<!-- supplier/index.html -->
<h1>{{ _("Dashboard") }}</h1>
<p>{{ _("Welcome to Supplier Portal") }}</p>
```

The `_()` function looks up translations from your CSV file.

## Translating JavaScript Messages

```javascript
// In your JS files
frappe.msgprint(__("Record saved successfully"));
frappe.throw(__("Invalid quantity"));
```

The `__()` function uses your translation file.

## Best Practices

1. **Start with high-traffic areas**
   - Login page, main dashboard, navigation
   - Most-used DocTypes (Customer, Supplier, Invoice)
   - Error messages

2. **Be consistent**
   - Use the same term for the same concept throughout
   - "Customer" should always be "ลูกค้า", not sometimes "คัสโตเมอร์"

3. **Context matters**
   - "Draft" in email = "ร่าง"
   - "Draft" in payment = "ดราฟท์" (banking term)
   - Use the context field if needed

4. **Test with real users**
   - Get feedback from Thai staff
   - Adjust translations based on their usage

5. **Keep technical terms in English sometimes**
   - "API", "URL", "ID" are often clearer in English
   - "Item Code" might be better as "รหัสสินค้า (Item Code)"

## Maintenance Commands

```bash
# Export current translations to file
bench --site [site] export-translations th scrap_metal_suite

# Import after editing
bench --site [site] import-translations th scrap_metal_suite/translations/th.csv

# Rebuild everything
bench --site [site] build-translation-files scrap_metal_suite
bench --site [site] clear-cache

# See translation coverage
bench --site [site] get-untranslated th scrap_metal_suite | wc -l
```

## Troubleshooting

### Translations not showing?

1. Clear cache: `bench clear-cache`
2. Check user language setting (User → Language → Thai)
3. Verify CSV format (UTF-8, no BOM)
4. Check for typos in source text (must match exactly)

### Partial translations?

- Check if text is dynamically generated
- Use `_()` or `__()` functions in code
- Add all variations to CSV

### ERPNext translations still showing?

- Your custom translations must have exact same source text
- Rebuild: `bench build-translation-files scrap_metal_suite`
- Clear cache after rebuild

## Quick Start Checklist

- [x] Create `scrap_metal_suite/translations/th.csv`
- [ ] Run `bench get-untranslated th scrap_metal_suite` to find strings
- [ ] Add translations to `th.csv` file
- [ ] Run `bench import-translations th scrap_metal_suite/translations/th.csv`
- [ ] Run `bench clear-cache`
- [ ] Change user language to Thai
- [ ] Test portal pages, DocTypes, messages
- [ ] Iterate and improve

## Resources

- [Frappe Translation Documentation](https://frappeframework.com/docs/user/en/translations)
- Thai business terminology: Use common terms from Thai accounting software
- Get help from Thai staff for natural phrasing

---

**Pro Tip**: Start by translating the 100 most common ERPNext terms that appear everywhere (Save, Submit, Cancel, Customer, Item, etc.). This will give you 80% coverage with 20% effort!
