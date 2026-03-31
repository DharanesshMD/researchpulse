"""
Pipeline orchestrator — chains all processing steps together.

Flow: ScrapedItems → chunk → embed → summarize → classify → dedup → store

Integrates all Phase 2 pipeline components into a single run_pipeline() function
that can be called from the CLI or scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from researchpulse.config import ResearchPulseConfig, get_config
from researchpulse.pipeline.chunker import TextChunker
from researchpulse.pipeline.classifier import TopicClassifier
from researchpulse.pipeline.deduplicator import SemanticDeduplicator
from researchpulse.pipeline.embedder import EmbeddingGenerator
from researchpulse.pipeline.summarizer import Summarizer
from researchpulse.scrapers.models import ScrapedItem
from researchpulse.utils.logging import get_logger

logger = get_logger("pipeline.orchestrator")


@dataclass
class PipelineResult:
    """Result of a full pipeline run."""

    total_input: int = 0
    total_chunks: int = 0
    total_after_dedup: int = 0
    total_summarized: int = 0
    total_classified: int = 0
    total_embedded: int = 0
    total_stored: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.total_stored > 0 or (self.total_input == 0 and not self.errors)


@dataclass
class ProcessedItem:
    """An item that has been through the full pipeline."""

    # Original fields
    title: str = ""
    url: str = ""
    source: str = ""
    content: str = ""
    published_at: str | None = None
    tags: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    # Pipeline-added fields
    summary: str = ""
    entities: list[str] = field(default_factory=list)
    key_findings: list[str] = field(default_factory=list)
    topic: str = "Other"
    topic_confidence: float = 0.0
    relevance_score: float = 0.0
    embedding: list[float] = field(default_factory=list)
    chunks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "source": self.source,
            "content": self.content,
            "published_at": self.published_at,
            "tags": self.tags,
            "summary": self.summary,
            "entities": self.entities,
            "key_findings": self.key_findings,
            "topic": self.topic,
            "topic_confidence": self.topic_confidence,
            "relevance_score": self.relevance_score,
            "chunk_index": 0,
            "source_id": self.url,
        }


class Pipeline:
    """
    Full processing pipeline orchestrator.

    Chains: chunk → embed → summarize → classify → dedup → store
    Each step is optional and can be skipped via config or flags.
    """

    def __init__(self, config: ResearchPulseConfig | None = None) -> None:
        self.config = config or get_config()

        # Initialize components
        self.chunker = TextChunker(
            chunk_size=self.config.outputs.rag.chunk_size,
            chunk_overlap=self.config.outputs.rag.chunk_overlap,
        )
        self.embedder = EmbeddingGenerator.from_config(self.config.llm)
        self.summarizer = Summarizer.from_config(self.config.llm)
        self.classifier = TopicClassifier.from_config(
            self.config.llm,
            self.config.interests,
        )
        self.deduplicator = SemanticDeduplicator(similarity_threshold=0.92)

    async def process(
        self,
        items: list[ScrapedItem],
        skip_summary: bool = False,
        skip_classify: bool = False,
        skip_dedup: bool = False,
        skip_embed: bool = False,
    ) -> tuple[list[ProcessedItem], PipelineResult]:
        """
        Run the full processing pipeline on a batch of scraped items.

        Args:
            items: List of ScrapedItem from scrapers.
            skip_summary: Skip LLM summarization step.
            skip_classify: Skip LLM classification step.
            skip_dedup: Skip semantic deduplication step.
            skip_embed: Skip embedding generation step.

        Returns:
            Tuple of (processed_items, pipeline_result).
        """
        result = PipelineResult(total_input=len(items))

        if not items:
            logger.info("Pipeline: no items to process")
            return [], result

        logger.info("Pipeline started", items=len(items))

        # -----------------------------------------------------------
        # Step 1: Convert ScrapedItems to ProcessedItems
        # -----------------------------------------------------------
        processed = [self._to_processed(item) for item in items]

        # -----------------------------------------------------------
        # Step 2: Chunk content (for RAG — stored alongside embeddings)
        # -----------------------------------------------------------
        for item in processed:
            if item.content:
                item.chunks = self.chunker.chunk(item.content)
            result.total_chunks += len(item.chunks) if item.chunks else 1

        logger.info("Chunking complete", total_chunks=result.total_chunks)

        # -----------------------------------------------------------
        # Step 3: Generate embeddings (on full content, not chunks)
        # -----------------------------------------------------------
        if not skip_embed:
            try:
                # Embed each item's full content (title + content)
                texts_to_embed = [
                    f"{p.title}\n\n{p.content[:4000]}" for p in processed
                ]
                all_embeddings = await self.embedder.embed_batch(texts_to_embed)

                for item, emb in zip(processed, all_embeddings):
                    item.embedding = emb

                result.total_embedded = len(all_embeddings)
                logger.info("Embedding complete", count=result.total_embedded)
            except Exception as e:
                err = f"Embedding failed: {e}"
                logger.error(err)
                result.errors.append(err)

        # -----------------------------------------------------------
        # Step 4: Semantic deduplication
        # -----------------------------------------------------------
        if not skip_dedup and not skip_embed and all(p.embedding for p in processed):
            try:
                item_dicts = [p.to_dict() for p in processed]
                embeddings = [p.embedding for p in processed]

                deduped_dicts = await self.deduplicator.deduplicate(item_dicts, embeddings)

                # Map back to ProcessedItems by URL
                deduped_urls = {d["url"] for d in deduped_dicts}
                processed = [p for p in processed if p.url in deduped_urls]

                result.total_after_dedup = len(processed)
                logger.info(
                    "Deduplication complete",
                    before=result.total_input,
                    after=result.total_after_dedup,
                )
            except Exception as e:
                err = f"Deduplication failed: {e}"
                logger.error(err)
                result.errors.append(err)
                result.total_after_dedup = len(processed)
        else:
            result.total_after_dedup = len(processed)

        # -----------------------------------------------------------
        # Step 5: LLM Summarization
        # -----------------------------------------------------------
        if not skip_summary:
            try:
                batch_input = [
                    {"text": p.content, "title": p.title, "source": p.source}
                    for p in processed
                ]
                summaries = await self.summarizer.summarize_batch(batch_input)

                for item, summary in zip(processed, summaries):
                    item.summary = summary.get("summary", "")
                    item.entities = summary.get("entities", [])
                    item.key_findings = summary.get("key_findings", [])

                result.total_summarized = sum(1 for s in summaries if s.get("summary"))
                logger.info("Summarization complete", count=result.total_summarized)
            except Exception as e:
                err = f"Summarization failed: {e}"
                logger.error(err)
                result.errors.append(err)

        # -----------------------------------------------------------
        # Step 6: Topic Classification
        # -----------------------------------------------------------
        if not skip_classify:
            try:
                batch_input = [
                    {"text": p.content, "title": p.title, "source": p.source}
                    for p in processed
                ]
                classifications = await self.classifier.classify_batch(batch_input)

                for item, cls_result in zip(processed, classifications):
                    item.topic = cls_result.get("topic", "Other")
                    item.topic_confidence = cls_result.get("confidence", 0.0)
                    item.relevance_score = cls_result.get("relevance_score", 0.0)

                result.total_classified = sum(1 for c in classifications if c.get("topic") != "Other")
                logger.info("Classification complete", count=result.total_classified)
            except Exception as e:
                err = f"Classification failed: {e}"
                logger.error(err)
                result.errors.append(err)

        logger.info(
            "Pipeline complete",
            input=result.total_input,
            after_dedup=result.total_after_dedup,
            summarized=result.total_summarized,
            classified=result.total_classified,
            errors=len(result.errors),
        )

        return processed, result

    async def process_and_store(
        self,
        items: list[ScrapedItem],
        **kwargs: Any,
    ) -> PipelineResult:
        """
        Run the pipeline and store results in both PostgreSQL and Qdrant.

        Args:
            items: List of ScrapedItem from scrapers.
            **kwargs: Passed to process().

        Returns:
            PipelineResult with storage counts.
        """
        from researchpulse.storage.database import Database
        from researchpulse.storage.repository import scraped_item_to_model
        from researchpulse.storage.vector_store import VectorStore

        processed, result = await self.process(items, **kwargs)

        if not processed:
            return result

        # Store in PostgreSQL
        try:
            db = Database(self.config.database.url)
            await db.create_tables()

            async with db.session() as session:
                stored_count = 0
                for proc_item, orig_item in zip(processed, items):
                    model = scraped_item_to_model(orig_item)
                    # Update with pipeline results
                    model.summary = proc_item.summary
                    model.relevance_score = proc_item.relevance_score
                    model.tags = proc_item.tags or model.tags

                    from researchpulse.storage.repository import BaseRepository
                    repo = BaseRepository(type(model), session)
                    existing = await repo.get_by_url(model.url)
                    if existing is None:
                        session.add(model)
                        stored_count += 1

                await session.flush()
                result.total_stored = stored_count

            await db.close()
            logger.info("PostgreSQL storage complete", stored=stored_count)
        except Exception as e:
            err = f"PostgreSQL storage failed: {e}"
            logger.error(err)
            result.errors.append(err)

        # Store embeddings in Qdrant
        if any(p.embedding for p in processed):
            try:
                vs = VectorStore.from_config(
                    self.config.vector_store,
                    embedding_dim=self.embedder.dimensions,
                )
                item_dicts = [p.to_dict() for p in processed]
                embeddings = [p.embedding for p in processed]

                await vs.store_embeddings(item_dicts, embeddings)
                await vs.close()
                logger.info("Qdrant storage complete", count=len(embeddings))
            except Exception as e:
                err = f"Qdrant storage failed: {e}"
                logger.error(err)
                result.errors.append(err)

        return result

    @staticmethod
    def _to_processed(item: ScrapedItem) -> ProcessedItem:
        """Convert a ScrapedItem to a ProcessedItem."""
        return ProcessedItem(
            title=item.title,
            url=item.url,
            source=item.source,
            content=item.content,
            published_at=item.published_at.isoformat() if item.published_at else None,
            tags=",".join(item.tags) if item.tags else "",
            extra=item.extra,
        )
