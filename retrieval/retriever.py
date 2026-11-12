"""
Retriever module for The Relay.
Implements top-k vector search, cross-encoder reranking, and citation formatting
for Setting A, Setting B, and Setting C.
"""

from typing import List, Dict, Any, Optional
from retrieval.vector_store import get_chroma_client, get_embedding_function

# Reranker model (lazy-loaded so it only loads into memory if Setting C is invoked)
_RERANKER = None


def get_reranker():
    global _RERANKER
    if _RERANKER is None:
        from sentence_transformers import CrossEncoder
        # Fast, lightweight cross-encoder for passage reranking
        _RERANKER = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _RERANKER


RETRIEVAL_PRESETS = {
    "setting_a": {
        "collection_name": "relay_setting_300",
        "top_k": 3,
        "rerank": False,
        "description": "300 words, 3 chunks, No reranking"
    },
    "setting_b": {
        "collection_name": "relay_setting_500",
        "top_k": 5,
        "rerank": False,
        "description": "500 words, 5 chunks, No reranking"
    },
    "setting_c": {
        "collection_name": "relay_setting_700",
        "top_k": 8,
        "rerank": True,
        "candidate_k": 15,  # Fetch 15 candidates, rerank to top 8
        "description": "700 words, 8 chunks, With reranking"
    }
}


class PaperRetriever:
    def __init__(self):
        self.client = get_chroma_client()
        self.embedding_fn = get_embedding_function()

    def retrieve(
        self,
        query: str,
        setting_name: str = "setting_b"
    ) -> Dict[str, Any]:
        """
        Retrieves passages based on the selected setting preset.
        Returns a dict containing:
          - passages: List of formatted passage dicts with text and citation
          - formatted_context: Concatenated context string for LLM prompting
          - max_similarity: Highest similarity score observed (for refusal heuristic)
          - setting_name: The preset used
        """
        if setting_name not in RETRIEVAL_PRESETS:
            raise ValueError(f"Unknown setting '{setting_name}'. Choose from {list(RETRIEVAL_PRESETS.keys())}")

        preset = RETRIEVAL_PRESETS[setting_name]
        collection = self.client.get_collection(
            name=preset["collection_name"],
            embedding_function=self.embedding_fn
        )

        # Decide how many items to query from ChromaDB
        k_to_fetch = preset.get("candidate_k", preset["top_k"]) if preset["rerank"] else preset["top_k"]

        results = collection.query(
            query_texts=[query],
            n_results=k_to_fetch
        )

        documents = results["documents"][0] if results["documents"] else []
        metadatas = results["metadatas"][0] if results["metadatas"] else []
        distances = results["distances"][0] if results["distances"] else []

        if not documents:
            return {
                "passages": [],
                "formatted_context": "",
                "max_similarity": 0.0,
                "setting_name": setting_name
            }

        # Convert cosine distance to cosine similarity (Chroma cosine distance is in [0, 2])
        # Cosine similarity = 1 - distance
        raw_items = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            similarity = max(0.0, 1.0 - dist)
            raw_items.append({
                "text": doc,
                "metadata": meta,
                "similarity": similarity
            })

        # Apply Cross-Encoder Reranking if enabled (Setting C)
        if preset["rerank"] and len(raw_items) > preset["top_k"]:
            reranker = get_reranker()
            pairs = [[query, item["text"]] for item in raw_items]
            rerank_scores = reranker.predict(pairs)
            for idx, score in enumerate(rerank_scores):
                raw_items[idx]["rerank_score"] = float(score)
            
            # Sort descending by cross-encoder score and take top_k
            raw_items.sort(key=lambda x: x["rerank_score"], reverse=True)
            raw_items = raw_items[:preset["top_k"]]

        # Build clean citations and formatted context block
        passages = []
        context_blocks = []
        max_sim = max(item["similarity"] for item in raw_items) if raw_items else 0.0

        for idx, item in enumerate(raw_items):
            m = item["metadata"]
            citation = f"[Paper: {m['paper_title']} ({m['arxiv_id']}{m['version']}), Page {m['page']}]"
            
            passages.append({
                "citation": citation,
                "text": item["text"],
                "metadata": m,
                "similarity": round(item["similarity"], 4)
            })

            context_blocks.append(f"Passage {idx + 1} {citation}:\n{item['text']}")

        formatted_context = "\n\n".join(context_blocks)

        return {
            "passages": passages,
            "formatted_context": formatted_context,
            "max_similarity": max_sim,
            "setting_name": setting_name
        }


if __name__ == "__main__":
    retriever = PaperRetriever()

    # Test with a question answerable from Paper 1 (Attention)
    q1 = "How does multi-head attention work in the Transformer?"
    print(f"\n--- Testing Query: '{q1}' ---")
    res1 = retriever.retrieve(q1, setting_name="setting_a")
    print(f"Setting: {res1['setting_name']}")
    print(f"Passages retrieved: {len(res1['passages'])}")
    print(f"Max similarity: {res1['max_similarity']}")
    if res1["passages"]:
        print(f"Top citation: {res1['passages'][0]['citation']}")

    # Test with an unanswerable question (absent from library)
    q2 = "Who was the first president of the United States?"
    print(f"\n--- Testing Out-of-Domain Query: '{q2}' ---")
    res2 = retriever.retrieve(q2, setting_name="setting_a")
    print(f"Max similarity: {res2['max_similarity']}")