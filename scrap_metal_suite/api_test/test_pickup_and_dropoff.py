# Both directions of the weighbridge — collections must work, deliveries must not change.
# Run with: bench --site smt.local execute scrap_metal_suite.api_test.test_pickup_and_dropoff.run
#
# The sale side reuses Truck Weight, the terminal and the print formats, so the
# risk is not that collections fail loudly — it is that deliveries fail quietly.
# Every delivery assertion here exists to catch that.
#
# Standalone: creates its own data and rolls everything back.

import frappe
from frappe.utils import flt, now_datetime


def _assert(condition, detail=None):
	if not condition:
		raise AssertionError(detail if detail is not None else "assertion failed")


class Results:
	def __init__(self):
		self.passed, self.failed = 0, []

	def check(self, name, fn):
		try:
			fn()
			self.passed += 1
			print("  PASS  %s" % name)
		except AssertionError as e:
			self.failed.append((name, str(e)))
			print("  FAIL  %s -> %s" % (name, str(e)[:120]))
		except Exception as e:
			self.failed.append((name, "%s: %s" % (type(e).__name__, e)))
			print("  ERR   %s -> %s: %s" % (name, type(e).__name__, str(e)[:120]))


def run():
	from scrap_metal_suite.api.v1.dropoff import (
		get_dropoff_details,
		get_dropoff_verification,
		record_truck_weight,
		save_weight_photo,
	)
	from scrap_metal_suite.api.v1.pickup import complete_pickup, record_pickup_weight
	from scrap_metal_suite.api.v1.weighbridge import get_visit_flow, lookup_visit

	r = Results()
	customer = frappe.get_all("Customer", limit=1)
	item = frappe.get_all("Item", filters={"item_group": "Processed Products"}, limit=1)
	dropoffs = frappe.get_all(
		"Dropoff", filters={"status": ["in", ["Scheduled", "In Progress"]]},
		order_by="creation desc", limit=1,
	)
	if not (customer and item and dropoffs):
		print("  SKIPPED: needs a Customer, a Processed Products item and an open Dropoff")
		return {"passed": 0, "failed": 0, "skipped": True}

	CUST, ITEM, DO = customer[0].name, item[0].name, dropoffs[0].name

	def pickup(plate="TEST-PU", qty=8000):
		return frappe.get_doc({
			"doctype": "Pickup", "customer": CUST, "license_plate": plate,
			"items": [{"item_code": ITEM, "qty": qty, "uom": "Kg"}],
		}).insert(ignore_permissions=True).name

	# ------------------------------------------------------------------ delivery
	print("\n=== DELIVERY SIDE (must be untouched) ===")

	r.check("details load", lambda: _assert("truck_weights" in get_dropoff_details(DO)))
	r.check("gross records", lambda: _assert(
		flt(record_truck_weight(dropoff=DO, weight_type="gross", weight=21000)["gross_weight"]) == 21000))
	r.check("tare records", lambda: _assert(
		flt(record_truck_weight(dropoff=DO, weight_type="tare", weight=13000)["tare_weight"]) == 13000))
	r.check("verification works", lambda: _assert("gross_weight" in get_dropoff_verification(DO)))
	r.check("weighings carry no pickup link", lambda: _assert(all(
		not t.pickup for t in frappe.get_all("Truck Weight", filters={"dropoff": DO}, fields=["pickup"]))))
	r.check("queue slip renders", lambda: _assert(
		len(frappe.get_print("Dropoff", DO, "ใบคิวสองภาษา")) > 500))

	# ---------------------------------------------------------------- collection
	print("\n=== COLLECTION SIDE ===")
	P = pickup()

	def order_enforced():
		try:
			record_pickup_weight(P, "gross", 20000)
			raise AssertionError("gross accepted before tare")
		except frappe.ValidationError:
			pass

	r.check("gross before tare refused", order_enforced)

	def weighs():
		record_pickup_weight(P, "tare", 12000)
		res = record_pickup_weight(P, "gross", 20050)
		_assert(flt(res["net_weight"]) == 8050, res)
		_assert(res["verification_status"] == "Verified", res)

	r.check("weighs in then out", weighs)

	def lighter_out():
		try:
			record_pickup_weight(P, "gross", 5000, reweight_reason="x")
			raise AssertionError("accepted a truck lighter on the way out")
		except frappe.ValidationError:
			pass

	r.check("truck lighter on exit refused", lighter_out)

	r.check("weighings carry no dropoff link", lambda: _assert(all(
		not t.dropoff for t in frappe.get_all("Truck Weight", filters={"pickup": P}, fields=["dropoff"]))))
	r.check("completes", lambda: _assert(complete_pickup(P)["status"] == "Completed"))

	def variance():
		q = pickup("TEST-VAR", qty=10000)
		record_pickup_weight(q, "tare", 12000)
		res = record_pickup_weight(q, "gross", 23000)  # 11,000 against 10,000 agreed
		_assert(res["verification_status"] == "Needs Review", res)

	r.check("variance beyond tolerance flags", variance)

	def no_items():
		q = frappe.get_doc({"doctype": "Pickup", "customer": CUST}).insert(ignore_permissions=True).name
		record_pickup_weight(q, "tare", 12000)
		_assert(record_pickup_weight(q, "gross", 20000)["verification_status"] == "Pending")

	r.check("nothing agreed does not divide by zero", no_items)

	def reweigh():
		q = pickup("TEST-RW")
		record_pickup_weight(q, "tare", 12000)
		res = record_pickup_weight(q, "tare", 12100, reweight_reason="ชั่งซ้ำ")
		_assert(res["is_reweight"] and flt(res["tare_weight"]) == 12100, res)
		_assert(frappe.db.count("Truck Weight", {"pickup": q}) == 1, "reweigh duplicated the row")

	r.check("reweigh updates rather than duplicates", reweigh)

	def incomplete():
		q = pickup("TEST-INC")
		record_pickup_weight(q, "tare", 12000)
		try:
			complete_pickup(q)
			raise AssertionError("completed with a weighing missing")
		except frappe.ValidationError:
			pass

	r.check("cannot complete half-weighed", incomplete)

	def photo():
		q = pickup("TEST-PH")
		tw = record_pickup_weight(q, "tare", 12000)["truck_weight_record"]
		# exactly what the terminal sends for a collection: no dropoff
		save_weight_photo(parent_doctype="Truck Weight", parent_doc=tw,
		                  photo_url="/private/files/t.jpg", weight_type="Truck Tare")
		rows = frappe.get_all("Weight Photo", filters={"parent": tw}, fields=["dropoff"])
		_assert(rows and not rows[0].dropoff, "collection photo got a dropoff link")

	r.check("photo saves on a collection weighing", photo)

	def photo_bad_link():
		q = pickup("TEST-PHB")
		tw = record_pickup_weight(q, "tare", 12000)["truck_weight_record"]
		try:
			save_weight_photo(parent_doctype="Truck Weight", parent_doc=tw,
			                  photo_url="/private/files/t.jpg", dropoff=q)
			raise AssertionError("a Pickup name was accepted as a photo's dropoff")
		except AssertionError:
			raise
		except Exception:
			pass  # link validation rejects it, which is why the terminal omits it

	r.check("pickup name rejected as a photo dropoff", photo_bad_link)

	# -------------------------------------------------------------------- shared
	print("\n=== SHARED ===")

	def orphan():
		try:
			frappe.get_doc({"doctype": "Truck Weight", "weight_type": "Gross",
			                "weight": 100, "weighed_at": now_datetime()}).insert(ignore_permissions=True)
			raise AssertionError("a weighing with no parent was accepted")
		except frappe.ValidationError:
			pass

	r.check("weighing with neither parent refused", orphan)

	def both_parents():
		try:
			frappe.get_doc({"doctype": "Truck Weight", "dropoff": DO, "pickup": P,
			                "weight_type": "Gross", "weight": 100,
			                "weighed_at": now_datetime()}).insert(ignore_permissions=True)
			raise AssertionError("a weighing with both parents was accepted")
		except frappe.ValidationError:
			pass

	r.check("weighing with both parents refused", both_parents)

	def mirrored():
		d, p = get_visit_flow("Dropoff"), get_visit_flow("Pickup")
		_assert(d["first_weight"] == "gross" and d["second_weight"] == "tare", d)
		_assert(p["first_weight"] == "tare" and p["second_weight"] == "gross", p)

	r.check("flows are mirror images", mirrored)

	def shared_plate():
		plate = frappe.db.get_value("Dropoff", {"license_plate": ["!=", ""]}, "license_plate")
		if not plate:
			return
		pickup(plate)
		_assert({x["doctype"] for x in lookup_visit(plate)} == {"Dropoff", "Pickup"},
		        "a shared plate must return both sides for the operator to choose")

	r.check("shared plate returns both sides", shared_plate)

	def slips():
		q = pickup("TEST-SL")
		tw = record_pickup_weight(q, "tare", 12000)["truck_weight_record"]
		hp = frappe.get_print("Truck Weight", tw, "Truck Weight Thermal")
		_assert("ลูกค้า" in hp and "Pickup" in hp, "collection slip shows delivery wording")
		td = frappe.get_all("Truck Weight", filters={"dropoff": ["!=", ""]}, limit=1)[0].name
		hd = frappe.get_print("Truck Weight", td, "Truck Weight Thermal")
		_assert("ผู้ขาย" in hd and "Drop-off" in hd, "delivery slip changed")

	r.check("truck slip correct on both sides", slips)

	def gate_ticket():
		q = pickup("TEST-GT")
		record_pickup_weight(q, "tare", 12000)
		record_pickup_weight(q, "gross", 20000)
		html = frappe.get_print("Pickup", q, "ใบชั่งน้ำหนักขาออก")
		_assert("ใบชั่งน้ำหนักขาออก" in html and "8,000" in html, "gate ticket wrong")

	r.check("gate ticket renders", gate_ticket)

	print("\n  %d passed, %d failed" % (r.passed, len(r.failed)))
	for name, err in r.failed:
		print("   FAILED: %s -> %s" % (name, err[:140]))

	# Nothing here is meant to survive.
	frappe.db.rollback()
	return {"passed": r.passed, "failed": len(r.failed)}
