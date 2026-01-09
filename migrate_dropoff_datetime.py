#!/usr/bin/env python
"""
Migrate dropoff.json: Replace date/time fields with datetime fields
"""
import json
import sys

def migrate_dropoff_json():
    """Update dropoff.json to use datetime fields instead of separate date/time"""

    file_path = 'scrap_metal_suite/scrap_metal_suite/doctype/dropoff/dropoff.json'

    # Read current JSON
    with open(file_path, 'r') as f:
        data = json.load(f)

    print("=== Before Migration ===")
    print(f"Total fields in field_order: {len(data['field_order'])}")
    print(f"Total field definitions: {len(data['fields'])}")

    # 1. Update field_order - remove old fields, add new ones
    new_field_order = []
    for field in data['field_order']:
        if field == 'dropoff_date':
            # Replace with new datetime fields
            new_field_order.append('dropoff_scheduled_start')
            new_field_order.append('dropoff_scheduled_end')
        elif field in ['dropoff_start_time', 'dropoff_end_time']:
            # Skip these - already replaced above
            pass
        else:
            new_field_order.append(field)

    data['field_order'] = new_field_order

    # 2. Remove old field definitions
    old_fieldnames = ['dropoff_date', 'dropoff_start_time', 'dropoff_end_time']
    data['fields'] = [f for f in data['fields'] if f.get('fieldname') not in old_fieldnames]

    # 3. Add new datetime field definitions
    # Find position to insert (after naming_series)
    naming_series_idx = next(i for i, f in enumerate(data['fields']) if f.get('fieldname') == 'naming_series')

    new_fields = [
        {
            "fieldname": "dropoff_scheduled_start",
            "fieldtype": "Datetime",
            "label": "Scheduled Start",
            "description": "When truck is expected to arrive",
            "reqd": 1,
            "in_list_view": 1,
            "in_standard_filter": 1,
            "default": "Now"
        },
        {
            "fieldname": "dropoff_scheduled_end",
            "fieldtype": "Datetime",
            "label": "Scheduled End",
            "description": "When drop-off should be complete",
            "depends_on": "eval:doc.dropoff_scheduled_start"
        }
    ]

    # Insert new fields after naming_series
    for i, new_field in enumerate(new_fields):
        data['fields'].insert(naming_series_idx + 1 + i, new_field)

    print("\n=== After Migration ===")
    print(f"Total fields in field_order: {len(data['field_order'])}")
    print(f"Total field definitions: {len(data['fields'])}")

    print("\n=== Changes ===")
    print("Removed fields:")
    print("  - dropoff_date (Date)")
    print("  - dropoff_start_time (Time)")
    print("  - dropoff_end_time (Time)")
    print("\nAdded fields:")
    print("  - dropoff_scheduled_start (Datetime)")
    print("  - dropoff_scheduled_end (Datetime)")

    # Write updated JSON
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=1)

    print(f"\n✅ Successfully updated {file_path}")
    print("Backup saved to: dropoff.json.backup")

    return True

if __name__ == '__main__':
    try:
        migrate_dropoff_json()
        sys.exit(0)
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
