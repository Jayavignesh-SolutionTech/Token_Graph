"""Offline token estimate.

Used for both sides of every with/without comparison, so ratios are fair even
though absolute counts differ a little from any one model's tokenizer.
"""

CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, round(len(text) / CHARS_PER_TOKEN))
