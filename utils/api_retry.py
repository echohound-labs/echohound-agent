"""
utils/api_retry.py — Anthropic API retry with exponential backoff + jitter
Ported from Claude Code source (withRetry.ts)
"""
import asyncio
import logging
import random
from typing import Optional
import anthropic
from anthropic import APIConnectionError, APIStatusError

logger = logging.getLogger("echohound.retry")

BASE_DELAY_MS       = 500
MAX_DELAY_MS        = 32_000
DEFAULT_MAX_RETRIES = 10
MAX_529_RETRIES     = 3
JITTER_FACTOR       = 0.25


def _get_retry_delay(attempt: int, retry_after_header: Optional[str] = None) -> float:
    if retry_after_header:
        try:
            return float(retry_after_header)
        except (ValueError, TypeError):
            pass
    base   = min(BASE_DELAY_MS * (2 ** (attempt - 1)), MAX_DELAY_MS)
    jitter = random.random() * JITTER_FACTOR * base
    return (base + jitter) / 1000


def _is_529(error: Exception) -> bool:
    if isinstance(error, APIStatusError):
        if error.status_code == 529:
            return True
        if hasattr(error, 'message') and '"type":"overloaded_error"' in str(error.message):
            return True
    if '"type":"overloaded_error"' in str(error):
        return True
    return False


def _is_retryable(error: Exception) -> bool:
    if _is_529(error):
        return True
    if isinstance(error, APIConnectionError):
        return True
    if isinstance(error, APIStatusError):
        return error.status_code in (408, 409, 429, 500, 502, 503, 529)
    return False


def _get_retry_after(error: Exception) -> Optional[str]:
    if isinstance(error, APIStatusError) and hasattr(error, 'response'):
        return error.response.headers.get("retry-after")
    return None


async def create_with_retry(
    client: anthropic.Anthropic,
    max_retries: int = DEFAULT_MAX_RETRIES,
    **kwargs
) -> anthropic.types.Message:
    consecutive_529 = 0
    last_error      = None

    for attempt in range(1, max_retries + 2):
        try:
            response = await asyncio.to_thread(client.messages.create, **kwargs)
            return response
        except anthropic.APIUserAbortError:
            raise
        except Exception as error:
            last_error = error

            if _is_529(error):
                consecutive_529 += 1
                if consecutive_529 >= MAX_529_RETRIES:
                    logger.error(f"[retry] API overloaded after {consecutive_529} consecutive 529s — giving up")
                    raise
            else:
                consecutive_529 = 0

            if not _is_retryable(error):
                logger.error(f"[retry] Non-retryable error: {type(error).__name__}: {error}")
                raise

            if attempt > max_retries:
                logger.error(f"[retry] Exhausted {max_retries} retries. Last error: {error}")
                raise

            retry_after = _get_retry_after(error)
            delay       = _get_retry_delay(attempt, retry_after)
            status      = getattr(error, 'status_code', '?')
            logger.warning(f"[retry] Attempt {attempt}/{max_retries} failed (HTTP {status}) — retrying in {delay:.1f}s")
            await asyncio.sleep(delay)

    raise last_error
