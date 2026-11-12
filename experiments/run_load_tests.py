"""
Load Testing Experiment Runner for Table 2a and Table 2b.
Executes the 5 mandatory load scenarios:
  1. Steady
  2. Burst
  3. Sustained Overload
  4. Per-minute Limit Halved
  5. Daily Budget Exhausted
All request traces are written to results/results.csv.
"""

import asyncio
import time
from typing import List, Dict, Any

from pipeline.relay_pipeline import RelayPipeline
from services.simulator import SimulatedModelService
from reliability.rate_limiter import AsyncRateLimiter
from reliability.retry_manager import RetryManager
from experiments.evaluation_questions import EVALUATION_QUESTIONS
from experiments.csv_logger import log_request_result


SAMPLE_QUERIES = [q["question"] for q in EVALUATION_QUESTIONS if not q["is_expected_refusal"]]


async def run_scenario(
    name: str,
    num_requests: int,
    dispatch_interval_s: float,
    simulator: SimulatedModelService,
    rate_limiter: AsyncRateLimiter,
    retry_manager: RetryManager
):
    print(f"\n=======================================================")
    print(f" Running Scenario: {name.upper()}")
    print(f" Requests: {num_requests} | Interval: {dispatch_interval_s}s")
    print(f"=======================================================")

    pipeline = RelayPipeline(
        backend_type="stand-in",
        retrieval_setting="setting_a",
        rate_limiter=rate_limiter,
        retry_manager=retry_manager
    )
    # Inject our configured simulator instance
    pipeline.model_service = simulator

    rate_limiter.reset_metrics()
    start_test = time.time()

    async def _send_one(i: int):
        q = SAMPLE_QUERIES[i % len(SAMPLE_QUERIES)]
        res = await pipeline.run(
            query=q,
            scenario=name,
            is_expected_refusal=False
        )
        log_request_result(res)
        return res

    tasks = []
    for i in range(num_requests):
        tasks.append(asyncio.create_task(_send_one(i)))
        if dispatch_interval_s > 0:
            await asyncio.sleep(dispatch_interval_s)

    results = await asyncio.gather(*tasks)
    total_duration_s = round(time.time() - start_test, 2)
    offered_rate = round((num_requests / total_duration_s) * 60, 1) if total_duration_s > 0 else 0

    succeeded = sum(1 for r in results if r["status"] == "ok")
    rate_limited = sum(1 for r in results if r["status"] == "rate_limited")
    timed_out = sum(1 for r in results if r["status"] == "timeout")
    errors = sum(1 for r in results if r["status"] == "error")
    peak_q = rate_limiter.get_peak_queue()

    print(f"\nScenario '{name}' Summary:")
    print(f"  Duration: {total_duration_s}s | Offered Rate: {offered_rate} req/min")
    print(f"  Succeeded: {succeeded}/{num_requests} ({succeeded/num_requests*100:.1f}%)")
    print(f"  Rate-Limited: {rate_limited}/{num_requests} ({rate_limited/num_requests*100:.1f}%)")
    print(f"  Timed Out / Given Up: {timed_out}/{num_requests} ({timed_out/num_requests*100:.1f}%)")
    print(f"  Peak Queue Depth: {peak_q}")

    return {
        "scenario": name,
        "requests": num_requests,
        "duration_s": total_duration_s,
        "offered_rate": offered_rate,
        "peak_queue": peak_q
    }


async def main():
    retry_mgr = RetryManager(max_retries=2, base_backoff_s=0.5, request_timeout_s=8.0)

    # -----------------------------------------------------------------
    # Scenario 1: Steady Traffic (20 requests, paced 1 per 1.5s)
    # -----------------------------------------------------------------
    sim_steady = SimulatedModelService(rpm_limit=1000)
    limiter_steady = AsyncRateLimiter(max_rpm=1000, max_concurrent=10)
    await run_scenario("steady", 20, 1.5, sim_steady, limiter_steady, retry_mgr)

    # -----------------------------------------------------------------
    # Scenario 2: Sudden Burst (50 requests simultaneously)
    # -----------------------------------------------------------------
    sim_burst = SimulatedModelService(rpm_limit=1000)
    limiter_burst = AsyncRateLimiter(max_rpm=1000, max_concurrent=10)
    await run_scenario("burst", 50, 0.0, sim_burst, limiter_burst, retry_mgr)

    # -----------------------------------------------------------------
    # Scenario 3: Sustained Overload (80 requests dispatched rapidly)
    # -----------------------------------------------------------------
    sim_overload = SimulatedModelService(rpm_limit=1000, error_rate=0.05)
    limiter_overload = AsyncRateLimiter(max_rpm=1000, max_concurrent=8, max_queue_depth=35)
    await run_scenario("sustained_overload", 80, 0.1, sim_overload, limiter_overload, retry_mgr)

    # -----------------------------------------------------------------
    # Scenario 4: Per-Minute Limit Halved (RPM halved to 30 req/min)
    # -----------------------------------------------------------------
    sim_halved = SimulatedModelService(rpm_limit=30)
    limiter_halved = AsyncRateLimiter(max_rpm=30, max_concurrent=10)
    await run_scenario("rpm_halved", 50, 0.2, sim_halved, limiter_halved, retry_mgr)

    # -----------------------------------------------------------------
    # Scenario 5: Daily Budget Exhausted (daily quota = 0)
    # -----------------------------------------------------------------
    sim_exhausted = SimulatedModelService(daily_limit=0)
    limiter_exhausted = AsyncRateLimiter(max_rpm=1000, max_concurrent=10)
    await run_scenario("daily_budget_exhausted", 20, 0.1, sim_exhausted, limiter_exhausted, retry_mgr)

    print("\nAll 5 load testing scenarios completed! All traces recorded in results/results.csv.")


if __name__ == "__main__":
    asyncio.run(main())