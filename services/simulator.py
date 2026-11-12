"""
Stand-in Simulated Model Service for The Relay.
Calibrated against real Groq measurements (850ms baseline TTFT, 150 tok/s).
Simulates latency spikes under concurrency, token streaming, 429 rate limits,
500 internal errors, and daily quota exhaustion.
"""

import asyncio
import time
import random
from typing import Dict, Any, Optional


class SimulatedModelService:
    def __init__(
        self,
        rpm_limit: int = 1000,
        daily_limit: int = 14400,
        error_rate: float = 0.02,  # 2% random 500 internal error rate under normal load
        timeout_threshold_s: float = 12.0
    ):
        # Calibrated limits from real Groq measurements
        self.rpm_limit = rpm_limit
        self.daily_limit = daily_limit
        self.daily_requests_used = 0
        self.error_rate = error_rate
        self.timeout_threshold_s = timeout_threshold_s

        # In-flight concurrency tracking (models hardware resource contention)
        self.in_flight_requests = 0
        self._lock = asyncio.Lock()

        # Sliding window for minute rate limit
        self.request_timestamps = []

    def _check_rate_limits(self) -> Optional[str]:
        """Checks both daily budget and per-minute sliding window."""
        now = time.time()
        
        # 1. Daily budget check
        if self.daily_requests_used >= self.daily_limit:
            return "429: Daily request quota exhausted"

        # 2. Per-minute sliding window check
        self.request_timestamps = [t for t in self.request_timestamps if now - t < 60.0]
        if len(self.request_timestamps) >= self.rpm_limit:
            return f"429: Rate limit exceeded ({self.rpm_limit} req/min limit)"

        self.request_timestamps.append(now)
        self.daily_requests_used += 1
        return None

    def _calculate_simulated_ttft(self) -> float:
        """
        Calculates TTFT based on real Groq baseline (~850ms) + concurrency penalty.
        - 1-2 concurrent: ~850ms - 1000ms
        - 3-5 concurrent: ~2000ms - 4000ms
        - >5 concurrent: ~6000ms - 10000ms
        """
        baseline_ttft = 0.85  # 850ms baseline from real Groq measurement
        jitter = random.uniform(-0.05, 0.1)

        if self.in_flight_requests <= 2:
            return max(0.4, baseline_ttft + jitter)
        elif self.in_flight_requests <= 5:
            # Latency swells under moderate queueing
            return baseline_ttft + (self.in_flight_requests * 0.6) + random.uniform(0.2, 0.8)
        else:
            # Severe saturation delay
            return min(11.0, 4.0 + (self.in_flight_requests * 0.9) + random.uniform(0.5, 2.0))

    async def call_streaming(
        self,
        prompt: str,
        system_prompt: str = "",
        simulated_tokens_out: int = 40,
        client_timeout_s: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Async streaming call matching the GroqService return schema.
        Simulates TTFT, token generation, streaming delays, and failure conditions.
        """
        start_time = time.perf_counter()

        # Rate limit check
        rate_error = self._check_rate_limits()
        if rate_error:
            end_time = time.perf_counter()
            elapsed_ms = round((end_time - start_time) * 1000, 2)
            return {
                "status": "rate_limited",
                "content": "",
                "first_token_ms": elapsed_ms,
                "total_ms": elapsed_ms,
                "tokens_in": len(prompt.split()) * 4 // 3,
                "tokens_out": 0,
                "source": "stand-in",
                "error": rate_error
            }

        async with self._lock:
            self.in_flight_requests += 1

        try:
            # Calculate dynamic TTFT
            simulated_ttft = self._calculate_simulated_ttft()

            # Check if this delay exceeds the client's timeout deadline
            timeout_limit = client_timeout_s or self.timeout_threshold_s
            if simulated_ttft >= timeout_limit:
                await asyncio.sleep(timeout_limit)
                end_time = time.perf_counter()
                elapsed_ms = round((end_time - start_time) * 1000, 2)
                return {
                    "status": "timeout",
                    "content": "",
                    "first_token_ms": elapsed_ms,
                    "total_ms": elapsed_ms,
                    "tokens_in": len(prompt.split()) * 4 // 3,
                    "tokens_out": 0,
                    "source": "stand-in",
                    "error": f"Request timed out after {timeout_limit}s"
                }

            # Wait for TTFT (the model processing prompt & queueing)
            await asyncio.sleep(simulated_ttft)
            first_token_time = time.perf_counter()

            # Random 500 error injection
            # Under heavy in-flight load, error rate increases slightly
            dynamic_error_rate = self.error_rate * (1 + 0.2 * self.in_flight_requests)
            if random.random() < dynamic_error_rate:
                end_time = time.perf_counter()
                elapsed_ms = round((end_time - start_time) * 1000, 2)
                return {
                    "status": "error",
                    "content": "",
                    "first_token_ms": round((first_token_time - start_time) * 1000, 2),
                    "total_ms": elapsed_ms,
                    "tokens_in": len(prompt.split()) * 4 // 3,
                    "tokens_out": 0,
                    "source": "stand-in",
                    "error": "500: Internal Server Error (simulated provider crash)"
                }

            # Simulate streaming tokens piece by piece
            # 150 tokens/sec ≈ 0.0067s per token
            token_delay = 0.007
            streamed_tokens = []
            
            # Construct a synthetic cited response
            sample_response = (
                "Based on the provided research papers, multi-head attention allows the model "
                "to jointly attend to information from different representation subspaces. "
                "[Paper: Attention Is All You Need (1706.03762v7), Page 5]"
            )
            words = sample_response.split()

            for word in words:
                await asyncio.sleep(token_delay)
                streamed_tokens.append(word)

            end_time = time.perf_counter()

            return {
                "status": "ok",
                "content": " ".join(streamed_tokens),
                "first_token_ms": round((first_token_time - start_time) * 1000, 2),
                "total_ms": round((end_time - start_time) * 1000, 2),
                "tokens_in": max(1, len(prompt.split()) * 4 // 3),
                "tokens_out": len(words) * 4 // 3,
                "source": "stand-in",
                "error": None
            }

        finally:
            async with self._lock:
                self.in_flight_requests = max(0, self.in_flight_requests - 1)


if __name__ == "__main__":
    async def test_simulator():
        sim = SimulatedModelService()
        print("--- Testing Stand-in Model Service under normal load ---")
        res1 = await sim.call_streaming("Test prompt under normal load")
        print(f"Normal Load -> Status: {res1['status']} | TTFT: {res1['first_token_ms']}ms | Total: {res1['total_ms']}ms")

        print("\n--- Testing Stand-in Model Service under simulated burst (10 concurrent) ---")
        tasks = [sim.call_streaming(f"Burst request {i}") for i in range(10)]
        results = await asyncio.gather(*tasks)
        for i, r in enumerate(results[:5]):
            print(f"Req {i} -> Status: {r['status']} | TTFT: {r['first_token_ms']}ms | Total: {r['total_ms']}ms")

    asyncio.run(test_simulator())