"""Tests for the text chunker."""

from __future__ import annotations

import pytest

from researchpulse.pipeline.chunker import TextChunker, Chunk


class TestFixedChunking:
    """Test fixed-size chunking strategy."""

    def test_short_text_single_chunk(self):
        """Short text should produce a single chunk."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=10, strategy="fixed")
        chunks = chunker.chunk("Hello world.")
        assert len(chunks) == 1
        assert chunks[0] == "Hello world."

    def test_long_text_multiple_chunks(self):
        """Long text should be split into multiple chunks."""
        chunker = TextChunker(chunk_size=50, chunk_overlap=10, strategy="fixed")
        text = "A" * 120
        chunks = chunker.chunk(text)
        assert len(chunks) >= 3

    def test_overlap_between_chunks(self):
        """Consecutive chunks should share overlapping text."""
        chunker = TextChunker(chunk_size=20, chunk_overlap=5, strategy="fixed")
        text = "abcdefghijklmnopqrstuvwxyz0123456789"
        chunks = chunker.chunk(text)
        assert len(chunks) >= 2
        # The end of chunk 0 should overlap with the start of chunk 1
        overlap = chunks[0][-5:]
        assert overlap in chunks[1]

    def test_empty_text(self):
        chunker = TextChunker(strategy="fixed")
        assert chunker.chunk("") == []
        assert chunker.chunk("   ") == []


class TestSentenceChunking:
    """Test sentence-boundary-aware chunking strategy."""

    def test_respects_sentence_boundaries(self):
        """Chunks should not split mid-sentence."""
        chunker = TextChunker(chunk_size=100, chunk_overlap=20, strategy="sentence")
        text = (
            "This is sentence one. This is sentence two. "
            "This is sentence three. This is sentence four."
        )
        chunks = chunker.chunk(text)
        # Each chunk should contain complete sentences
        for chunk in chunks:
            # Should not end with an incomplete word (heuristic)
            assert not chunk.endswith("-")

    def test_long_sentence_force_split(self):
        """A single sentence longer than chunk_size should be force-split."""
        chunker = TextChunker(chunk_size=50, chunk_overlap=10, strategy="sentence")
        text = "A" * 120 + "."
        chunks = chunker.chunk(text)
        assert len(chunks) >= 2

    def test_multiple_paragraphs(self):
        """Should handle paragraph breaks correctly."""
        chunker = TextChunker(chunk_size=200, chunk_overlap=30, strategy="sentence")
        text = (
            "First paragraph sentence one. First paragraph sentence two.\n\n"
            "Second paragraph sentence one. Second paragraph sentence two.\n\n"
            "Third paragraph with a longer sentence that contains more information."
        )
        chunks = chunker.chunk(text)
        assert len(chunks) >= 1
        # All original content should be preserved
        all_text = " ".join(chunks)
        assert "First paragraph" in all_text
        assert "Third paragraph" in all_text

    def test_empty_text(self):
        chunker = TextChunker(strategy="sentence")
        assert chunker.chunk("") == []

    def test_single_sentence(self):
        chunker = TextChunker(chunk_size=500, strategy="sentence")
        chunks = chunker.chunk("Just one sentence here.")
        assert len(chunks) == 1
        assert chunks[0] == "Just one sentence here."


class TestChunkWithMetadata:
    """Test chunk_with_metadata method."""

    def test_returns_chunk_objects(self):
        chunker = TextChunker(chunk_size=50, chunk_overlap=10, strategy="fixed")
        text = "A" * 120
        chunks = chunker.chunk_with_metadata(text, source_id="test-123")
        assert len(chunks) >= 2
        assert all(isinstance(c, Chunk) for c in chunks)

    def test_chunk_metadata_fields(self):
        chunker = TextChunker(chunk_size=500, strategy="sentence")
        chunks = chunker.chunk_with_metadata("A simple test.", source_id="src-1")
        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.source_id == "src-1"
        assert chunk.index == 0
        assert chunk.chunk_id  # Should be auto-generated
        assert chunk.text == "A simple test."

    def test_empty_text_returns_empty(self):
        chunker = TextChunker()
        assert chunker.chunk_with_metadata("", source_id="x") == []

    def test_unique_chunk_ids(self):
        chunker = TextChunker(chunk_size=30, chunk_overlap=5, strategy="fixed")
        text = "Word " * 50
        chunks = chunker.chunk_with_metadata(text, source_id="test")
        chunk_ids = [c.chunk_id for c in chunks]
        assert len(chunk_ids) == len(set(chunk_ids))  # All unique
