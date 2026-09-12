"""
intent_triage.py — Rule-based intent detection.

Classifies user messages into one of four intents using keyword matching.
This runs entirely in Python — no LLM call is made here.

Intent labels:
  PRODUCT_QUERY   — product questions, availability, specs, pricing, comparisons
  ORDER_TRACKING  — order status, shipment stage, delivery, tracking numbers
  RETURNS_POLICY  — returns, refunds, exchanges, shipping policy, costs
  OUT_OF_SCOPE    — anything outside the e-commerce support domain
"""

import re
from typing import Optional

# ── Keyword dictionaries ──────────────────────────────────────────────────────

_ORDER_KEYWORDS = [
    r'\border\b', r'\btrack\b', r'\btracking\b', r'\bstatus\b',
    r'\bshipment\b', r'\bshipments\b', r'\bshipped\b', r'\bshipping status\b',
    r'\bdelivery\b', r'\bdeliver\b', r'\bdelivered\b', r'\bdispatch\b',
    r'\bwhere is\b', r'\bwhere.*my\b', r'\best.*delivery\b',
    r'\bpackage\b', r'\bparcel\b', r'\bcarrier\b', r'\bfedex\b',
    r'\bups\b', r'\busps\b', r'\btracking number\b', r'\bord-\d{5}\b',
    r'\bmy order\b', r'\border id\b', r'\border number\b',
    r'\bprocessing\b', r'\bout for delivery\b',
]

_PRODUCT_KEYWORDS = [
    r'\bproduct\b', r'\bproducts\b', r'\bitem\b', r'\bitems\b',
    r'\bprice\b', r'\bpricing\b', r'\bcost\b', r'\bhow much\b',
    r'\bavailable\b', r'\bavailability\b', r'\bin stock\b', r'\bstock\b',
    r'\bspec\b', r'\bspecs\b', r'\bspecifications?\b', r'\bfeature\b', r'\bfeatures\b',
    r'\bsize\b', r'\bsizes\b', r'\bvariant\b', r'\bvariants\b', r'\bcolor\b', r'\bcolors\b',
    r'\bcompare\b', r'\bcomparison\b', r'\bvs\b', r'\bversus\b',
    r'\bbuy\b', r'\bpurchase\b', r'\bget\b', r'\border\b',
    r'\bearbuds?\b', r'\bheadphones?\b', r'\bspeaker\b', r'\bcharger\b',
    r'\bwebcam\b', r'\btablet\b', r'\blaptop\b', r'\bphone\b',
    r'\bjacket\b', r'\bshirt\b', r'\bshorts\b', r'\bclothing\b', r'\bapparel\b',
    r'\byoga\b', r'\bmat\b', r'\bdumbbells?\b', r'\bweights?\b',
    r'\bpurifier\b', r'\blamp\b', r'\bdesk lamp\b', r'\bcoffee\b',
    r'\bsmart plug\b', r'\bwifi\b', r'\bbook\b', r'\bbooks\b',
    r'\bdo you (sell|have|carry|stock)\b',
    r'\bwhat.*sell\b', r'\bwhat.*carry\b', r'\bshow me\b', r'\btell me about\b',
]

_RETURNS_KEYWORDS = [
    r'\breturn\b', r'\breturns\b', r'\brefund\b', r'\brefunds\b',
    r'\bexchange\b', r'\bexchanges\b', r'\breplace\b', r'\breplacement\b',
    r'\bpolicy\b', r'\bpolicies\b', r'\bshipping cost\b', r'\bfree shipping\b',
    r'\bshipping fee\b', r'\bshipping time\b', r'\bshipping.*policy\b',
    r'\bhow long.*ship\b', r'\bhow.*return\b', r'\bcan i return\b',
    r'\breturn window\b', r'\b30 days?\b', r'\brefund process\b',
    r'\bget.*money back\b', r'\bmoney back\b', r'\bdamaged\b', r'\bdefective\b',
    r'\bwrong item\b', r'\bwrong size\b', r'\bdoesn.t fit\b',
    r'\bchange.*size\b', r'\bswap\b',
    r'\bhow much.*ship\b', r'\bovernight\b', r'\bexpedited\b',
]

