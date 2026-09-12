"""
data_lookup.py — Pure Python lookups against the mock data files.

The backend (Conversation Manager) calls these functions to retrieve relevant
facts before constructing the LLM prompt.  No LLM is involved here.
"""

import json
import re
from pathlib import Path
from typing import Optional

from backend.config import PRODUCTS_FILE, ORDERS_FILE, POLICY_FILE

# ── Load data at module import (once) ────────────────────────────────────────

def _load_json(path: Path) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def _load_text(path: Path) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()

_PRODUCTS: list[dict] = _load_json(PRODUCTS_FILE)
_ORDERS:   list[dict] = _load_json(ORDERS_FILE)
_POLICY:   str        = _load_text(POLICY_FILE)


# ── Order lookups ─────────────────────────────────────────────────────────────

def get_order_by_id(order_id: str) -> Optional[dict]:
    """Return the order dict for a given Order ID (case-insensitive), or None."""
    oid = order_id.strip().upper()
    for order in _ORDERS:
        if order["order_id"].upper() == oid:
            return order
    return None


def format_order_context(order: dict) -> str:
    """Convert an order dict into a concise text block for prompt injection."""
    items_text = "\n".join(
        f"  - {it['qty']}× {it['name']} ({it.get('variant','')}) @ ${it['price']:.2f}"
        for it in order["items"]
    )

    tracking_line = (
        f"Tracking: {order['tracking_number']} via {order['carrier']}"
        if order.get("tracking_number")
        else "Tracking: Not yet assigned (order still processing)"
    )

    delivery_line = (
        f"Delivered on: {order['actual_delivery']}"
        if order.get("actual_delivery")
        else f"Estimated delivery: {order.get('estimated_delivery', 'TBD')}"
    )

    return_block = ""
    if order.get("return_reason"):
        return_block = (
            f"\nReturn reason: {order['return_reason']}"
            f"\nReturn status: {order.get('return_status', 'Unknown')}"
        )

    return (
        f"Order ID: {order['order_id']}\n"
        f"Customer: {order['customer_name']}\n"
        f"Order date: {order['order_date']}\n"
        f"Status: {order['status']}\n"
        f"{tracking_line}\n"
        f"{delivery_line}\n"
        f"Shipping address: {order['shipping_address']}\n"
        f"Items ordered:\n{items_text}\n"
        f"Total: ${order['total']:.2f} ({order['payment_status']})"
        f"{return_block}"
    )


def extract_order_id(text: str) -> Optional[str]:
    """
    Extract an Order ID from user text.
    Accepts formats: ORD-10001, ord-10001, ORD10001, #10001
    """
    pattern = r'\b(?:ORD[-\s]?)?(\d{5})\b'
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return f"ORD-{match.group(1)}"
    return None


# ── Product lookups ───────────────────────────────────────────────────────────

def search_products(query: str, max_results: int = 3) -> list[dict]:
    """
    Return up to max_results products whose name, category, or description
    contains any word from the query (case-insensitive, simple keyword match).
    """
    query_words = set(re.findall(r'\w+', query.lower()))
    scored: list[tuple[int, dict]] = []

    for product in _PRODUCTS:
        haystack = (
            product["name"] + " " +
            product["category"] + " " +
            product.get("description", "")
        ).lower()
        score = sum(1 for w in query_words if w in haystack)
        if score > 0:
            scored.append((score, product))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in scored[:max_results]]


def get_product_by_sku(sku: str) -> Optional[dict]:
    """Return product by exact SKU."""
    sku = sku.strip().upper()
    for p in _PRODUCTS:
        if p["sku"].upper() == sku:
            return p
    return None


def format_product_context(products: list[dict]) -> str:
    """Convert a list of product dicts into prompt-injectable text."""
    if not products:
        return "No matching products found in the catalog."

    lines = []
    for p in products:
        variant_summary = _summarize_variants(p.get("variants", []))
        specs_summary   = _summarize_specs(p.get("specs", {}))
        lines.append(
            f"SKU: {p['sku']} | {p['name']}\n"
            f"  Category: {p['category']} | Price: ${p['price']:.2f} | "
            f"Total stock: {p['stock']} units\n"
            f"  Description: {p.get('description','')}\n"
            f"  Variants: {variant_summary}\n"
            f"  Specs: {specs_summary}"
        )
    return "\n\n".join(lines)


def _summarize_variants(variants: list[dict]) -> str:
    if not variants:
        return "N/A"
    parts = []
    for v in variants:
        attrs = {k: v for k, v in v.items() if k != "stock"}
        attrs_str = ", ".join(f"{k}={val}" for k, val in attrs.items())
        parts.append(f"{attrs_str} (stock: {v.get('stock', '?')})")
    return " | ".join(parts)


def _summarize_specs(specs: dict) -> str:
    if not specs:
        return "N/A"
    return ", ".join(f"{k}: {v}" for k, v in specs.items())


def get_all_categories() -> list[str]:
    """Return sorted list of unique product categories."""
    return sorted({p["category"] for p in _PRODUCTS})


def get_products_by_category(category: str) -> list[dict]:
    """Return all products in a given category (case-insensitive)."""
    return [p for p in _PRODUCTS if p["category"].lower() == category.lower()]


# ── Policy lookup ─────────────────────────────────────────────────────────────

def get_policy_text() -> str:
    """Return the full policy document text."""
    return _POLICY


def get_policy_excerpt(topic_keywords: list[str], max_chars: int = 1500) -> str:
    """
    Return the most relevant section(s) of the policy for given topic keywords.
    Falls back to the full policy if no specific section matched.
    """
    if not topic_keywords:
        return _POLICY[:max_chars]

    # Split policy into sections by markdown headers
    sections = re.split(r'\n(?=#{1,3} )', _POLICY)
    scored: list[tuple[int, str]] = []

    for section in sections:
        section_lower = section.lower()
        score = sum(1 for kw in topic_keywords if kw.lower() in section_lower)
        if score > 0:
            scored.append((score, section))

    scored.sort(key=lambda x: x[0], reverse=True)

    if not scored:
        return _POLICY[:max_chars]

    # Join top matching sections up to max_chars
    result = ""
    for _, section in scored:
        if len(result) + len(section) <= max_chars:
            result += section + "\n\n"
        else:
            break

    return result.strip() or _POLICY[:max_chars]
