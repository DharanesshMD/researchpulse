"""
Smart text chunker for processing research content.

Splits long documents into semantically meaningful chunks for embedding and RAG retrieval.
Supports fixed-size with overlap and sentence-boundary-aware strategies.
"""

from __future__ import annotations

import re
import hashlib
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class Chunk:
    """A text chunk with tracking metadata."""

    text: str
    index: int
    source_id: str = ""
    chunk_id: str = ""
    start_char: int = 0
    end_char: int = 0
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.chunk_id:
            hash_input = f"{self.source_id}:{self.index}:{self.text[:64]}"
            self.chunk_id = hashlib.sha256(hash_input.encode()).hexdigest()[:16]


# Sentence-ending patterns
_SENTENCE_ENDINGS = re.compile(r"(?<=[.!?])\s+")
_PARAGRAPH_BREAK = re.compile(r"\n\s*\n")


class TextChunker:
    """
    Split text into chunks for embedding.

    Strategies:
    - "fixed": Fixed-size character windows with overlap.
    - "sentence": Sentence-boundary aware chunking — fills chunks up to
      chunk_size but never splits mid-sentence.
    """

    def __init__(
        self,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
        strategy: Literal["fixed", "sentence"] = "sentence",
    ) -> None:
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.strategy = strategy

    def chunk(self, text: str) -> list[str]:
        """Split text into plain string chunks."""
        if not text or not text.strip():
            return []

        if self.strategy == "sentence":
            return self._chunk_by_sentence(text)
        return self._chunk_fixed(text)

    def chunk_with_metadata(self, text: str, source_id: str) -> list[Chunk]:
        """Split text into Chunk objects with source tracking metadata."""
        if not text or not text.strip():
            return []

        if self.strategy == "sentence":
            raw_chunks = self._chunk_by_sentence_with_positions(text)
        else:
            raw_chunks = self._chunk_fixed_with_positions(text)

        return [
            Chunk(
                text=chunk_text,
                index=i,
                source_id=source_id,
                start_char=start,
                end_char=end,
            )
            for i, (chunk_text, start, end) in enumerate(raw_chunks)
        ]

    # ------------------------------------------------------------------
    # Fixed-size chunking
    # ------------------------------------------------------------------

    def _chunk_fixed(self, text: str) -> list[str]:
        """Fixed-size character windows with overlap."""
        chunks: list[str] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            start += self.chunk_size - self.chunk_overlap

        return chunks

    def _chunk_fixed_with_positions(self, text: str) -> list[tuple[str, int, int]]:
        """Fixed-size with position tracking."""
        chunks: list[tuple[str, int, int]] = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = min(start + self.chunk_size, text_len)
            chunk = text[start:end].strip()
            if chunk:
                chunks.append((chunk, start, end))
            start += self.chunk_size - self.chunk_overlap

        return chunks

    # ------------------------------------------------------------------
    # Sentence-boundary chunking
    # ------------------------------------------------------------------

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences, preserving paragraph structure."""
        # First split by paragraphs, then by sentences within each
        paragraphs = _PARAGRAPH_BREAK.split(text)
        sentences: list[str] = []

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            # Split paragraph into sentences
            para_sentences = _SENTENCE_ENDINGS.split(para)
            for sent in para_sentences:
                sent = sent.strip()
                if sent:
                    sentences.append(sent)

        return sentences

    def _chunk_by_sentence(self, text: str) -> list[str]:
        """Sentence-boundary-aware chunking."""
        sentences = self._split_into_sentences(text)
        if not sentences:
            return [text.strip()] if text.strip() else []

        chunks: list[str] = []
        current_chunk: list[str] = []
        current_length = 0

        for sentence in sentences:
            sentence_len = len(sentence)

            # If a single sentence exceeds chunk_size, force-split it
            if sentence_len > self.chunk_size:
                # Flush current chunk first
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_length = 0

                # Split the long sentence with fixed strategy
                for i in range(0, sentence_len, self.chunk_size - self.chunk_overlap):
                    part = sentence[i : i + self.chunk_size].strip()
                    if part:
                        chunks.append(part)
                continue

            # Would adding this sentence exceed the limit?
            new_length = current_length + sentence_len + (1 if current_chunk else 0)
            if new_length > self.chunk_size and current_chunk:
                # Flush current chunk
                chunks.append(" ".join(current_chunk))

                # Overlap: carry over the last sentence(s) that fit within overlap
                overlap_sentences: list[str] = []
                overlap_len = 0
                for prev_sent in reversed(current_chunk):
                    if overlap_len + len(prev_sent) + 1 <= self.chunk_overlap:
                        overlap_sentences.insert(0, prev_sent)
                        overlap_len += len(prev_sent) + 1
                    else:
                        break

                current_chunk = overlap_sentences
                current_length = sum(len(s) for s in current_chunk) + max(0, len(current_chunk) - 1)

            current_chunk.append(sentence)
            current_length += sentence_len + (1 if len(current_chunk) > 1 else 0)

        # Flush remaining
        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks

    def _chunk_by_sentence_with_positions(self, text: str) -> list[tuple[str, int, int]]:
        """Sentence-boundary chunking with character positions."""
        chunks = self._chunk_by_sentence(text)
        result: list[tuple[str, int, int]] = []
        search_start = 0

        for chunk in chunks:
            # Find the first sentence of this chunk in the original text
            # to get an approximate position
            first_words = chunk[:50]
            pos = text.find(first_words, search_start)
            if pos == -1:
                pos = search_start

            start = pos
            end = min(start + len(chunk), len(text))
            result.append((chunk, start, end))
            search_start = max(search_start, start + 1)

        return result
