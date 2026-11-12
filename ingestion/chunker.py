"""
Chunker module for The Relay.
Splits page-level text into chunks of configurable sizes with overlap,
preserving complete metadata for citation tracking.
"""

from typing import List, Dict, Any


def split_text_into_chunks(text: str, chunk_size: int, overlap: int) -> List[str]:
    """
    Splits text by whitespace-delimited words with an overlap window.
    Word-based chunking closely approximates token counts (1 word ≈ 1.3 tokens)
    without introducing tokenizer overhead.
    """
    words = text.split()
    if not words:
        return []

    chunks = []
    step = chunk_size - overlap
    if step <= 0:
        raise ValueError("chunk_size must be strictly greater than overlap")

    for i in range(0, len(words), step):
        chunk_words = words[i:i + chunk_size]
        chunks.append(" ".join(chunk_words))
        if i + chunk_size >= len(words):
            break

    return chunks


def chunk_pages(
    pages_data: List[Dict[str, Any]],
    chunk_size: int = 500,
    overlap: int = 50
) -> List[Dict[str, Any]]:
    """
    Takes a list of page dicts (from pdf_loader) and produces chunks.
    Each chunk dict contains:
      - 'id': unique identifier (e.g., '1706.03762_p3_c0')
      - 'text': chunk text content
      - 'metadata': paper title, arxiv_id, version, page, chunk_index
    """
    all_chunks = []

    for page_item in pages_data:
        text = page_item["text"]
        meta = page_item["metadata"]
        text_chunks = split_text_into_chunks(text, chunk_size=chunk_size, overlap=overlap)

        for c_idx, chunk_text in enumerate(text_chunks):
            chunk_id = f"{meta['arxiv_id']}_p{meta['page']}_c{c_idx}"
            chunk_record = {
                "id": chunk_id,
                "text": chunk_text,
                "metadata": {
                    "paper_title": meta["paper_title"],
                    "arxiv_id": meta["arxiv_id"],
                    "version": meta["version"],
                    "page": meta["page"],
                    "chunk_index": c_idx,
                    "chunk_size_setting": chunk_size
                }
            }
            all_chunks.append(chunk_record)

    return all_chunks


if __name__ == "__main__":
    from ingestion.pdf_loader import load_all_papers

    pages = load_all_papers()
    
    # Test our three required chunk sizes
    for size, overlap in [(300, 30), (500, 50), (700, 70)]:
        chunks = chunk_pages(pages, chunk_size=size, overlap=overlap)
        print(f"Setting ({size} words, {overlap} overlap): generated {len(chunks)} chunks")