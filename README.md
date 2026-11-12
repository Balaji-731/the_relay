# The Relay — Reliable, Low-Latency Research Assistant Pipeline

An asynchronous, fault-tolerant AI research assistant pipeline built for the ML Engineering Intern Assignment. It answers technical queries strictly using 3 specific research papers (*Attention Is All You Need*, *Moshi*, *Dynamic Chunking*) with full citation tracking, early refusal branching, rate-limiting, and jittered exponential backoff retries.

---

## Project Structure

```text
The_Relay/
├── data/
│   ├── papers/             # Exact arXiv PDFs (1706.03762v7, 2410.00037v1, 2507.07955v2)
│   └── chroma_db/          # Persistent ChromaDB collections (300, 500, 700 words)
├── ingestion/
│   ├── pdf_loader.py       # Page-level text extraction with citation metadata (PyMuPDF)
│   └── chunker.py          # Configurable word chunking with overlap
├── retrieval/
│   ├── vector_store.py     # ChromaDB persistence & local embedding generation (MiniLM)
│   └── retriever.py        # Top-k vector retrieval, cross-encoder reranker & refusal scoring
├── services/
│   ├── groq_service.py     # Hosted Groq API async client with streaming TTFT tracking
│   └── simulator.py        # Calibrated stand-in model service with dynamic concurrency latency
├── reliability/
│   ├── rate_limiter.py     # Token-bucket sliding-window rate limiter & queue manager
│   └── retry_manager.py    # Exponential backoff with full jitter & request deadlines
├── pipeline/
│   └── relay_pipeline.py   # 4-step Relay pipeline with early mathematical refusal branching
├── experiments/
│   ├── evaluation_questions.py  # 16 curated technical & unanswerable evaluation questions
│   ├── run_retrieval_experiment.py # Table 3 benchmark runner (Setting A, B, C)
│   ├── run_load_tests.py   # Table 2a/2b load test runner (5 required scenarios)
│   └── csv_logger.py       # Thread-safe logger writing strictly to results/results.csv
├── results/
│   ├── results.csv         # Raw trace file containing all 268 requests with exact schema
│   └── compute_tables.py   # Pandas script generating Table 1, 2a, 2b, and 3
├── report/
│   ├── writeup.md          # Complete two-page submission report matching requested headings
│   └── conversation_history.md # Unedited log of prompts, decisions, and caught mistakes
├── pyproject.toml          # uv project configuration and dependency lock
└── README.md               # Quick-start instructions
```

---

## Quick Start (with `uv`)

### 1. Setup Environment
```powershell
# Clone or navigate to the repository
cd The_Relay

# Create virtual environment and sync dependencies
uv sync
```

### 2. Configure Groq API Key
Create a `.env` file in the project root:
```env
GROQ_API_KEY=gsk_your_groq_api_key_here
```

### 3. Run the Pipeline Interactively
```powershell
# Test interactive question answering with early refusal branching
uv run python -m pipeline.relay_pipeline
```

---

## Reproducing Experiments & Computing Tables

All experimental results are generated deterministically and logged to `results/results.csv`.

### 1. Run Retrieval Quality vs. Cost Experiments (Table 3)
```powershell
uv run python -m experiments.run_retrieval_experiment
```
Evaluates all 16 questions across Setting A (300 words), Setting B (500 words), and Setting C (700 words with reranking).

### 2. Run the 5 Load Testing Scenarios (Table 2a & Table 2b)
```powershell
uv run python -m experiments.run_load_tests
```
Executes:
1. `steady`: 20 requests at steady pace.
2. `burst`: 50 concurrent requests simultaneously.
3. `sustained_overload`: 80 requests exceeding service draining capacity.
4. `rpm_halved`: 50 requests with per-minute quota cut by 50%.
5. `daily_budget_exhausted`: 20 requests simulating 3:00 PM daily quota exhaustion.

### 3. Recompute All Tables from `results/results.csv`
```powershell
uv run python -m results.compute_tables
```
Parses `results/results.csv` using `pandas` and prints Table 1, Table 2a, Table 2b, and Table 3 in markdown format with exact $p50, p95, p99$ latency percentiles and success rates.

---

## Key Experimental Findings

1. **Early Refusal Branching Saves 100% of Tokens on Out-of-Domain Queries:**
   By measuring dense cosine distance against indexed passages, questions absent from the library trigger an instant refusal in **18 ms** consuming **0 LLM tokens**.
2. **Optimal Retrieval Setting:**
   Setting A (300 words, 3 chunks) achieved **93.8% total accuracy (0.0% wrong)** with **1,009 tokens/answer**. Settings B & C exceeded Groq's 8,000 TPM limit on consecutive calls, causing 43.8% timeout/retries.
3. **Concurrency Bottlenecks Dominate Rate Limits:**
   In burst scenarios, requests failed primarily from concurrency queue saturation (peak queue = 40) rather than per-minute limits, proving that admission control and load shedding are essential in production LLM pipelines.
