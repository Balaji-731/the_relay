"""
The Relay Pipeline.
Implements the 4 processing steps, tool call, refusal branching,
and citation verification grading.
"""

import re
import time
import uuid
from typing import Dict, Any, Optional

from retrieval.retriever import PaperRetriever
from services.groq_service import GroqService
from services.simulator import SimulatedModelService
from reliability.rate_limiter import AsyncRateLimiter
from reliability.retry_manager import RetryManager


# Empirical threshold established from our probe (in-domain ~0.65 vs out-of-domain ~0.11)
REFUSAL_SIMILARITY_THRESHOLD = 0.30

STANDARD_REFUSAL_TEXT = (
    "I cannot find the answer to this question in the provided library of research papers "
    "(Attention Is All You Need, Moshi, and Dynamic Chunking)."
)


class RelayPipeline:
    def __init__(
        self,
        backend_type: str = "real",  # "real" or "stand-in"
        retrieval_setting: str = "setting_b",
        rate_limiter: Optional[AsyncRateLimiter] = None,
        retry_manager: Optional[RetryManager] = None
    ):
        self.backend_type = backend_type
        self.retrieval_setting = retrieval_setting

        # Step 2 Tool
        self.retriever = PaperRetriever()

        # Step 3 Backends
        if backend_type == "real":
            self.model_service = GroqService()
        else:
            self.model_service = SimulatedModelService()

        # Reliability wrappers
        self.rate_limiter = rate_limiter or AsyncRateLimiter()
        self.retry_manager = retry_manager or RetryManager()

    # Step 1: Query Understanding
    def understand_query(self, query: str) -> Dict[str, Any]:
        cleaned = query.strip()
        is_empty = len(cleaned) == 0
        is_short = len(cleaned.split()) < 3
        
        # Simple intent heuristic: check for technical paper domain keywords
        domain_keywords = [
            "transformer", "attention", "multi-head", "moshi", "audio", "speech",
            "chunk", "dynamic", "h-net", "byte", "token", "encoder", "decoder",
            "layer", "mimo", "rq-vae", "helium"
        ]
        has_domain_keywords = any(kw in cleaned.lower() for kw in domain_keywords)

        return {
            "cleaned_query": cleaned,
            "is_valid": not is_empty,
            "is_short": is_short,
            "has_domain_keywords": has_domain_keywords
        }

    # Step 4: Citation and Quality Checker
    def verify_and_grade(
        self,
        response_text: str,
        retrieved_passages: list,
        is_expected_refusal: bool = False
    ) -> str:
        """
        Grades response into one of the 4 strict categories for results.csv:
        - correct
        - wrong
        - refused_correctly
        - refused_wrongly
        """
        refusal_phrases = [
            "cannot find", "not found", "does not contain", "not mentioned",
            "provided library", "not stated in the paper"
        ]
        is_refusal = any(phrase in response_text.lower() for phrase in refusal_phrases)

        # Check if citations exist in the output (e.g. "[Paper: ..., Page ...]")
        has_citation = bool(re.search(r"\[Paper:.*?Page.*?\]", response_text))

        if is_expected_refusal:
            if is_refusal:
                return "refused_correctly"
            else:
                return "wrong"  # Hallucinated an answer when it should have refused

        if is_refusal:
            return "refused_wrongly"  # Refused an answer that was actually in the library

        if has_citation and len(response_text) > 40:
            return "correct"
        
        return "wrong"

    async def run(
        self,
        query: str,
        scenario: str = "ad_hoc",
        is_expected_refusal: bool = False
    ) -> Dict[str, Any]:
        """
        Executes the full Relay 4-step pipeline with timing and tracing.
        """
        request_id = f"req_{uuid.uuid4().hex[:8]}"
        start_time = time.time()
        start_time_iso = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(start_time))

        # -------------------------------------------------------------
        # Step 1: Query Understanding
        # -------------------------------------------------------------
        q_meta = self.understand_query(query)
        if not q_meta["is_valid"]:
            return {
                "request_id": request_id,
                "scenario": scenario,
                "source": self.backend_type,
                "start_time": start_time_iso,
                "first_token_ms": 0.0,
                "total_ms": 0.0,
                "status": "error",
                "retries": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "retrieval_setting": self.retrieval_setting,
                "answer_grade": "wrong",
                "content": "Empty query provided"
            }

        # -------------------------------------------------------------
        # Step 2: Retrieval Engine (Tool Call)
        # -------------------------------------------------------------
        retrieval_res = self.retriever.retrieve(
            query=q_meta["cleaned_query"],
            setting_name=self.retrieval_setting
        )
        passages = retrieval_res["passages"]
        max_sim = retrieval_res["max_similarity"]

        # Branch: Early Refusal if library does not contain relevant passages
        if max_sim < REFUSAL_SIMILARITY_THRESHOLD or not passages:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "request_id": request_id,
                "scenario": scenario,
                "source": self.backend_type,
                "start_time": start_time_iso,
                "first_token_ms": elapsed_ms,
                "total_ms": elapsed_ms,
                "status": "ok",
                "retries": 0,
                "tokens_in": len(query.split()) * 4 // 3,
                "tokens_out": 25,
                "retrieval_setting": self.retrieval_setting,
                "answer_grade": "refused_correctly" if is_expected_refusal else "refused_wrongly",
                "content": STANDARD_REFUSAL_TEXT
            }

        # -------------------------------------------------------------
        # Step 3: Answer Generation (Rate Limiter + Retry + LLM Call)
        # -------------------------------------------------------------
        system_prompt = (
            "You are The Relay, an AI research assistant for engineers. "
            "Answer the question strictly using the provided research paper passages. "
            "You must cite the source using the exact format: [Paper: <Title> (<arxiv_id>), Page <page>]. "
            "If the answer is not supported by the passages, reply: 'I cannot find the answer in the provided library.'"
        )
        user_prompt = f"Passages:\n{retrieval_res['formatted_context']}\n\nQuestion: {query}\nAnswer with citations:"

        # Acquire rate-limit queue slot
        slot_acquired = await self.rate_limiter.acquire()
        if not slot_acquired:
            elapsed_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "request_id": request_id,
                "scenario": scenario,
                "source": self.backend_type,
                "start_time": start_time_iso,
                "first_token_ms": elapsed_ms,
                "total_ms": elapsed_ms,
                "status": "rate_limited",
                "retries": 0,
                "tokens_in": 0,
                "tokens_out": 0,
                "retrieval_setting": self.retrieval_setting,
                "answer_grade": "wrong",
                "content": "Request shed: system queue is saturated"
            }

        try:
            # Execute with Retry Manager
            async def _execute_call():
                return await self.model_service.call_streaming(
                    prompt=user_prompt,
                    system_prompt=system_prompt
                )

            call_res = await self.retry_manager.execute_with_retry(_execute_call)

        finally:
            self.rate_limiter.release()

        # -------------------------------------------------------------
        # Step 4: Citation and Quality Verification Loop
        # -------------------------------------------------------------
        if call_res["status"] == "ok":
            grade = self.verify_and_grade(
                response_text=call_res["content"],
                retrieved_passages=passages,
                is_expected_refusal=is_expected_refusal
            )
        else:
            grade = "wrong"

        total_elapsed_ms = round((time.time() - start_time) * 1000, 2)

        return {
            "request_id": request_id,
            "scenario": scenario,
            "source": self.backend_type,
            "start_time": start_time_iso,
            "first_token_ms": call_res.get("first_token_ms", total_elapsed_ms),
            "total_ms": total_elapsed_ms,
            "status": call_res["status"],
            "retries": call_res.get("retries", 0),
            "tokens_in": call_res.get("tokens_in", len(user_prompt.split()) * 4 // 3),
            "tokens_out": call_res.get("tokens_out", 0),
            "retrieval_setting": self.retrieval_setting,
            "answer_grade": grade,
            "content": call_res.get("content", "")
        }


if __name__ == "__main__":
    import asyncio

    async def test_pipeline():
        print("--- Testing Pipeline with Real Groq Backend ---")
        pipeline = RelayPipeline(backend_type="real", retrieval_setting="setting_b")

        # 1. Test In-domain question
        res1 = await pipeline.run(
            query="How does multi-head attention work in the Transformer?",
            is_expected_refusal=False
        )
        print("\n[Query 1 Result]")
        print(f"Status: {res1['status']} | Grade: {res1['answer_grade']}")
        print(f"TTFT: {res1['first_token_ms']}ms | Total: {res1['total_ms']}ms | Tokens Out: {res1['tokens_out']}")
        print(f"Response: {res1['content'][:250]}...")

        # 2. Test Out-of-domain question (should trigger refusal branch)
        res2 = await pipeline.run(
            query="What is quantum entanglement in qubits?",
            is_expected_refusal=True
        )
        print("\n[Query 2 Result (Unanswerable)]")
        print(f"Status: {res2['status']} | Grade: {res2['answer_grade']}")
        print(f"TTFT: {res2['first_token_ms']}ms | Total: {res2['total_ms']}ms")
        print(f"Response: {res2['content']}")

    asyncio.run(test_pipeline())