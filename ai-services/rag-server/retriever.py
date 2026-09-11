"""Retrieval for the shared RAG server: chunking plus BM25 ranking.

No embedding model and no vector database. The corpus is a small curated set of
markdown files, and BM25 over it is both good enough and fully explainable -
every score in a citation can be traced back to term frequencies in a named
file, which matters when the retrieval has to be defended in the Q&A.

It also keeps the server dependency-free and instant to start, which is the
difference between the demo working on an 8 GB laptop and not.
"""

import math
import re
from pathlib import Path

KNOWLEDGE_DIR = Path(__file__).resolve().parent / "knowledge"

# BM25 parameters. k1 controls how fast term frequency saturates, b how much
# document length is penalised. These are the standard defaults.
K1 = 1.5
B = 0.75

# Short function words carry no retrieval signal but do inflate scores on long
# chunks, so they are dropped at both index and query time.
STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for",
    "from", "has", "have", "how", "i", "if", "in", "is", "it", "its", "me", "my",
    "of", "on", "or", "that", "the", "this", "to", "was", "what", "when", "where",
    "which", "who", "why", "will", "with", "you", "your",
}

TARGET_CHUNK_WORDS = 120


def tokenise(text):
    return [
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if token not in STOPWORDS and len(token) > 1
    ]


def _split_into_chunks(text):
    """Split one markdown file on its headings, then on size.

    Headings are kept because they become the `section` field of a citation -
    "travel/trips.md > Budget planning" is a far more useful source than a
    bare file name and a chunk number.
    """
    chunks = []
    section = "Introduction"
    buffer = []

    def flush():
        if not buffer:
            return
        body = " ".join(" ".join(buffer).split())
        if body:
            chunks.append((section, body))
        buffer.clear()

    for line in text.splitlines():
        heading = re.match(r"^#{1,6}\s+(.*)$", line.strip())
        if heading:
            flush()
            section = heading.group(1).strip()
            continue

        if not line.strip():
            # A blank line only ends a chunk once it is big enough, so single
            # sentences do not become their own unrankable fragments.
            if sum(len(part.split()) for part in buffer) >= TARGET_CHUNK_WORDS:
                flush()
            continue

        buffer.append(line.strip())

    flush()
    return chunks


class Index:
    """An in-memory BM25 index over the knowledge directory."""

    def __init__(self, knowledge_dir=KNOWLEDGE_DIR):
        self.knowledge_dir = Path(knowledge_dir)
        self.chunks = []
        self.document_frequency = {}
        self.average_length = 0.0
        self.build()

    def build(self):
        self.chunks = []

        for path in sorted(self.knowledge_dir.rglob("*.md")):
            source = path.relative_to(self.knowledge_dir).as_posix()
            text = path.read_text(encoding="utf-8")
            for number, (section, body) in enumerate(_split_into_chunks(text), start=1):
                tokens = tokenise(f"{section} {body}")
                if not tokens:
                    continue
                frequencies = {}
                for token in tokens:
                    frequencies[token] = frequencies.get(token, 0) + 1
                self.chunks.append(
                    {
                        "source": source,
                        "section": section,
                        "chunk": number,
                        "text": body,
                        "length": len(tokens),
                        "frequencies": frequencies,
                    }
                )

        self.document_frequency = {}
        for chunk in self.chunks:
            for token in chunk["frequencies"]:
                self.document_frequency[token] = self.document_frequency.get(token, 0) + 1

        total = sum(chunk["length"] for chunk in self.chunks)
        self.average_length = (total / len(self.chunks)) if self.chunks else 0.0

    def _idf(self, token):
        appearances = self.document_frequency.get(token, 0)
        if appearances == 0:
            return 0.0
        total = len(self.chunks)
        return math.log(1 + (total - appearances + 0.5) / (appearances + 0.5))

    def search(self, question, top_k=4):
        """Return the top_k chunks for a question, each with its BM25 score."""
        query_tokens = tokenise(question)
        if not query_tokens or not self.chunks:
            return []

        scored = []
        for chunk in self.chunks:
            score = 0.0
            matched = set()
            for token in query_tokens:
                frequency = chunk["frequencies"].get(token)
                if not frequency:
                    continue
                matched.add(token)
                normaliser = K1 * (
                    1 - B + B * chunk["length"] / (self.average_length or 1)
                )
                score += self._idf(token) * frequency * (K1 + 1) / (frequency + normaliser)

            if score > 0:
                scored.append(
                    {
                        "source": chunk["source"],
                        "section": chunk["section"],
                        "chunk": chunk["chunk"],
                        "text": chunk["text"],
                        "score": round(score, 4),
                        # The share of the question actually covered by this
                        # chunk. Score alone rewards one rare term; coverage is
                        # what separates a real answer from a lucky keyword.
                        "coverage": round(len(matched) / len(set(query_tokens)), 3),
                    }
                )

        scored.sort(key=lambda item: item["score"], reverse=True)
        return scored[:top_k]

    def stats(self):
        sources = sorted({chunk["source"] for chunk in self.chunks})
        return {
            "chunks": len(self.chunks),
            "sources": sources,
            "source_count": len(sources),
            "vocabulary": len(self.document_frequency),
            "average_chunk_tokens": round(self.average_length, 1),
        }
