"""
Groq Service module for The Relay.
Provides async streaming model calls, precise TTFT and total latency tracking,
token counting, and rate-limit header inspection.
"""

import os
import time
from typing import AsyncGenerator, Dict, Any, Optional
from dotenv import load_dotenv
from groq import AsyncGroq, RateLimitError, APIError

load_dotenv()

# We use llama-3.1-8b-instant: it's fast, widely supported on Groq's free tier,
# and ideal for benchmarking TTFT and tokens/sec.
DEFAULT_MODEL = "openai/gpt-oss-20b"


class GroqService:
    def __init__(self, api_key: Optional[str] = None, model: str = DEFAULT_MODEL):
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError("GROQ_API_KEY not found. Please set it in your .env file.")
        
        self.client = AsyncGroq(api_key=self.api_key)
        self.model = model
        self.last_headers: Dict[str, str] = {}

    async def call_streaming(
        self,
        prompt: str,
        system_prompt: str = "You are a precise AI research assistant. Answer only from the provided passages.",
        max_tokens: int = 1024,
        temperature: float = 0.2
    ) -> Dict[str, Any]:
        """
        Calls Groq with streaming to capture Time to First Token (TTFT),
        total latency, token output, and response headers.
        """
        start_time = time.perf_counter()
        first_token_time = None
        collected_chunks = []
        tokens_out_approx = 0

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )

            async for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    if first_token_time is None:
                        first_token_time = time.perf_counter()
                    collected_chunks.append(delta)

            end_time = time.perf_counter()

            if first_token_time is None:
                first_token_time = end_time

            first_token_ms = round((first_token_time - start_time) * 1000, 2)
            total_ms = round((end_time - start_time) * 1000, 2)
            full_response = "".join(collected_chunks)
            
            # Approximation: 1 token ≈ 4 characters or ~0.75 words
            tokens_out_approx = max(1, len(full_response.split()) * 4 // 3)
            tokens_in_approx = max(1, (len(prompt.split()) + len(system_prompt.split())) * 4 // 3)

            return {
                "status": "ok",
                "content": full_response,
                "first_token_ms": first_token_ms,
                "total_ms": total_ms,
                "tokens_in": tokens_in_approx,
                "tokens_out": tokens_out_approx,
                "source": "real",
                "error": None
            }

        except RateLimitError as e:
            end_time = time.perf_counter()
            total_ms = round((end_time - start_time) * 1000, 2)
            return {
                "status": "rate_limited",
                "content": "",
                "first_token_ms": total_ms,
                "total_ms": total_ms,
                "tokens_in": 0,
                "tokens_out": 0,
                "source": "real",
                "error": str(e)
            }

        except Exception as e:
            end_time = time.perf_counter()
            total_ms = round((end_time - start_time) * 1000, 2)
            return {
                "status": "error",
                "content": "",
                "first_token_ms": total_ms,
                "total_ms": total_ms,
                "tokens_in": 0,
                "tokens_out": 0,
                "source": "real",
                "error": str(e)
            }


async def probe_groq_limits():
    """
    Sends a sample request and inspects raw HTTP response headers
    to determine exact rate limits for Table 1.
    """
    import httpx

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        print("Error: GROQ_API_KEY not found in .env!")
        return

    # Strip any accidental whitespace or quotes
    api_key = api_key.strip().strip("'\"")

    print(f"Using API Key: {api_key[:8]}...{api_key[-4:]}")
    print("Testing Groq models endpoint...")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        # 1. First, check which models are currently active on your account
        models_resp = await client.get("https://api.groq.com/openai/v1/models", headers=headers)
        if models_resp.status_code == 200:
            models_data = models_resp.json().get("data", [])
            all_model_ids = [m["id"] for m in models_data]
            print(f"\nAll available models on your key ({len(all_model_ids)}):")
            for mid in all_model_ids:
                print(f"  - {mid}")
        else:
            print(f"Models check failed! Status {models_resp.status_code}: {models_resp.text}")

        # 2. Test chat completion
        payload = {
            "model": DEFAULT_MODEL,
            "messages": [{"role": "user", "content": "Ping"}],
            "max_tokens": 5
        }
        resp = await client.post("https://api.groq.com/openai/v1/chat/completions", headers=headers, json=payload)
        
        print(f"\nChat Completions HTTP Status: {resp.status_code}")
        if resp.status_code != 200:
            print(f"Error Response Body: {resp.text}")
        else:
            print("--- Rate Limit Headers Found ---")
            for k, v in resp.headers.items():
                if "ratelimit" in k.lower():
                    print(f"  {k}: {v}")

        # 3. Test GroqService streaming call
        print("\nTesting GroqService streaming call...")
        service = GroqService(api_key=api_key)
        result = await service.call_streaming("What is attention in 1 sentence?")
        print(f"Status: {result['status']}")
        if result['status'] != 'ok':
            print(f"Service Error: {result.get('error')}")
        else:
            print(f"TTFT: {result['first_token_ms']} ms")
            print(f"Total Latency: {result['total_ms']} ms")
            print(f"Tokens Out: ~{result['tokens_out']}")
            print(f"Reply: {result['content'][:120]}...")

if __name__ == "__main__":
    import asyncio
    asyncio.run(probe_groq_limits())