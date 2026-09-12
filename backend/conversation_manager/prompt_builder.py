"""
prompt_builder.py — Assembles the full prompt for each LLM call.

The prompt structure is:
  [System prompt with hard rules]
  [Injected context data: order / product / policy facts]
  [Trimmed conversation history]
  [Current user message → LLM completes]

The Conversation Manager calls build_messages() which returns an Ollama-
compatible list of {role, content} dicts.
"""

from backend.conversation_manager.domain_policy import (
    SYSTEM_PROMPT_TEMPLATE,
    CONTEXT_SECTION_PRODUCT,
    CONTEXT_SECTION_ORDER,
    CONTEXT_SECTION_POLICY,
    CONTEXT_NO_DATA,
)
from backend.conversation_manager.context_trimmer import (
    trim_history,
    estimate_prompt_tokens,
    _estimate_tokens,
)


def build_messages(
    history: list,
    user_message: str,
    intent: str,
    injected_product_info: str = "",
    injected_order_info:   str = "",
    injected_policy_info:  str = "",
) -> list[dict]:
    """
    Assemble the full list of chat messages for the Ollama API.

    Args:
        history:               List of Turn objects (full session history).
        user_message:          The current user message (not yet in history).
        intent:                Detected intent label.
        injected_product_info: Pre-fetched product data string.
        injected_order_info:   Pre-fetched order data string.
        injected_policy_info:  Pre-fetched policy text string.

    Returns:
        A list of dicts: [{"role": "system"|"user"|"assistant", "content": "..."}]
    """
    # ── Build context data block ───────────────────────────────────────────
    context_parts = []

    if injected_product_info:
        context_parts.append(
            CONTEXT_SECTION_PRODUCT.format(product_info=injected_product_info)
        )
    if injected_order_info:
        context_parts.append(
            CONTEXT_SECTION_ORDER.format(order_info=injected_order_info)
        )
    if injected_policy_info:
        context_parts.append(
            CONTEXT_SECTION_POLICY.format(policy_info=injected_policy_info)
        )

    if not context_parts:
        context_data = CONTEXT_NO_DATA
    else:
        context_data = "\n".join(context_parts)

    system_content = SYSTEM_PROMPT_TEMPLATE.format(context_data=context_data)

    # ── Estimate reserved tokens (system prompt + injected facts) ─────────
    reserved = _estimate_tokens(system_content)

    # ── Trim history to fit within context budget ─────────────────────────
    trimmed = trim_history(history, reserved_tokens=reserved)

    # ── Assemble messages list ────────────────────────────────────────────
    messages: list[dict] = [{"role": "system", "content": system_content}]

    for turn in trimmed:
        messages.append({"role": turn.role, "content": turn.content})

    # Add the current user message last
    messages.append({"role": "user", "content": user_message})

    return messages


def build_canned_messages(system_content: str, user_message: str) -> list[dict]:
    """
    Build a minimal message list for canned/fallback responses that don't
    need injected data (e.g., out-of-scope redirects when serving from
    domain_policy directly without calling the LLM).
    """
    return [
        {"role": "system", "content": system_content},
        {"role": "user",   "content": user_message},
    ]
