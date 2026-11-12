"""
Rate Limiter and Queue Manager for The Relay.
Implements token-bucket pacing, concurrency limiting, and peak queue tracking.
"""

import asyncio
import time
from typing import Optional


class AsyncRateLimiter:
    def __init__(
        self,
        max_rpm: int = 1000,
        max_concurrent: int = 15,
        max_queue_depth: int = 100
    ):
        self.max_rpm = max_rpm
        self.max_concurrent = max_concurrent
        self.max_queue_depth = max_queue_depth

        # Concurrency semaphore
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Queue metrics
        self.current_queue_depth = 0
        self.peak_queue_depth = 0
        self._lock = asyncio.Lock()

        # Sliding window timestamps
        self.timestamps = []

    async def acquire(self) -> bool:
        """
        Enters queue to acquire processing slot.
        Returns True if acquired, or False if queue is saturated (drop/shed).
        """
        async with self._lock:
            if self.current_queue_depth >= self.max_queue_depth:
                return False  # Shed load immediately
            self.current_queue_depth += 1
            if self.current_queue_depth > self.peak_queue_depth:
                self.peak_queue_depth = self.current_queue_depth

        try:
            # Wait for available concurrent processing slot
            await self.semaphore.acquire()

            # Pacing check (sliding window)
            async with self._lock:
                now = time.time()
                self.timestamps = [t for t in self.timestamps if now - t < 60.0]
                if len(self.timestamps) >= self.max_rpm:
                    # Brief sleep to pace requests
                    sleep_needed = 60.0 - (now - self.timestamps[0])
                    if sleep_needed > 0:
                        await asyncio.sleep(min(sleep_needed, 1.0))
                self.timestamps.append(time.time())

            return True

        finally:
            async with self._lock:
                self.current_queue_depth = max(0, self.current_queue_depth - 1)

    def release(self):
        """Releases concurrency slot."""
        self.semaphore.release()

    def get_peak_queue(self) -> int:
        return self.peak_queue_depth

    def reset_metrics(self):
        self.peak_queue_depth = self.current_queue_depth