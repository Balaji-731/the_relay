"""
Retrieval Experiment Runner for Table 3.
Evaluates Setting A, Setting B, and Setting C against the 16 evaluation questions,
logging results to results/results.csv.
"""

import asyncio
import time
from pipeline.relay_pipeline import RelayPipeline
from experiments.evaluation_questions import EVALUATION_QUESTIONS
from experiments.csv_logger import log_request_result


async def run_retrieval_experiment(backend_for_all: str = "real"):
    """
    Runs the 16 evaluation questions across Setting A, Setting B, and Setting C.
    Paces queries by 2 seconds to respect Groq's 8,000 TPM limit.
    """
    settings = ["setting_a", "setting_b", "setting_c"]
    print(f"\n=======================================================")
    print(f" Starting Retrieval Experiment (Table 3)")
    print(f" Total questions: {len(EVALUATION_QUESTIONS)} | Settings: {settings}")
    print(f" Backend: {backend_for_all}")
    print(f"=======================================================\n")

    for setting in settings:
        print(f"\n--- Running Evaluation for {setting.upper()} ---")
        pipeline = RelayPipeline(
            backend_type=backend_for_all,
            retrieval_setting=setting
        )

        for idx, q_item in enumerate(EVALUATION_QUESTIONS):
            q_text = q_item["question"]
            is_refusal = q_item["is_expected_refusal"]
            q_id = q_item["id"]

            print(f"[{setting} | {idx+1}/{len(EVALUATION_QUESTIONS)}] Testing {q_id}...", end=" ", flush=True)

            res = await pipeline.run(
                query=q_text,
                scenario=f"retrieval_{setting}",
                is_expected_refusal=is_refusal
            )

            # Log to results.csv
            log_request_result(res)

            print(f"-> Grade: {res['answer_grade']} | TTFT: {res['first_token_ms']}ms | Total: {res['total_ms']}ms")

            # Small pacing pause between calls to protect real Groq TPM
            if backend_for_all == "real":
                await asyncio.sleep(2.0)

    print("\nRetrieval experiment completed! All rows logged to results/results.csv.")


if __name__ == "__main__":
    asyncio.run(run_retrieval_experiment(backend_for_all="real"))