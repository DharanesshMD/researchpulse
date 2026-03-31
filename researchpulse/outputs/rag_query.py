"""
RAG (Retrieval-Augmented Generation) query interface.

Allows natural language questions across the entire research knowledge base.
Pipeline: query → embed → vector search → context assembly → LLM answer with citations.
"""

from __future__ import annotations

import os
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel

from researchpulse.config import LLMConfig, ResearchPulseConfig, get_config
from researchpulse.pipeline.embedder import EmbeddingGenerator
from researchpulse.storage.vector_store import VectorStore
from researchpulse.utils.logging import get_logger

logger = get_logger("outputs.rag")

RAG_SYSTEM_PROMPT = """\
You are a research assistant with access to a knowledge base of academic papers, \
GitHub repositories, news articles, and Reddit discussions.

Answer the user's question based ONLY on the provided context. If the context \
doesn't contain enough information, say so honestly — do not make up facts.

Rules:
- Be specific, technical, and concise.
- Reference sources by their title when citing information.
- If multiple sources discuss the topic, synthesize the information.
- Format your answer with clear paragraphs. Use bullet points for lists.
"""

RAG_USER_TEMPLATE = """\
Question: {question}

Context (retrieved from knowledge base):
{context}

Answer the question based on the context above. Cite sources by title.
"""


def _create_llm(config: LLMConfig) -> BaseChatModel:
    """Create the appropriate LangChain LLM from config."""
    if config.provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=config.anthropic.model,
            max_tokens=config.anthropic.max_tokens,
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
        )
    else:
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.openai.model,
            max_tokens=config.openai.max_tokens,
            api_key=os.environ.get("OPENAI_API_KEY", ""),
        )


def _format_context(results: list[dict[str, Any]]) -> str:
    """Format vector search results into a context string for the LLM."""
    if not results:
        return "No relevant documents found."

    parts = []
    for i, item in enumerate(results, 1):
        title = item.get("title", "Untitled")
        source = item.get("source", "unknown")
        content = item.get("content_preview", "")
        summary = item.get("summary", "")
        url = item.get("url", "")
        score = item.get("score", 0.0)

        text = summary if summary else content
        parts.append(
            f"[{i}] {title} ({source}, relevance: {score:.2f})\n"
            f"URL: {url}\n"
            f"{text}\n"
        )

    return "\n---\n".join(parts)


class RAGQuery:
    """
    RAG-based question answering over the research knowledge base.

    Pipeline: query → embed → vector search → context assembly → LLM answer
    """

    def __init__(
        self,
        config: ResearchPulseConfig | None = None,
        top_k: int | None = None,
    ) -> None:
        self.config = config or get_config()
        self.top_k = top_k or self.config.outputs.rag.top_k

        self._embedder = EmbeddingGenerator.from_config(self.config.llm)
        self._vector_store = VectorStore.from_config(
            self.config.vector_store,
            embedding_dim=self._embedder.dimensions,
        )
        self._llm = _create_llm(self.config.llm)

    async def ask(
        self,
        question: str,
        source_filter: str | None = None,
        top_k: int | None = None,
    ) -> dict[str, Any]:
        """
        Answer a question using RAG.

        Args:
            question: The natural language question.
            source_filter: Optional filter by source (arxiv, github, news, reddit).
            top_k: Override the default number of results to retrieve.

        Returns:
            {
                "answer": "The generated answer...",
                "sources": [{"title": "...", "url": "...", "score": 0.9}],
                "question": "The original question",
            }
        """
        if not question or not question.strip():
            return {"answer": "Please provide a question.", "sources": [], "question": ""}

        k = top_k or self.top_k
        logger.info("RAG query", question=question[:100], top_k=k)

        # Step 1: Embed the query
        query_embedding = await self._embedder.embed(question)

        # Step 2: Vector search
        search_results = await self._vector_store.search(
            query_embedding=query_embedding,
            top_k=k,
            source_filter=source_filter,
        )

        if not search_results:
            return {
                "answer": "I couldn't find any relevant information in the knowledge base for your question.",
                "sources": [],
                "question": question,
            }

        # Step 3: Assemble context
        context = _format_context(search_results)

        # Step 4: LLM generation
        user_message = RAG_USER_TEMPLATE.format(
            question=question,
            context=context,
        )

        response = await self._llm.ainvoke([
            SystemMessage(content=RAG_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ])

        answer = response.content

        # Step 5: Format sources
        sources = [
            {
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "source": r.get("source", ""),
                "score": r.get("score", 0.0),
            }
            for r in search_results
        ]

        logger.info("RAG answer generated", sources_count=len(sources))

        return {
            "answer": answer,
            "sources": sources,
            "question": question,
        }

    async def close(self) -> None:
        """Clean up resources."""
        await self._embedder.close()
        await self._vector_store.close()