_CLOSING_KEYWORDS = [
    r'\bthank you\b', r'\bthanks\b', r'\bthank\b', r'\bbye\b',
    r'\bgoodbye\b', r'\bsee you\b', r'\bthat.s all\b', r'\bthat was all\b',
    r'\bno more\b', r'\bnothing else\b', r'\ball good\b', r'\ball set\b',
    r'\bdone\b', r'\bgreat\b',
]


def _matches_any(text: str, patterns: list[str]) -> bool:
    lower = text.lower()
    return any(re.search(p, lower) for p in patterns)


def detect_intent(text: str, previous_intent: Optional[str] = None) -> str:
    """
    Detect the intent of a user message.

    Args:
        text: The raw user message.
        previous_intent: The active intent from the previous turn (for disambiguation).

    Returns:
        One of: PRODUCT_QUERY, ORDER_TRACKING, RETURNS_POLICY, OUT_OF_SCOPE, CLOSING
    """
    if not text or not text.strip():
        return previous_intent or "OUT_OF_SCOPE"

    # Score each category
    scores = {
        "ORDER_TRACKING": sum(1 for p in _ORDER_KEYWORDS if re.search(p, text, re.IGNORECASE)),
        "PRODUCT_QUERY":  sum(1 for p in _PRODUCT_KEYWORDS if re.search(p, text, re.IGNORECASE)),
        "RETURNS_POLICY": sum(1 for p in _RETURNS_KEYWORDS if re.search(p, text, re.IGNORECASE)),
    }

    # Check for closing signal
    if _matches_any(text, _CLOSING_KEYWORDS) and max(scores.values(), default=0) <= 1:
        return "CLOSING"

    # Require a minimum score to classify (avoids false positives on short texts)
    best_intent = max(scores, key=lambda k: scores[k])
    best_score  = scores[best_intent]

    if best_score == 0:
        # No e-commerce keywords detected — check if it could be a follow-up
        # (e.g., user just types an order ID number alone)
        if re.search(r'\bord[-\s]?\d{5}\b', text, re.IGNORECASE):
            return "ORDER_TRACKING"
        return "OUT_OF_SCOPE"

    # ORDER_TRACKING and PRODUCT_QUERY can overlap; ORDER wins if there's an Order ID
    if re.search(r'\bord[-\s]?\d{5}\b', text, re.IGNORECASE):
        return "ORDER_TRACKING"

    return best_intent


def is_topic_switch(new_intent: str, previous_intent: Optional[str]) -> bool:
    """
    Return True if the user has switched to a different intent category.
    CLOSING and OUT_OF_SCOPE do not count as topic switches from a previous
    in-domain intent.
    """
    if previous_intent is None:
        return False
    if new_intent in ("OUT_OF_SCOPE", "CLOSING"):
        return False
    return new_intent != previous_intent


def get_policy_keywords_for_query(text: str) -> list[str]:
    """Extract topic keywords from a policy-related query for focused policy lookup."""
    keyword_map = {
        "return":   ["return", "how to start a return"],
        "refund":   ["refund", "refund timeline"],
        "exchange": ["exchange"],
        "damage":   ["damaged", "defective"],
        "cancel":   ["cancel"],
        "ship":     ["shipping", "delivery"],
        "cost":     ["shipping cost", "free shipping"],
        "overnight":["overnight"],
        "expedite": ["expedited"],
        "international": ["international"],
        "track":    ["tracking"],
    }
    found = []
    lower = text.lower()
    for trigger, kws in keyword_map.items():
        if trigger in lower:
            found.extend(kws)
    return list(set(found)) if found else ["return", "refund", "shipping"]
