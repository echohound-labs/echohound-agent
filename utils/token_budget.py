"""
utils/token_budget.py — Natural language token budget parser
parse_token_budget("+500k")          → 500_000
parse_token_budget("use 2M tokens")  → 2_000_000
parse_token_budget("hey whats up")   → None
"""
import re
from typing import Optional, Tuple

_SHORTHAND_START = re.compile(r'^\s*\+(\d+(?:\.\d+)?)\s*(k|m|b)\b', re.IGNORECASE)
_SHORTHAND_END   = re.compile(r'\s\+(\d+(?:\.\d+)?)\s*(k|m|b)\s*[.!?]?\s*$', re.IGNORECASE)
_VERBOSE         = re.compile(r'\b(?:use|spend)\s+(\d+(?:\.\d+)?)\s*(k|m|b)\s*tokens?\b', re.IGNORECASE)
_MULTIPLIERS     = {'k': 1_000, 'm': 1_000_000, 'b': 1_000_000_000}


def _parse_match(value: str, suffix: str) -> int:
    return int(float(value) * _MULTIPLIERS[suffix.lower()])


def parse_token_budget(text: str) -> Optional[int]:
    m = _SHORTHAND_START.match(text)
    if m: return _parse_match(m.group(1), m.group(2))
    m = _SHORTHAND_END.search(text)
    if m: return _parse_match(m.group(1), m.group(2))
    m = _VERBOSE.search(text)
    if m: return _parse_match(m.group(1), m.group(2))
    return None


def format_token_budget(tokens: int) -> str:
    if tokens >= 1_000_000_000:
        v = tokens / 1_000_000_000
        return f"{v:.1f}B" if v != int(v) else f"{int(v)}B"
    if tokens >= 1_000_000:
        v = tokens / 1_000_000
        return f"{v:.1f}M" if v != int(v) else f"{int(v)}M"
    if tokens >= 1_000:
        v = tokens / 1_000
        return f"{v:.1f}k" if v != int(v) else f"{int(v)}k"
    return str(tokens)


def extract_budget_from_message(text: str) -> Tuple[Optional[int], str]:
    budget = parse_token_budget(text)
    if budget is None:
        return None, text
    cleaned = _SHORTHAND_START.sub('', text).strip()
    cleaned = _SHORTHAND_END.sub('', cleaned).strip()
    cleaned = _VERBOSE.sub('', cleaned).strip()
    return budget, cleaned
