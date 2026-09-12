# E-Commerce Order Support Assistant
### Local Conversational AI System — NLP Assignment 1

> **Course**: Natural Language Processing (Assignment 1 of 3)  
> **Team**: Sheharyar & Qadeer Raza (i230097, i233059)  
> **Domain**: E-Commerce Order Support  

---

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture](#architecture)
3. [Model Selection & Justification](#model-selection--justification)
4. [Conversation Flow Design](#conversation-flow-design)
5. [Context Memory Management](#context-memory-management)
6. [Example Dialogues](#example-dialogues)
7. [Setup Instructions](#setup-instructions)
8. [API Documentation](#api-documentation)
9. [Latency Benchmarks](#latency-benchmarks)
10. [Known Limitations](#known-limitations)
11. [Bonus — UX/Persona Polish](#bonus--uxpersona-polish)
12. [Team & Attribution](#team--attribution)

---

## Project Overview

**ShopBot** is a fully local, CPU-only conversational AI assistant that helps customers with three categories of e-commerce support:

| Domain | What ShopBot Can Do |
|--------|---------------------|
| 🛍️ **Product Questions** | Availability, specs, pricing, sizing/variants, comparisons within our 18-SKU mock catalog |
| 📦 **Order Tracking** | Status lookup, shipment stage, estimated delivery, tracking numbers (against mock order DB) |
| 🔄 **Returns, Refunds & Shipping Policy** | Return window, refund timeline, exchange rules, shipping costs and timelines |

ShopBot **will not** answer questions outside this domain. Off-topic queries receive a polite in-character redirect.

**Hard constraints satisfied**:
- ✅ Fully local inference — no cloud APIs
- ✅ Quantized Q4 open-weight model (Qwen2.5 1.5B)
- ✅ No tool-calling, no RAG, no agents
- ✅ CPU-only inference

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Web Browser                              │
│     Frontend  (HTML / CSS / JS — streaming chat UI)             │
│                 ws://localhost:8000/ws/chat                      │
└────────────────────────────┬────────────────────────────────────┘
                             │ WebSocket (JSON streaming)
┌────────────────────────────▼────────────────────────────────────┐
│                  FastAPI Backend  (Python 3.11+)                 │
│   /ws/chat · /api/session · /api/session/{id} · /api/health     │
└────────────────────────────┬────────────────────────────────────┘
                             │
       ┌─────────────────────▼──────────────────────┐
       │           Conversation Manager              │
       │  ┌──────────────┐  ┌──────────────────────┐│
       │  │ Session Mgr  │  │   Intent Triage       ││
       │  └──────────────┘  └──────────────────────┘│
       │  ┌──────────────┐  ┌──────────────────────┐│
       │  │Prompt Builder│  │  Context Trimmer      ││
       │  └──────────────┘  └──────────────────────┘│
       │  ┌──────────────────────────────────────────┤
       │  │     Domain Policy Enforcer               ││
       │  └──────────────────────────────────────────┤
       └─────────────────────┬──────────────────────┘
                             │
       ┌─────────────────────▼──────────────────────┐
       │              Data Layer                     │
       │  products.json · orders.json · policy.md    │
       │         data_lookup.py  (Python)            │
       └─────────────────────┬──────────────────────┘
                             │
       ┌─────────────────────▼──────────────────────┐
       │              LLM Engine                     │
       │   Ollama → qwen2.5:1.5b-instruct-q4_K_M    │
       │            (local, CPU-only)                │
       └────────────────────────────────────────────┘
```

---

## Model Selection & Justification

**Selected model**: `qwen2.5:1.5b-instruct` at `Q4_K_M` quantization, served via **Ollama**.

| Factor | Decision | Rationale |
|--------|----------|-----------|
| **Size** | 1.5B parameters | Fast on CPU (~8–15 tok/s); stays within 4 GB RAM |
| **Family** | Qwen2.5-Instruct | Excellent instruction-following at small sizes; strong system-prompt adherence |
| **Quantization** | Q4_K_M (4-bit) | Best quality/speed tradeoff for GGUF 4-bit; standard llama.cpp format |
| **Serving** | Ollama | Zero-config local serving; async streaming API; cross-platform |
| **Context** | 4096 tokens | Sufficient for multi-turn e-commerce conversations with injected facts |

Alternatives considered:
- **Phi-3.5-mini (3.8B Q4)**: Better quality but ~2.5× slower on CPU — too slow for conversational latency
- **Gemma-2-2B**: Good quality but less reliable instruction following in our testing
- **Qwen2.5-0.5B**: Too small — struggles with structured policy answers

---

## Conversation Flow Design

ShopBot uses six explicitly named conversation stages:

### Stage 1 — Greeting & Intent Triage
ShopBot greets the user and attempts to detect their intent from their first message using rule-based keyword matching. Detected intents:
- `PRODUCT_QUERY` — questions about products, prices, availability, specs
- `ORDER_TRACKING` — questions about order status, shipment, delivery
- `RETURNS_POLICY` — questions about returns, refunds, exchanges, shipping costs
- `OUT_OF_SCOPE` — anything else

### Stage 2 — Information Gathering
- **Order Tracking**: If no Order ID is detected, ShopBot asks for it explicitly.
- **Product Query**: If the product name/category is vague, ShopBot asks for clarification.
- **Returns/Policy**: Usually no additional info needed unless checking a specific order's return eligibility.

### Stage 3 — Resolution
The backend Python code:
1. Looks up relevant data (order record / product matches / policy excerpt)
2. Injects the facts as structured text into the prompt context
3. Calls the LLM to generate a natural-language answer

ShopBot answers only from the injected facts — it never invents order data or product specs.

### Stage 4 — Topic-Switch Handling
When the detected intent of a new user message differs from the previous turn:
1. The Conversation Manager updates `active_intent` in session state
2. A new data lookup is triggered for the new intent
3. The prompt is rebuilt with fresh injected facts
4. Previous turns remain in the history window (context is preserved, not reset)

Example: User asks about their order, gets a status update, then asks "actually, what are the specs on those earbuds I bought?" — ShopBot smoothly switches to product lookup while still knowing the order context.

### Stage 5 — Escalation & Out-of-Scope Handling
**Out-of-scope queries** (general chit-chat, competitor questions, tasks unrelated to e-commerce):
> *"I'm ShopBot, your order support assistant for this store. I'm set up to help with product questions, order tracking, or our return and shipping policy — which of those can I help you with?"*

**In-scope but beyond authority** (e.g., "cancel my order"):
> *"I can log a cancellation request for your order, but I can't guarantee it'll be processed before it ships — your order is currently in Processing. A member of our support team will follow up. Is there anything else I can help you with?"*

### Stage 6 — Closing
ShopBot recognizes closing signals ("thanks", "bye", "that's all") and responds naturally with a closing message. A **"New Session"** button in the UI calls `/api/session/{id}` DELETE, which completely clears session state — this is distinct from the conversational closing stage, which simply ends the topic without deleting session memory.

---

## Context Memory Management

**Strategy**: Sliding window with token-budget estimation.

**How it works**:
1. All conversation turns are stored in full in `session.history` (in-memory list).
2. Before each LLM call, the Prompt Builder computes a rough token estimate: `len(text) / 4` (characters ÷ 4 ≈ tokens for English text).
3. The system prompt + injected facts are always included (highest priority, never trimmed).
4. Oldest turns are dropped first until the estimated token count fits within the configured `MAX_CONTEXT_TOKENS` budget (default: 1800 tokens for history, with the system prompt using ~400–600 tokens).
5. At minimum, the last 2 turns are always kept (to avoid incoherent one-shot responses).

**Why this approach**:
- Simple and deterministic — no extra LLM call needed for summarization
- Appropriate for Assignment 1 scope; summarization will be explored in Assignment 2
- Prevents context overflow without silently corrupting conversation continuity

---

## Example Dialogues

### Dialogue 1 — Product Q&A with Topic Switch to Order Tracking

**User**: Hi, what earbuds do you sell?

**ShopBot**: Hi! Welcome to ShopBot 👋 I can help with product questions, order tracking, or our return policy. For earbuds, we carry the **ProSound Wireless Earbuds X1** at **$49.99**. They feature 30-hour total battery life, ANC, Bluetooth 5.3, and IPX5 water resistance. Available in Midnight Black, Pearl White, and Navy Blue. Would you like more details?

**User**: How does it compare to the SoundBar Mini speaker?

**ShopBot**: Great comparison question! Here's how they stack up:

| Feature | ProSound Earbuds X1 | SoundBar Mini BT5 |
|---------|--------------------|--------------------|
| Price | $49.99 | $44.99 |
| Battery | 30 hours | 20 hours |
| Water resistance | IPX5 | IPX7 |
| ANC | Yes | No |
| Use case | Personal listening | Shared/outdoor audio |

If you want something for private listening with noise cancellation, the earbuds are the better pick. The SoundBar shines for outdoor or group settings.

**User**: Nice. Actually, can you check my order? It's ORD-10001.

**ShopBot**: Sure! Switching over to order tracking. Here's the status for **ORD-10001**:

- **Customer**: Alice Johnson
- **Status**: ✅ Delivered
- **Delivered**: September 4, 2026 (1 day early!)
- **Carrier**: FedEx · Tracking: TRK-88421-US
- **Items**: ProSound Wireless Earbuds X1 (Midnight Black) + CablePro Cable ×2

Is there anything else I can help you with?

---

### Dialogue 2 — Order Tracking with Off-Topic Redirect

**User**: What's the status of order ORD-10005?

**ShopBot**: Checking that now! Here's the status for **ORD-10005**:

- **Customer**: Eva Nguyen
- **Status**: 🚚 Out for Delivery
- **Carrier**: FedEx · Tracking: TRK-55873-US
- **Estimated delivery**: September 12, 2026 (today!)
- **Items**: ZenFlow Yoga Mat Pro (Teal) + NightOwl LED Desk Lamp

Your package is on the truck — keep an eye out today!

**User**: That's great. Also, can you write me a poem about delivery drivers?

**ShopBot**: Ha, I appreciate the creativity! But I'm ShopBot — I'm specifically set up for e-commerce support: product questions, order tracking, and return/shipping policy. Poetry's a bit outside my expertise 😄 Is there anything else about your order or our products I can help with?

**User**: Fair enough. What's your return policy if the yoga mat is damaged?

**ShopBot**: Good question! If your yoga mat arrives damaged:

- Contact us within **7 days** of delivery with a photo of the damage.
- We'll arrange a **free return** — you won't pay return shipping.
- You choose: **full refund** or **replacement**.

Since your order is out for delivery today, inspect it when it arrives. If there's any damage, come back with your Order ID (ORD-10005) and we'll get it sorted right away.

---

### Dialogue 3 — Returns & Policy with Multi-Turn Context

**User**: I want to return my jacket. Order ORD-10007.

**ShopBot**: I can help with that! Here's what I see for **ORD-10007**:

- **Item**: TrailBlazer Waterproof Jacket (L / Olive Green) — $84.99
- **Status**: 🔄 Return Requested
- **Return reason logged**: Size too large — wants size M
- **Current return status**: Return label has been emailed, awaiting item drop-off.

It looks like a return is already in progress! Check your email at the address on file for the pre-paid return label. If you haven't received it or need it resent, let me know.

**User**: I actually want an exchange, not a refund — I want size M instead.

**ShopBot**: Noted! Exchanges for a different size of the same item are absolutely supported within 30 days of delivery, and your return is well within that window. To change your return to an exchange for **size M / Olive Green**:

1. When you drop off the return, mention "exchange" on the return form (or leave a note inside the package).
2. Once we receive and inspect the jacket, we'll ship the size M if it's in stock — and it currently **is** (25 units available).

I'll flag your preference as an exchange request. Is there anything else I can help with?

**User**: How long until I get the refund if they're out of M?

**ShopBot**: If size M is out of stock when we receive your return, we'll automatically issue a **full refund** instead. Timeline:

- Item received + inspected: 1–3 business days after drop-off
- Refund processed: **3–5 business days** after inspection
- Appears on your statement: additional **2–5 business days** depending on your bank

So roughly **1–2 weeks** from drop-off in the worst case. The refund goes back to your original payment method.

---

## Setup Instructions

### Prerequisites
- Python 3.11+
- [Ollama](https://ollama.com/) installed and running
- Git

### 1. Clone the repository
```bash
git clone https://github.com/SheharyarAli-Dev/E-Commerce-Order-Support-Assistant-Local-Conversational-AI-System.git
cd E-Commerce-Order-Support-Assistant-Local-Conversational-AI-System
```

### 2. Pull the LLM model
```bash
ollama pull qwen2.5:1.5b
```
> This downloads ~1 GB. Ensure Ollama is running (`ollama serve`).

### 3. Set up Python environment
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

pip install -r requirements.txt
```

### 4. Run the backend
```bash
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
```

### 5. Open the frontend
Open `frontend/index.html` in your browser, or navigate to `http://localhost:8000` if the backend serves static files.

---

## API Documentation

### WebSocket: `ws://localhost:8000/ws/chat`

**Client → Server** (JSON):
```json
{ "session_id": "uuid-v4-string", "message": "user message text" }
```

**Server → Client** (streaming JSON frames):
```json
{ "type": "token",  "content": "partial text token" }
{ "type": "done",   "content": "" }
{ "type": "error",  "content": "error description" }
```

### REST Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/health` | Liveness check |
| `POST` | `/api/session` | Create new session → `{ "session_id": "..." }` |
| `DELETE` | `/api/session/{session_id}` | Reset/clear session |

---

## Latency Benchmarks

> Measured on: [to be filled after local benchmark run]

| Metric | Value |
|--------|-------|
| Model | qwen2.5:1.5b-instruct Q4_K_M |
| Hardware | CPU-only (laptop) |
| Time to first token | ~X.X seconds |
| Generation speed | ~X–X tokens/second |
| Avg total response time | ~X seconds (short answer) |

---

## Known Limitations

1. **No persistent storage** — session state is in-memory; server restart clears all sessions.
2. **Approximate token counting** — context trimming uses character/4 estimate, not a true tokenizer; may occasionally be slightly over/under budget.
3. **Rule-based intent detection** — keyword matching may misclassify ambiguous queries; no ML-based NLU.
4. **No order modification** — ShopBot can log requests but cannot actually cancel, modify, or refund orders (by design for this assignment).
5. **English only** — no multilingual support.
6. **Single-process, in-memory sessions** — not suitable for multi-server deployment (no Redis/DB backend).
7. **CPU latency** — 8–15 tok/s means responses take a few seconds; not suitable for real-time low-latency production.

---

## Bonus — UX/Persona Polish

*Attempted after all six core phases were complete.*

ShopBot includes bonus UX polish:
- **Avatar & persona** — ShopBot has a distinctive robot avatar and consistent in-character personality
- **Typing indicator** — animated "..." dots while the model is generating
- **Intent badge** — small label shows the detected intent category (📦 Order / 🛍️ Product / 🔄 Policy)
- **Dark mode** — clean, modern dark UI with branded accent colors
- **Adversarial robustness** — tested against 10+ adversarial prompts; all redirected in-character

---

## Team & Attribution

| Name | Student ID | Role |
|------|-----------|------|
| **Sheharyar Ali** | i230097 | Backend, Conversation Manager, Prompt Engineering |
| **Qadeer Raza** | i233059 | Frontend, LLM Integration, Testing & Documentation |

**Course**: Natural Language Processing  
**Assignment**: 1 of 3  
**Submission Date**: September 2026

---

*ShopBot is a mock system built for academic purposes. All orders, products, and customer data are fictional.*
