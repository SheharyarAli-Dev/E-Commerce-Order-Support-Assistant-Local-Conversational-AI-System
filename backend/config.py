"""
Configuration settings for the ShopBot backend.
All tuneable parameters are centralized here.
"""

import os
from pathlib import Path

# ── Paths ────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"

PRODUCTS_FILE = DATA_DIR / "products.json"
ORDERS_FILE   = DATA_DIR / "orders.json"
POLICY_FILE   = DATA_DIR / "policy.md"

# ── Ollama / LLM ─────────────────────────────────────────────────────────────
OLLAMA_HOST  = os.getenv("OLLAMA_HOST", "http://localhost:11434")
MODEL_NAME   = os.getenv("SHOPBOT_MODEL", "qwen2.5:1.5b")

# Generation parameters
TEMPERATURE  = float(os.getenv("SHOPBOT_TEMPERATURE", "0.3"))
TOP_P        = float(os.getenv("SHOPBOT_TOP_P", "0.9"))
MAX_TOKENS   = int(os.getenv("SHOPBOT_MAX_TOKENS", "512"))

# ── Context window management ─────────────────────────────────────────────────
# Approximate token budget for conversation history (system prompt takes ~500)
MAX_HISTORY_TOKENS = int(os.getenv("SHOPBOT_MAX_HISTORY_TOKENS", "1800"))
# Always keep at least this many recent turns regardless of token budget
MIN_HISTORY_TURNS  = int(os.getenv("SHOPBOT_MIN_HISTORY_TURNS", "2"))

# ── Session ───────────────────────────────────────────────────────────────────
# Session timeout in seconds (30 minutes of inactivity)
SESSION_TIMEOUT_SECONDS = int(os.getenv("SHOPBOT_SESSION_TIMEOUT", "1800"))

# ── Server ───────────────────────────────────────────────────────────────────
ALLOWED_ORIGINS = ["*"]   # tighten in production
