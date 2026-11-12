"""
Curated 16 Evaluation Questions for The Relay.
Covers all 3 research papers and contains unanswerable questions to verify explicit refusal.
"""

from typing import List, Dict, Any

EVALUATION_QUESTIONS: List[Dict[str, Any]] = [
    # -------------------------------------------------------------
    # Paper 1: Attention Is All You Need (1706.03762v7)
    # -------------------------------------------------------------
    {
        "id": "q1_attn",
        "question": "Why does the Transformer use Scaled Dot-Product Attention instead of additive attention?",
        "paper": "Attention Is All You Need",
        "is_expected_refusal": False,
        "key_concepts": ["scaled", "dimension", "softmax", "faster", "space-efficient"]
    },
    {
        "id": "q2_attn",
        "question": "What is the formula for the sinusoidal positional encodings used in the Transformer?",
        "paper": "Attention Is All You Need",
        "is_expected_refusal": False,
        "key_concepts": ["sin", "cos", "pos", "2i", "10000"]
    },
    {
        "id": "q3_attn",
        "question": "What are the values of d_k, d_v, and number of heads h in the Transformer base model?",
        "paper": "Attention Is All You Need",
        "is_expected_refusal": False,
        "key_concepts": ["h=8", "d_k=64", "d_v=64", "d_model=512"]
    },
    {
        "id": "q4_attn",
        "question": "How does self-attention in the decoder differ from self-attention in the encoder?",
        "paper": "Attention Is All You Need",
        "is_expected_refusal": False,
        "key_concepts": ["masking", "autoregressive", "future positions", "prevent leftward"]
    },

    # -------------------------------------------------------------
    # Paper 2: Moshi: A Speech-Text Foundation Model (2410.00037v1)
    # -------------------------------------------------------------
    {
        "id": "q5_moshi",
        "question": "How does Moshi model multi-stream audio and text dialogue simultaneously?",
        "paper": "Moshi",
        "is_expected_refusal": False,
        "key_concepts": ["dual-stream", "inner monologue", "user stream", "agent stream"]
    },
    {
        "id": "q6_moshi",
        "question": "What is the Mimi neural audio codec and what bitrate/frame rate does it operate at?",
        "paper": "Moshi",
        "is_expected_refusal": False,
        "key_concepts": ["mimi", "12.5 hz", "rq-vae", "residual vector quantization", "codec"]
    },
    {
        "id": "q7_moshi",
        "question": "What is the purpose of the 'inner monologue' in Moshi's architecture?",
        "paper": "Moshi",
        "is_expected_refusal": False,
        "key_concepts": ["inner monologue", "predict text before audio", "linguistic reasoning"]
    },
    {
        "id": "q8_moshi",
        "question": "What base language model is used to initialize Moshi before speech fine-tuning?",
        "paper": "Moshi",
        "is_expected_refusal": False,
        "key_concepts": ["helium", "7b", "text pretraining"]
    },

    # -------------------------------------------------------------
    # Paper 3: Dynamic Chunking / H-Net (2507.07955v2)
    # -------------------------------------------------------------
    {
        "id": "q9_chunk",
        "question": "How does Dynamic Chunking eliminate the traditional Byte-Pair Encoding (BPE) tokenization step?",
        "paper": "Dynamic Chunking",
        "is_expected_refusal": False,
        "key_concepts": ["end-to-end", "learned boundary", "bytes", "segmentation", "tokenizer-free"]
    },
    {
        "id": "q10_chunk",
        "question": "What is the H-Net architecture and how does it achieve hierarchical sequence modeling?",
        "paper": "Dynamic Chunking",
        "is_expected_refusal": False,
        "key_concepts": ["hierarchical", "multi-stage", "downsampling", "upsampling"]
    },
    {
        "id": "q11_chunk",
        "question": "What data efficiency improvement did H-Net demonstrate on DNA sequences compared to token baselines?",
        "paper": "Dynamic Chunking",
        "is_expected_refusal": False,
        "key_concepts": ["4x", "data efficiency", "genomic", "dna"]
    },
    {
        "id": "q12_chunk",
        "question": "What mechanism does Dynamic Chunking use to determine chunk boundaries dynamically?",
        "paper": "Dynamic Chunking",
        "is_expected_refusal": False,
        "key_concepts": ["router", "boundary probability", "gumbel", "sigmoid", "threshold"]
    },

    # -------------------------------------------------------------
    # Unanswerable Questions (Must be REFUSED explicitly)
    # -------------------------------------------------------------
    {
        "id": "q13_absent",
        "question": "What is the training loss and learning rate schedule of the DeepSeek-V3 mixture of experts model?",
        "paper": "Absent",
        "is_expected_refusal": True,
        "key_concepts": []
    },
    {
        "id": "q14_absent",
        "question": "How does quantum key distribution establish encryption keys using polarization states?",
        "paper": "Absent",
        "is_expected_refusal": True,
        "key_concepts": []
    },
    {
        "id": "q15_absent",
        "question": "What are the clinical trial results for mRNA-4157 personalized cancer vaccine?",
        "paper": "Absent",
        "is_expected_refusal": True,
        "key_concepts": []
    },
    {
        "id": "q16_absent",
        "question": "How does the Raft consensus algorithm handle split votes during leader election?",
        "paper": "Absent",
        "is_expected_refusal": True,
        "key_concepts": []
    }
]


if __name__ == "__main__":
    print(f"Loaded {len(EVALUATION_QUESTIONS)} evaluation questions:")
    for q in EVALUATION_QUESTIONS:
        status = "REFUSAL TARGET" if q["is_expected_refusal"] else "IN-DOMAIN"
        print(f"[{q['id']}] ({status}) {q['question']}")