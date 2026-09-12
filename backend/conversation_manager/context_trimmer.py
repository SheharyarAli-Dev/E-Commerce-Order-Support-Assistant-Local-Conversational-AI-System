"""
context_trimmer.py — Conversation history trimming for context window management.

Strategy: Sliding window with token-budget estimation.
- Rough token estimate = len(text) / 4  (characters ÷ 4 ≈ English tokens)
- System prompt + injected facts are always kept (pre-deducted from budget)
- Oldest turns dropped first until history fits within MAX_HISTORY_TOKENS
- At least MIN_HISTORY_TURNS recent turns are always preserved
"""

from backend.config import MAX_HISTORY_TOKENS, MIN_HISTORY_TURNS


def _estimate_tokens(text: str) -> int:
    """Rough token count estimate: characters / 4."""
    return max(1, len(text) // 4)


def trim_history(
    history: list,
    reserved_tokens: int = 0,
) -> list:
    """
    Trim a list of Turn objects so that the total estimated token count of the
    remaining turns fits within (MAX_HISTORY_TOKENS - reserved_tokens).

    Args:
        history:         Full list of Turn objects (oldest first).
        reserved_tokens: Tokens already used by system prompt + injected facts.

    Returns:
        A (possibly shortened) list of Turn objects to include in the prompt.
    """
    budget = MAX_HISTORY_TOKENS - reserved_tokens
    if budget <= 0:
        # Nothing left — return only the minimum turns
        return history[-MIN_HISTORY_TURNS:] if len(history) >= MIN_HISTORY_TURNS else history[:]

    # Always keep at minimum the last MIN_HISTORY_TURNS turns
    must_keep = history[-MIN_HISTORY_TURNS:] if len(history) >= MIN_HISTORY_TURNS else history[:]
    must_keep_tokens = sum(_estimate_tokens(t.content) for t in must_keep)

    if must_keep_tokens >= budget:
        # Even the mandatory minimum is over budget — return it anyway
        # (the LLM will still handle it; we just can't trim further)
        return must_keep

    # Walk from oldest to newest, adding turns that fit in the remaining budget
    remaining_budget = budget - must_keep_tokens
    optional_turns   = history[:-MIN_HISTORY_TURNS] if len(history) > MIN_HISTORY_TURNS else []

    included_optional = []
    # Try from newest-optional toward oldest so we keep the most recent context
    for turn in reversed(optional_turns):
        cost = _estimate_tokens(turn.content)
        if cost <= remaining_budget:
            included_optional.insert(0, turn)
            remaining_budget -= cost
        # If a turn doesn't fit, skip it (we don't break — there may be shorter earlier turns)

    return included_optional + must_keep


def estimate_prompt_tokens(system_prompt: str, injected_facts: str, history: list) -> int:
    """Estimate total token count for a prompt assembly."""
    total = _estimate_tokens(system_prompt) + _estimate_tokens(injected_facts)
    total += sum(_estimate_tokens(t.content) for t in history)
    return total
