"""
Document parsing for private training.

Extracts text chunks from PDF, DOCX, and Markdown files.
Chunks are sized for embedding (~500 tokens / 1500 chars).
"""

import logging
import re
from pathlib import Path

logger = logging.getLogger("wavestreamer_runner.document_parser")

MAX_CHUNK_CHARS = 1500  # ~500 tokens


def parse_document(file_path: Path, doc_type: str = "auto") -> tuple[str, list[str]]:
    """Parse a document into text chunks.

    Args:
        file_path: Path to the document.
        doc_type: "pdf", "docx", "md", "txt", or "auto" (detect from extension).

    Returns:
        (detected_type, list_of_text_chunks)
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Document not found: {path}")

    if doc_type == "auto":
        ext = path.suffix.lower()
        type_map = {".pdf": "pdf", ".docx": "docx", ".md": "md", ".markdown": "md", ".txt": "txt"}
        doc_type = type_map.get(ext, "txt")

    parsers = {"pdf": _parse_pdf, "docx": _parse_docx, "md": _parse_markdown, "txt": _parse_text}
    parser = parsers.get(doc_type, _parse_text)

    raw_chunks = parser(path)

    # Re-chunk to enforce size limit
    chunks = []
    for chunk in raw_chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        if len(chunk) <= MAX_CHUNK_CHARS:
            chunks.append(chunk)
        else:
            chunks.extend(_split_long_chunk(chunk))

    return doc_type, chunks


def _parse_pdf(path: Path) -> list[str]:
    """Extract text from PDF, one chunk per page."""
    try:
        import fitz  # pymupdf
    except ImportError:
        raise ImportError("PDF support requires pymupdf: pip install pymupdf")

    doc = fitz.open(str(path))
    pages = []
    for page in doc:
        text = page.get_text().strip()
        if text:
            pages.append(text)
    doc.close()
    return pages


def _parse_docx(path: Path) -> list[str]:
    """Extract text from DOCX, one chunk per section (grouped paragraphs)."""
    try:
        from docx import Document
    except ImportError:
        raise ImportError("DOCX support requires python-docx: pip install python-docx")

    doc = Document(str(path))
    chunks = []
    current = []

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            # Empty paragraph = section break
            if current:
                chunks.append("\n".join(current))
                current = []
            continue
        current.append(text)

    if current:
        chunks.append("\n".join(current))

    return chunks


def _parse_markdown(path: Path) -> list[str]:
    """Extract text from Markdown, one chunk per heading section."""
    text = path.read_text(encoding="utf-8")
    # Split on headings (# ## ### etc.)
    sections = re.split(r"(?m)^(#{1,4}\s+.+)$", text)

    chunks = []
    current = ""
    for part in sections:
        part = part.strip()
        if not part:
            continue
        if re.match(r"^#{1,4}\s+", part):
            # This is a heading — start new chunk
            if current:
                chunks.append(current)
            current = part
        else:
            if current:
                current += "\n\n" + part
            else:
                current = part

    if current:
        chunks.append(current)

    return chunks


def _parse_text(path: Path) -> list[str]:
    """Extract text from plain text, split on double newlines."""
    text = path.read_text(encoding="utf-8")
    paragraphs = text.split("\n\n")
    chunks = []
    current = ""
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(current) + len(para) + 2 > MAX_CHUNK_CHARS and current:
            chunks.append(current)
            current = para
        else:
            current = current + "\n\n" + para if current else para

    if current:
        chunks.append(current)

    return chunks


def _split_long_chunk(text: str) -> list[str]:
    """Split a chunk that exceeds MAX_CHUNK_CHARS at paragraph or sentence boundaries."""
    # Try paragraph split first
    paragraphs = text.split("\n\n")
    if len(paragraphs) > 1:
        chunks = []
        current = ""
        for para in paragraphs:
            if len(current) + len(para) + 2 > MAX_CHUNK_CHARS and current:
                chunks.append(current.strip())
                current = para
            else:
                current = current + "\n\n" + para if current else para
        if current:
            chunks.append(current.strip())
        return chunks

    # Fall back to sentence split
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 > MAX_CHUNK_CHARS and current:
            chunks.append(current.strip())
            current = sent
        else:
            current = current + " " + sent if current else sent
    if current:
        chunks.append(current.strip())

    return chunks


def supported_extensions() -> list[str]:
    """Return list of supported file extensions."""
    return [".pdf", ".docx", ".md", ".markdown", ".txt"]
