"""
manager.py — The ConversationManager: orchestrates intent triage, data lookup,
prompt construction, and (via llm_engine) streaming inference.

This is the central coordinator called by the FastAPI WebSocket handler.
"""

from typing import AsyncIterator, Optional

from backend.conversation_manager.session import Session
from backend.conversation_manager.intent_triage import (
    detect_intent,
    is_topic_switch,
    get_policy_keywords_for_query,
)
from backend.conversation_manager.prompt_builder import build_messages
from backend.conversation_manager.domain_policy import (
    OUT_OF_SCOPE_REDIRECT,
    OUT_OF_SCOPE_REDIRECT_FOLLOWUP,
    CLOSING_RESPONSE,
    ORDER_NOT_FOUND,
    NO_ORDER_ID,
    PRODUCT_NOT_FOUND,
)
from backend import data_lookup


class ConversationManager:
    """
    Stateless orchestrator — all state is stored in the Session object.

    Usage:
        cm = ConversationManager()
        async for token in cm.handle_turn(session, user_message):
            yield token
    """

    def __init__(self, llm_engine):
        """
        Args:
            llm_engine: An instance of LLMEngine (from backend.llm_engine)
                        providing an async streaming generate() method.
        """
        self.llm = llm_engine

    async def handle_turn(
        self,
        session: Session,
        user_message: str,
    ) -> AsyncIterator[str]:
        """
        Process one user turn.  Yields response tokens as they arrive from the LLM.

        Workflow:
          1. Detect intent from user message
          2. Check for topic switch vs. previous intent
          3. Perform data lookups based on intent (no LLM involved)
          4. Check for canned response cases (out-of-scope, no order ID, etc.)
          5. Build the full prompt (system + context data + history + user msg)
          6. Stream the LLM response token by token
          7. Record completed turn in session history
        """
        # ── 1. Intent detection ────────────────────────────────────────────
        intent = detect_intent(user_message, session.active_intent)
        switched = is_topic_switch(intent, session.active_intent)

        # Update session intent (but not for out-of-scope / closing)
        if intent not in ("OUT_OF_SCOPE", "CLOSING"):
            session.active_intent = intent

        # ── 2. Handle CLOSING ─────────────────────────────────────────────
        if intent == "CLOSING":
            reply = CLOSING_RESPONSE
            session.add_turn("user", user_message)
            session.add_turn("assistant", reply)
            yield reply
            return

        # ── 3. Handle OUT_OF_SCOPE ────────────────────────────────────────
        if intent == "OUT_OF_SCOPE":
            # Use a slightly different message for repeat out-of-scope queries
            prior_oos = sum(
                1 for t in session.history
                if t.role == "assistant" and "I'm ShopBot" in t.content
            )
            reply = OUT_OF_SCOPE_REDIRECT if prior_oos == 0 else OUT_OF_SCOPE_REDIRECT_FOLLOWUP
            session.add_turn("user", user_message)
            session.add_turn("assistant", reply)
            yield reply
            return

        # ── 4. Data lookup based on intent ────────────────────────────────
        injected_product_info = ""
        injected_order_info   = ""
        injected_policy_info  = ""

        if intent == "ORDER_TRACKING":
            order_id = (
                data_lookup.extract_order_id(user_message)
                or session.last_order_id
            )
            if not order_id:
                # Ask for the order ID — don't call the LLM
                reply = NO_ORDER_ID
                session.add_turn("user", user_message)
                session.add_turn("assistant", reply)
                yield reply
                return

            order = data_lookup.get_order_by_id(order_id)
            if not order:
                reply = ORDER_NOT_FOUND
                session.add_turn("user", user_message)
                session.add_turn("assistant", reply)
                yield reply
                return

            session.last_order_id = order_id
            injected_order_info   = data_lookup.format_order_context(order)

        elif intent == "PRODUCT_QUERY":
            # Try to find products relevant to the query
            products = data_lookup.search_products(user_message, max_results=3)

            # If topic switched away from order, also keep order context if available
            if not products and session.last_sku:
                p = data_lookup.get_product_by_sku(session.last_sku)
                products = [p] if p else []

            if products:
                session.last_sku = products[0]["sku"]
                injected_product_info = data_lookup.format_product_context(products)
            else:
                # No product match — return canned response
                reply = PRODUCT_NOT_FOUND
                session.add_turn("user", user_message)
                session.add_turn("assistant", reply)
                yield reply
                return

        elif intent == "RETURNS_POLICY":
            # Extract policy topic keywords and inject relevant section
            kws = get_policy_keywords_for_query(user_message)
            injected_policy_info = data_lookup.get_policy_excerpt(kws, max_chars=1500)

            # Also inject order context if there's an order in play (for return eligibility)
            if session.last_order_id:
                order = data_lookup.get_order_by_id(session.last_order_id)
                if order:
                    injected_order_info = data_lookup.format_order_context(order)

        # ── 5. Build prompt messages ───────────────────────────────────────
        messages = build_messages(
            history               = session.history,
            user_message          = user_message,
            intent                = intent,
            injected_product_info = injected_product_info,
            injected_order_info   = injected_order_info,
            injected_policy_info  = injected_policy_info,
        )

        # ── 6. Stream LLM response ────────────────────────────────────────
        # Add user turn to history before streaming starts
        session.add_turn("user", user_message)

        full_reply = ""
        async for token in self.llm.stream(messages):
            full_reply += token
            yield token

        # ── 7. Record assistant reply in history ──────────────────────────
        session.add_turn("assistant", full_reply)
