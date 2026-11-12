"""
PDF Loader module for The Relay.
Extracts clean text from arXiv research papers while preserving page-level metadata.
"""

import os
import re
from typing import List, Dict, Any
import pymupdf


PAPERS_METADATA = {
    "attention_is_all_you_need_v7.pdf": {
        "title": "Attention Is All You Need",
        "arxiv_id": "1706.03762",
        "version": "v7"
    },
    "moshi_v1.pdf": {
        "title": "Moshi: a speech-text foundation model for real-time dialogue",
        "arxiv_id": "2410.00037",
        "version": "v1"
    },
    "dynamic_chunking_v2.pdf": {
        "title": "Dynamic Chunking for End-to-End Hierarchical Sequence Modeling",
        "arxiv_id": "2507.07955",
        "version": "v2"
    }
}


def clean_text(text: str) -> str:
    """Clean hyphenated line breaks, odd ligatures, and excessive whitespace."""
    # Reconnect hyphenated words split at the end of a line
    text = re.sub(r'(\w+)-\n(\w+)', r'\1\2', text)
    # Replace newlines with spaces within paragraphs
    text = re.sub(r'\n+', ' ', text)
    # Collapse multiple spaces into one
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def load_paper_pages(pdf_path: str) -> List[Dict[str, Any]]:
    """
    Extracts text page-by-page from a given PDF.
    Returns a list of dicts: [{'text': str, 'metadata': dict}, ...]
    """
    filename = os.path.basename(pdf_path)
    paper_meta = PAPERS_METADATA.get(filename, {
        "title": filename,
        "arxiv_id": "unknown",
        "version": "unknown"
    })

    doc = pymupdf.open(pdf_path)
    pages_data = []

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        raw_text = page.get_text("text")
        cleaned = clean_text(raw_text)

        if not cleaned:
            continue

        pages_data.append({
            "text": cleaned,
            "metadata": {
                "paper_title": paper_meta["title"],
                "arxiv_id": paper_meta["arxiv_id"],
                "version": paper_meta["version"],
                "page": page_idx + 1,  # 1-indexed for human readability in citations
                "source_file": filename
            }
        })

    doc.close()
    return pages_data


def load_all_papers(papers_dir: str = "data/papers") -> List[Dict[str, Any]]:
    """Loads all PDF papers in the specified directory."""
    all_pages = []
    for filename in os.listdir(papers_dir):
        if filename.endswith(".pdf"):
            full_path = os.path.join(papers_dir, filename)
            pages = load_paper_pages(full_path)
            all_pages.extend(pages)
            print(f"Loaded {len(pages)} pages from {filename}")
    return all_pages


if __name__ == "__main__":
    # Quick sanity test
    papers = load_all_papers()
    print(f"Total pages extracted across all papers: {len(papers)}")