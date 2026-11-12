"""
CSV Logger for The Relay.
Ensures thread-safe, compliant logging to results/results.csv
with the exact schema required by the assignment brief.
"""

import os
import csv
import threading
from typing import Dict, Any

RESULTS_CSV_PATH = "results/results.csv"
CSV_COLUMNS = [
    "request_id",
    "scenario",
    "source",
    "start_time",
    "first_token_ms",
    "total_ms",
    "status",
    "retries",
    "tokens_in",
    "tokens_out",
    "retrieval_setting",
    "answer_grade"
]

_CSV_LOCK = threading.Lock()


def init_results_csv(file_path: str = RESULTS_CSV_PATH):
    """Initializes results.csv with header if it doesn't exist."""
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with _CSV_LOCK:
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            with open(file_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(CSV_COLUMNS)


def log_request_result(record: Dict[str, Any], file_path: str = RESULTS_CSV_PATH):
    """Appends a single request record to results.csv."""
    init_results_csv(file_path)
    
    # Sanitize and ensure only allowed values are recorded
    row = [
        record.get("request_id", ""),
        record.get("scenario", "unknown"),
        record.get("source", "stand-in"),
        record.get("start_time", ""),
        record.get("first_token_ms", 0.0),
        record.get("total_ms", 0.0),
        record.get("status", "error"),
        record.get("retries", 0),
        record.get("tokens_in", 0),
        record.get("tokens_out", 0),
        record.get("retrieval_setting", "setting_b"),
        record.get("answer_grade", "wrong")
    ]

    with _CSV_LOCK:
        with open(file_path, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(row)