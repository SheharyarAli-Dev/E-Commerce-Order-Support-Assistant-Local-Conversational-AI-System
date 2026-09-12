"""
scripts/seed_data_check.py — Validate the mock data JSON files.

Run with: python scripts/seed_data_check.py
Verifies schema completeness and prints a summary of the loaded data.
"""

import json
import sys
import os
from pathlib import Path

# Force UTF-8 output on Windows
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

ROOT = Path(__file__).parent.parent
PRODUCTS_FILE = ROOT / "data" / "products.json"
ORDERS_FILE   = ROOT / "data" / "orders.json"
POLICY_FILE   = ROOT / "data" / "policy.md"

REQUIRED_PRODUCT_FIELDS = {"sku", "name", "category", "price", "stock"}
REQUIRED_ORDER_FIELDS   = {"order_id", "customer_name", "order_date", "status", "items", "total"}

errors = []

# ── Products ──────────────────────────────────────────────────────────────────
print("Checking products.json …")
try:
    products = json.loads(PRODUCTS_FILE.read_text(encoding="utf-8"))
    print(f"  Loaded {len(products)} products")
    for p in products:
        missing = REQUIRED_PRODUCT_FIELDS - set(p.keys())
        if missing:
            errors.append(f"Product {p.get('sku','?')}: missing fields {missing}")
    categories = {p["category"] for p in products}
    print(f"  Categories: {sorted(categories)}")
    skus = [p["sku"] for p in products]
    print(f"  SKUs: {skus}")
except Exception as e:
    errors.append(f"products.json load error: {e}")

# ── Orders ────────────────────────────────────────────────────────────────────
print("\nChecking orders.json …")
try:
    orders = json.loads(ORDERS_FILE.read_text(encoding="utf-8"))
    print(f"  Loaded {len(orders)} orders")
    for o in orders:
        missing = REQUIRED_ORDER_FIELDS - set(o.keys())
        if missing:
            errors.append(f"Order {o.get('order_id','?')}: missing fields {missing}")
    statuses = {o["status"] for o in orders}
    print(f"  Statuses present: {sorted(statuses)}")
    order_ids = [o["order_id"] for o in orders]
    print(f"  Order IDs: {order_ids}")
except Exception as e:
    errors.append(f"orders.json load error: {e}")

# ── Policy ────────────────────────────────────────────────────────────────────
print("\nChecking policy.md …")
try:
    policy = POLICY_FILE.read_text(encoding="utf-8")
    print(f"  Loaded policy document ({len(policy)} chars)")
    for section in ["Return Policy", "Refund Policy", "Exchange Policy", "Shipping Policy"]:
        if section in policy:
            print(f"  ✓ {section} section found")
        else:
            errors.append(f"policy.md: missing section '{section}'")
except Exception as e:
    errors.append(f"policy.md load error: {e}")

# ── Result ────────────────────────────────────────────────────────────────────
print()
if errors:
    print(f"ERRORS ({len(errors)}):")
    for e in errors:
        print(f"  ✗ {e}")
    sys.exit(1)
else:
    print("All data files validated successfully ✓")
