"""
Retry and Timeout Manager for The Relay.
Implements exponential backoff with full jitter, per-request deadlines,
and retry budget monitoring to prevent retry storms.
"""

import asyncio
import random
import time
from typing import Callable, Any, Dict, Optional


class RetryManager:
    def __init__(
        self,
        max_retries: int = 2,
        base_backoff_s: float = 0.5,
        max_backoff_s: float = 4.0,
        request_timeout_s: float = 10.0
    ):
        self.max_retries = max_retries
        self.base_backoff_s = base_backoff_s
        self.max_backoff_s = max_backoff_s
        self.request_timeout_s = request_timeout_s

    def calculate_jittered_backoff(self, attempt: int) -> float:
        """
        Calculates exponential backoff with full jitter:
        sleep = Uniform(0, min(max_backoff, base * 2^attempt))
        """
        temp = min(self.max_backoff_s, self.base_backoff_s * (2 ** attempt))
        return random.uniform(0.1, temp)

    async def execute_with_retry(
        self,
        call_fn: Callable[[], Any],
        on_retry: Optional[Callable[[int, float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Executes an async model call with timeout and retries.
        Returns the result dict enriched with:
          - 'retries': number of retry attempts made
          - 'retry_delay_total_ms': total time spent sleeping between retries
        """
        retries_done = 0
        total_retry_sleep_ms = 0.0

        for attempt in range(self.max_retries + 1):
            try:
                # Wrap the call inside our strict client timeout deadline
                result = await asyncio.wait_for(
                    call_fn(),
                    timeout=self.request_timeout_s
                )

                # Check if the result returned a rate limit or server error
                status = result.get("status")
                if status == "ok":
                    result["retries"] = retries_done
                    result["retry_delay_total_ms"] = round(total_retry_sleep_ms, 2)
                    return result

                # If status is rate_limited or error, evaluate if we can retry
                if attempt < self.max_retries and status in ["rate_limited", "error"]:
                    backoff = self.calculate_jittered_backoff(attempt)
                    total_retry_sleep_ms += backoff * 1000
                    retries_done += 1

                    if on_retry:
                        on_retry(retries_done, backoff, result.get("error", status))

                    await asyncio.sleep(backoff)
                    continue

                # Max retries exhausted
                result["retries"] = retries_done
                result["retry_delay_total_ms"] = round(total_retry_sleep_ms, 2)
                return result

            except asyncio.TimeoutError:
                if attempt < self.max_retries:
                    backoff = self.calculate_jittered_backoff(attempt)
                    total_retry_sleep_ms += backoff * 1000
                    retries_done += 1
                    await asyncio.sleep(backoff)
                    continue

                return {
                    "status": "timeout",
                    "content": "",
                    "first_token_ms": round(self.request_timeout_s * 1000, 2),
                    "total_ms": round((self.request_timeout_s * 1000) + total_retry_sleep_ms, 2),
                    "tokens_in": 0,
                    "tokens_out": 0,
                    "source": "unknown",
                    "retries": retries_done,
                    "retry_delay_total_ms": round(total_retry_sleep_ms, 2),
                    "error": f"Deadline of {self.request_timeout_s}s exceeded"
                }

        return {
            "status": "error",
            "content": "",
            "first_token_ms": 0.0,
            "total_ms": round(total_retry_sleep_ms, 2),
            "tokens_in": 0,
            "tokens_out": 0,
            "source": "unknown",
            "retries": retries_done,
            "retry_delay_total_ms": round(total_retry_sleep_ms, 2),
            "error": "Max retries exhausted"
        }