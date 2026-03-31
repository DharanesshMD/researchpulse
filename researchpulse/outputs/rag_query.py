"""
RAG (Retrieval-Augmented Generation) query interface (Phase 3).

Will allow natural language questions across the entire
research knowledge base using vector similarity + LLM.
"""

from __future__ import annotations


class RAGQuery:
    """
    RAG-based question answering over the research knowledge base.

    Pipeline: query → embed → vector search → context assembly → LLM answer
    """

    def __init__(self, top_k: int = 10) -> None:
        self.top_k = top_k

    async def ask(self, question: str) -> dict:
        """
        Answer a question using RAG.

        Returns:
            {
                "answer": "The generated answer...",
                "sources": [{"title": "...", "url": "...", "relevance": 0.9}],
            }
        """
        raise NotImplementedError("RAG query is implemented in Phase 3")
