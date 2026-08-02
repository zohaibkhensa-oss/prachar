"""Document processing pipeline for the Business Knowledge Hub.

This module ingests uploaded documents (PDF, Word, Excel, PowerPoint, CSV,
images, plain text, HTML, URLs and YouTube transcripts) and converts them into
clean, searchable text chunks ready for embedding and retrieval.

Design goals
------------
* **Zero hard dependencies** — every optional parser degrades gracefully when
  its third-party library is not installed, returning a clear, actionable error
  message instead of crashing.
* **Pure-Python first** — text, CSV, HTML and URL parsing use only the standard
  library.
* **Production quality** — structured dataclasses, per-stage logging, defensive
  error handling and a single :class:`ProcessingResult` envelope for callers.

The pipeline has four stages:

1. **Parsing** — extract text per page into :class:`ParsedPage` objects.
2. **Cleaning** — normalise whitespace, fix encoding artefacts, strip noise.
3. **Chunking** — split pages into overlapping :class:`TextChunk` objects.
4. **Metadata extraction** — page numbers, sections, titles and language hints
   are attached to every page and chunk.
"""

from __future__ import annotations

import csv
import html
import io
import logging
import os
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class ParsedPage:
    """A single page (or logical unit) of parsed document content.

    Attributes:
        page_number: 1-indexed page number (for non-paginated formats this is
            a monotonically increasing counter over the parsed units).
        text: Raw-ish text extracted for the page. Cleaning is applied later.
        section: Optional section/heading title the page belongs to.
        metadata: Free-form per-page metadata (title, language, table count…).
    """

    page_number: int
    text: str
    section: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TextChunk:
    """A searchable chunk of text produced by the chunker.

    Attributes:
        content: The chunk text.
        chunk_index: Global index of the chunk across the whole document.
        page_number: Page this chunk originated from (first page if spanning).
        section: Section this chunk originated from, if any.
        token_count: Rough token estimate (``len(content) // 4``).
        metadata: Free-form per-chunk metadata.
    """

    content: str
    chunk_index: int
    page_number: int | None = None
    section: str | None = None
    token_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProcessingResult:
    """Envelope returned by :meth:`DocumentProcessor.process`.

    Attributes:
        success: Whether the full pipeline completed without fatal errors.
        pages: All parsed pages.
        chunks: All chunks produced from the pages.
        error: Human-readable error message when ``success`` is False.
        total_tokens: Sum of token counts across all chunks.
        file_type: Detected file type (e.g. ``"pdf"``, ``"word"``).
    """

    success: bool
    pages: list[ParsedPage] = field(default_factory=list)
    chunks: list[TextChunk] = field(default_factory=list)
    error: str = ""
    total_tokens: int = 0
    file_type: str = ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Minimal set of stopwords used by the (very light) language heuristic.
_STOPWORDS_EN = {
    "the", "and", "for", "are", "but", "not", "you", "all", "any", "can",
    "had", "her", "was", "one", "our", "out", "day", "get", "has", "him",
    "his", "how", "its", "may", "new", "now", "old", "see", "two", "way",
    "who", "boy", "did", "let", "say", "she", "too", "use",
}
_STOPWORDS_HI = {"और", "का", "की", "के", "में", "से", "है", "हैं", "को", "पर"}
_STOPWORDS_ES = {"el", "la", "de", "que", "y", "en", "los", "se", "las", "por"}


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 characters per token."""
    return max(0, len(text) // 4)


def _detect_language(text: str) -> str:
    """Best-effort language detection using script + stopword heuristics.

    Returns an ISO 639-1 code (``"en"``, ``"hi"``, ``"es"``) or ``"unknown"``.
    The heuristic is intentionally cheap — it only needs to be good enough to
    annotate metadata, not to drive downstream logic.
    """
    if not text:
        return "unknown"
    sample = text[:4000]
    # Devanagari range (Hindi, Marathi, etc.)
    if re.search(r"[\u0900-\u097F]", sample):
        return "hi"
    # CJK
    if re.search(r"[\u4e00-\u9fff]", sample):
        return "zh"
    # Arabic
    if re.search(r"[\u0600-\u06FF]", sample):
        return "ar"
    # Cyrillic
    if re.search(r"[\u0400-\u04FF]", sample):
        return "ru"
    # Latin — disambiguate EN vs ES via stopwords.
    words = re.findall(r"[a-zà-ÿ]+", sample.lower())
    if not words:
        return "unknown"
    word_set = set(words)
    en_hits = len(word_set & _STOPWORDS_EN)
    es_hits = len(word_set & _STOPWORDS_ES)
    if es_hits > en_hits:
        return "es"
    return "en"


def _import_optional(module: str):
    """Import a third-party module, returning ``None`` if unavailable."""
    try:
        return __import__(module)
    except Exception:  # noqa: BLE001 — import errors are expected here
        return None


# ---------------------------------------------------------------------------
# Document processor
# ---------------------------------------------------------------------------


class DocumentProcessor:
    """End-to-end document processing pipeline.

    The processor is stateless across calls — each :meth:`process` invocation
    is independent and safe to call concurrently from multiple threads/tasks
    (parsers themselves are responsible for their own thread-safety).
    """

    # Mapping from detected file type → internal parser method name.
    _PARSERS = {
        "pdf": "_parse_pdf",
        "word": "_parse_word",
        "excel": "_parse_excel",
        "powerpoint": "_parse_powerpoint",
        "csv": "_parse_csv",
        "image": "_parse_image",
        "text": "_parse_text",
        "html": "_parse_html",
        "url": "_parse_url",
        "youtube": "_parse_youtube",
    }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(
        self,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        file_type: str = "",
        url: str = "",
    ) -> ProcessingResult:
        """Run the full parse → clean → chunk pipeline.

        Exactly one of ``file_path``, ``file_bytes`` or ``url`` should be
        supplied. ``file_type`` may be omitted — it will be detected from the
        file name / URL / content.

        Returns a :class:`ProcessingResult` envelope. On failure, ``success``
        is ``False`` and ``error`` contains a human-readable message; partial
        results may still be present in ``pages``/``chunks``.
        """
        try:
            file_type = (file_type or "").strip().lower()
            if url:
                file_type = file_type or "url"
            elif file_path and not file_type:
                file_type = self.detect_file_type(file_path)
            elif file_bytes is not None and not file_type:
                file_type = "text"  # safest default for raw bytes

            if not file_type:
                return ProcessingResult(
                    success=False,
                    error="Could not determine file type. Pass file_type explicitly.",
                    file_type="",
                )

            pages = self.parse(
                file_path=file_path,
                file_bytes=file_bytes,
                file_type=file_type,
                url=url,
            )

            # If parsing produced no pages but no exception was raised, treat
            # it as a soft failure with a helpful message.
            if not pages:
                return ProcessingResult(
                    success=False,
                    error=f"No content extracted from {file_type} source.",
                    file_type=file_type,
                )

            # Clean each page in place.
            for page in pages:
                page.text = self.clean(page.text)
                page.metadata.setdefault("language", _detect_language(page.text))

            chunks = self.chunk(pages)
            total_tokens = sum(c.token_count for c in chunks)

            logger.info(
                "document_processor.processed file_type=%s pages=%d chunks=%d tokens=%d",
                file_type,
                len(pages),
                len(chunks),
                total_tokens,
            )

            return ProcessingResult(
                success=True,
                pages=pages,
                chunks=chunks,
                total_tokens=total_tokens,
                file_type=file_type,
            )
        except Exception as exc:  # noqa: BLE001 — top-level safety net
            logger.exception("document_processor.failed file_type=%s", file_type)
            return ProcessingResult(
                success=False,
                error=f"{type(exc).__name__}: {exc}",
                file_type=file_type,
            )

    def parse(
        self,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        file_type: str = "",
        url: str = "",
    ) -> list[ParsedPage]:
        """Dispatch to the correct parser and return parsed pages.

        Raises :class:`ValueError` for unsupported file types. Parser-specific
        failures (e.g. missing optional library) are returned as a single
        :class:`ParsedPage` whose ``text`` describes the issue, so callers can
        still obtain a result envelope.
        """
        file_type = (file_type or "").strip().lower()
        if url and not file_type:
            file_type = "url"
        if not file_type and file_path:
            file_type = self.detect_file_type(file_path)

        parser_name = self._PARSERS.get(file_type)
        if not parser_name:
            raise ValueError(
                f"Unsupported file type '{file_type}'. "
                f"Supported: {sorted(self._PARSERS)}"
            )

        parser = getattr(self, parser_name)
        logger.debug("document_processor.parse type=%s parser=%s", file_type, parser_name)
        return parser(file_path=file_path, file_bytes=file_bytes, url=url)

    def clean(self, text: str) -> str:
        """Normalise and de-noise extracted text.

        Steps:
        * Unicode NFKC normalisation.
        * Replace common smart quotes / bullets with ASCII equivalents.
        * Collapse runs of whitespace into single spaces.
        * Strip control characters except newlines/tabs.
        * Collapse 3+ newlines into 2 (paragraph breaks).
        """
        if not text:
            return ""

        # Normalise unicode then decode any HTML entities that survived parsing.
        text = unicodedata.normalize("NFKC", text)
        text = html.unescape(text)

        # Smart quotes / common bullets → ASCII.
        replacements = {
            "\u2018": "'", "\u2019": "'", "\u201c": '"', "\u201d": '"',
            "\u2013": "-", "\u2014": "-", "\u2026": "...",
            "\u2022": "-", "\u00b7": "-", "\u00a0": " ",
        }
        for src, dst in replacements.items():
            text = text.replace(src, dst)

        # Strip control chars except \n, \t, \r.
        text = "".join(
            ch for ch in text
            if ch in ("\n", "\t", "\r") or (ord(ch) >= 0x20 and ord(ch) != 0x7f)
        )

        # Collapse spaces/tabs on each line.
        lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.splitlines()]
        text = "\n".join(lines)

        # Collapse 3+ blank lines into a single blank line.
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def chunk(
        self,
        pages: list[ParsedPage],
        chunk_size: int = 1500,
        overlap: int = 200,
    ) -> list[TextChunk]:
        """Split parsed pages into overlapping chunks.

        Chunks are created per page to preserve page/section metadata. When a
        page's text is shorter than ``chunk_size`` it becomes a single chunk.
        The ``overlap`` parameter controls how many characters of the previous
        chunk are repeated at the start of the next one, preserving context.

        Args:
            pages: Parsed pages to chunk.
            chunk_size: Target chunk size in characters (1000–2000 recommended).
            overlap: Overlap between consecutive chunks in characters.

        Returns:
            A list of :class:`TextChunk` objects with global ``chunk_index``.
        """
        if chunk_size <= 0:
            raise ValueError("chunk_size must be positive")
        if overlap < 0 or overlap >= chunk_size:
            raise ValueError("overlap must be in [0, chunk_size)")
        if not pages:
            return []

        chunks: list[TextChunk] = []
        index = 0
        step = max(1, chunk_size - overlap)

        for page in pages:
            text = page.text or ""
            if not text:
                continue
            start = 0
            while start < len(text):
                end = min(len(text), start + chunk_size)
                piece = text[start:end]
                if piece.strip():
                    chunks.append(
                        TextChunk(
                            content=piece,
                            chunk_index=index,
                            page_number=page.page_number,
                            section=page.section or None,
                            token_count=_estimate_tokens(piece),
                            metadata=dict(page.metadata),
                        )
                    )
                    index += 1
                if end >= len(text):
                    break
                start += step

        logger.debug(
            "document_processor.chunked pages=%d chunks=%d chunk_size=%d overlap=%d",
            len(pages), len(chunks), chunk_size, overlap,
        )
        return chunks

    def detect_file_type(self, file_name: str, mime_type: str = "") -> str:
        """Detect a logical file type from a file name and/or MIME type.

        Returns one of the keys in :attr:`_PARSERS` (e.g. ``"pdf"``,
        ``"word"``). Falls back to ``"text"`` when no signal matches.
        """
        name = (file_name or "").lower()
        mime = (mime_type or "").lower()

        ext_map = {
            ".pdf": "pdf",
            ".docx": "word", ".doc": "word",
            ".xlsx": "excel", ".xls": "excel",
            ".pptx": "powerpoint", ".ppt": "powerpoint",
            ".csv": "csv",
            ".png": "image", ".jpg": "image", ".jpeg": "image",
            ".gif": "image", ".webp": "image", ".bmp": "image", ".tiff": "image",
            ".txt": "text", ".md": "text", ".markdown": "text", ".log": "text",
            ".html": "html", ".htm": "html",
        }
        for ext, ftype in ext_map.items():
            if name.endswith(ext):
                return ftype

        mime_map = {
            "application/pdf": "pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "word",
            "application/msword": "word",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "excel",
            "application/vnd.ms-excel": "excel",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation": "powerpoint",
            "application/vnd.ms-powerpoint": "powerpoint",
            "text/csv": "csv",
            "image/png": "image", "image/jpeg": "image", "image/gif": "image",
            "image/webp": "image", "image/bmp": "image", "image/tiff": "image",
            "text/plain": "text", "text/markdown": "text",
            "text/html": "html",
        }
        for m, ftype in mime_map.items():
            if mime == m:
                return ftype

        return "text"

    # ------------------------------------------------------------------
    # Parsers — PDF
    # ------------------------------------------------------------------

    def _parse_pdf(
        self,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        url: str = "",
    ) -> list[ParsedPage]:
        """Parse a PDF using PyPDF2 or pdfplumber if available.

        Falls back to a single instructional page asking the user to install
        one of the optional libraries.
        """
        data = self._read_bytes(file_path, file_bytes)
        if data is None:
            return self._missing_input("pdf")

        # Try pdfplumber first — generally better text quality.
        pdfplumber = _import_optional("pdfplumber")
        if pdfplumber is not None:
            try:
                pages: list[ParsedPage] = []
                with pdfplumber.open(io.BytesIO(data)) as pdf:
                    for i, page in enumerate(pdf.pages, start=1):
                        text = page.extract_text() or ""
                        pages.append(ParsedPage(
                            page_number=i,
                            text=text,
                            metadata={"parser": "pdfplumber"},
                        ))
                if pages:
                    return pages
            except Exception as exc:  # noqa: BLE001
                logger.warning("pdfplumber failed: %s — trying PyPDF2", exc)

        pypdf = _import_optional("PyPDF2") or _import_optional("pypdf")
        if pypdf is not None:
            try:
                reader = pypdf.PdfReader(io.BytesIO(data))
                pages = []
                for i, page in enumerate(reader.pages, start=1):
                    try:
                        text = page.extract_text() or ""
                    except Exception:  # noqa: BLE001
                        text = ""
                    pages.append(ParsedPage(
                        page_number=i,
                        text=text,
                        metadata={"parser": "pypdf"},
                    ))
                if pages:
                    return pages
            except Exception as exc:  # noqa: BLE001
                logger.warning("pypdf failed: %s", exc)

        return [ParsedPage(
            page_number=1,
            text=(
                "PDF parsing requires an optional library. "
                "Install one with: pip install pdfplumber  (recommended) "
                "or  pip install pypdf"
            ),
            metadata={"parser": "none", "missing_dependency": "pdfplumber|pypdf"},
        )]

    # ------------------------------------------------------------------
    # Parsers — Word
    # ------------------------------------------------------------------

    def _parse_word(
        self,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        url: str = "",
    ) -> list[ParsedPage]:
        """Parse a .docx file using python-docx if available."""
        data = self._read_bytes(file_path, file_bytes)
        if data is None:
            return self._missing_input("word")

        docx = _import_optional("docx")
        if docx is None:
            return [ParsedPage(
                page_number=1,
                text=(
                    "Word (.docx) parsing requires the optional library python-docx. "
                    "Install with: pip install python-docx"
                ),
                metadata={"missing_dependency": "python-docx"},
            )]

        try:
            document = docx.Document(io.BytesIO(data))
            # Group paragraphs into logical "pages" by heading boundaries so
            # that chunk metadata can carry section titles.
            pages: list[ParsedPage] = []
            current_section = ""
            buffer: list[str] = []
            page_no = 1

            def _flush() -> None:
                nonlocal page_no
                text = "\n".join(buffer).strip()
                if text:
                    pages.append(ParsedPage(
                        page_number=page_no,
                        text=text,
                        section=current_section,
                        metadata={"parser": "python-docx"},
                    ))
                    page_no += 1
                buffer.clear()

            for para in document.paragraphs:
                style = (para.style.name or "").lower() if para.style else ""
                if "heading" in style and para.text.strip():
                    _flush()
                    current_section = para.text.strip()
                    buffer.append(para.text)
                else:
                    if para.text.strip():
                        buffer.append(para.text)
            _flush()

            if not pages:
                pages.append(ParsedPage(
                    page_number=1, text="", metadata={"parser": "python-docx"},
                ))
            return pages
        except Exception as exc:  # noqa: BLE001
            logger.exception("word parse failed")
            return [ParsedPage(
                page_number=1,
                text=f"Failed to parse Word document: {exc}",
                metadata={"error": str(exc)},
            )]

    # ------------------------------------------------------------------
    # Parsers — Excel
    # ------------------------------------------------------------------

    def _parse_excel(
        self,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        url: str = "",
    ) -> list[ParsedPage]:
        """Parse an .xlsx file using openpyxl if available.

        Each worksheet becomes one :class:`ParsedPage`; rows are joined with
        tabs and a trailing newline so the chunker can split naturally.
        """
        data = self._read_bytes(file_path, file_bytes)
        if data is None:
            return self._missing_input("excel")

        openpyxl = _import_optional("openpyxl")
        if openpyxl is None:
            return [ParsedPage(
                page_number=1,
                text=(
                    "Excel (.xlsx) parsing requires the optional library openpyxl. "
                    "Install with: pip install openpyxl"
                ),
                metadata={"missing_dependency": "openpyxl"},
            )]

        try:
            wb = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
            pages: list[ParsedPage] = []
            for idx, ws in enumerate(wb.worksheets, start=1):
                lines: list[str] = []
                for row in ws.iter_rows(values_only=True):
                    cells = [
                        "" if c is None else str(c)
                        for c in row
                    ]
                    if any(cell.strip() for cell in cells):
                        lines.append("\t".join(cells))
                pages.append(ParsedPage(
                    page_number=idx,
                    text="\n".join(lines),
                    section=ws.title or f"Sheet{idx}",
                    metadata={"parser": "openpyxl", "sheet": ws.title},
                ))
            return pages
        except Exception as exc:  # noqa: BLE001
            logger.exception("excel parse failed")
            return [ParsedPage(
                page_number=1,
                text=f"Failed to parse Excel workbook: {exc}",
                metadata={"error": str(exc)},
            )]

    # ------------------------------------------------------------------
    # Parsers — PowerPoint
    # ------------------------------------------------------------------

    def _parse_powerpoint(
        self,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        url: str = "",
    ) -> list[ParsedPage]:
        """Parse a .pptx file using python-pptx if available (one page/slide)."""
        data = self._read_bytes(file_path, file_bytes)
        if data is None:
            return self._missing_input("powerpoint")

        pptx = _import_optional("pptx")
        if pptx is None:
            return [ParsedPage(
                page_number=1,
                text=(
                    "PowerPoint (.pptx) parsing requires the optional library python-pptx. "
                    "Install with: pip install python-pptx"
                ),
                metadata={"missing_dependency": "python-pptx"},
            )]

        try:
            prs = pptx.Presentation(io.BytesIO(data))
            pages: list[ParsedPage] = []
            for idx, slide in enumerate(prs.slides, start=1):
                texts: list[str] = []
                title = ""
                for shape in slide.shapes:
                    if not shape.has_text_frame:
                        continue
                    shape_text = shape.text_frame.text.strip()
                    if not shape_text:
                        continue
                    if shape == slide.shapes.title:
                        title = shape_text
                    texts.append(shape_text)
                pages.append(ParsedPage(
                    page_number=idx,
                    text="\n".join(texts),
                    section=title,
                    metadata={"parser": "python-pptx", "slide": idx},
                ))
            return pages
        except Exception as exc:  # noqa: BLE001
            logger.exception("powerpoint parse failed")
            return [ParsedPage(
                page_number=1,
                text=f"Failed to parse PowerPoint deck: {exc}",
                metadata={"error": str(exc)},
            )]

    # ------------------------------------------------------------------
    # Parsers — CSV (pure stdlib)
    # ------------------------------------------------------------------

    def _parse_csv(
        self,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        url: str = "",
    ) -> list[ParsedPage]:
        """Parse a CSV using the stdlib :mod:`csv` module.

        The whole file is treated as one page; rows are rendered as tab
        separated values so the chunker can break between rows.
        """
        text_data = self._read_text(file_path, file_bytes)
        if text_data is None:
            return self._missing_input("csv")

        try:
            reader = csv.reader(io.StringIO(text_data))
            lines: list[str] = []
            header: list[str] = []
            for row_idx, row in enumerate(reader):
                if not row:
                    continue
                if row_idx == 0:
                    header = row
                lines.append("\t".join(row))
            metadata: dict[str, Any] = {"parser": "csv", "rows": len(lines)}
            if header:
                metadata["header"] = header
            return [ParsedPage(
                page_number=1,
                text="\n".join(lines),
                metadata=metadata,
            )]
        except Exception as exc:  # noqa: BLE001
            logger.exception("csv parse failed")
            return [ParsedPage(
                page_number=1,
                text=f"Failed to parse CSV: {exc}",
                metadata={"error": str(exc)},
            )]

    # ------------------------------------------------------------------
    # Parsers — Image (OCR placeholder)
    # ------------------------------------------------------------------

    def _parse_image(
        self,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        url: str = "",
    ) -> list[ParsedPage]:
        """OCR an image using pytesseract if available, else placeholder."""
        data = self._read_bytes(file_path, file_bytes)
        if data is None:
            return self._missing_input("image")

        pytesseract = _import_optional("pytesseract")
        pil = _import_optional("PIL") or _import_optional("pil")
        if pytesseract is None or pil is None:
            return [ParsedPage(
                page_number=1,
                text=(
                    "Image OCR requires the optional libraries pytesseract and Pillow. "
                    "Install with: pip install pytesseract Pillow  "
                    "(and the system tesseract-ocr binary)."
                ),
                metadata={"missing_dependency": "pytesseract|Pillow"},
            )]

        try:
            image = pil.Image.open(io.BytesIO(data))
            text = pytesseract.image_to_string(image)
            return [ParsedPage(
                page_number=1,
                text=text or "",
                metadata={"parser": "pytesseract"},
            )]
        except Exception as exc:  # noqa: BLE001
            logger.exception("image OCR failed")
            return [ParsedPage(
                page_number=1,
                text=f"Failed to OCR image: {exc}",
                metadata={"error": str(exc)},
            )]

    # ------------------------------------------------------------------
    # Parsers — plain text (pure stdlib)
    # ------------------------------------------------------------------

    def _parse_text(
        self,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        url: str = "",
    ) -> list[ParsedPage]:
        """Parse a plain-text / markdown file.

        Splits on form-feed (``\\f``) characters if present (a common
        page-break convention), otherwise returns a single page.
        """
        text_data = self._read_text(file_path, file_bytes)
        if text_data is None:
            return self._missing_input("text")

        if "\f" in text_data:
            parts = text_data.split("\f")
            return [
                ParsedPage(page_number=i, text=part, metadata={"parser": "text"})
                for i, part in enumerate(parts, start=1) if part.strip()
            ] or [ParsedPage(page_number=1, text="", metadata={"parser": "text"})]

        return [ParsedPage(page_number=1, text=text_data, metadata={"parser": "text"})]

    # ------------------------------------------------------------------
    # Parsers — HTML (pure stdlib)
    # ------------------------------------------------------------------

    def _parse_html(
        self,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        url: str = "",
    ) -> list[ParsedPage]:
        """Strip HTML tags and return visible text.

        Uses :class:`html.parser.HTMLParser` from the stdlib — no external
        dependency required. Headings (h1–h6) become section titles.
        """
        text_data = self._read_text(file_path, file_bytes)
        if text_data is None and url:
            text_data = self._fetch_url(url)
        if text_data is None:
            return self._missing_input("html")

        try:
            pages = self._html_to_pages(text_data)
            return pages or [ParsedPage(page_number=1, text="", metadata={"parser": "html"})]
        except Exception as exc:  # noqa: BLE001
            logger.exception("html parse failed")
            return [ParsedPage(
                page_number=1,
                text=f"Failed to parse HTML: {exc}",
                metadata={"error": str(exc)},
            )]

    def _html_to_pages(self, html_text: str) -> list[ParsedPage]:
        """Convert raw HTML into :class:`ParsedPage` objects."""
        from html.parser import HTMLParser

        class _Stripper(HTMLParser):
            def __init__(self) -> None:
                super().__init__(convert_charrefs=True)
                self.parts: list[str] = []
                self._skip = 0
                self.title = ""
                self._in_title = False

            def handle_starttag(self, tag, attrs):
                if tag in ("script", "style", "noscript"):
                    self._skip += 1
                if tag == "title":
                    self._in_title = True
                if tag in ("p", "br", "div", "li", "tr", "h1", "h2", "h3"):
                    self.parts.append("\n")

            def handle_endtag(self, tag):
                if tag in ("script", "style", "noscript") and self._skip > 0:
                    self._skip -= 1
                if tag == "title":
                    self._in_title = False
                if tag in ("p", "div", "li", "tr", "h1", "h2", "h3"):
                    self.parts.append("\n")

            def handle_data(self, data):
                if self._in_title:
                    self.title += data
                if self._skip:
                    return
                self.parts.append(data)

        stripper = _Stripper()
        stripper.feed(html_text)
        text = "".join(stripper.parts)
        title = stripper.title.strip()
        return [ParsedPage(
            page_number=1,
            text=text,
            section=title,
            metadata={"parser": "html", "title": title},
        )]

    # ------------------------------------------------------------------
    # Parsers — URL (fetch + HTML strip)
    # ------------------------------------------------------------------

    def _parse_url(
        self,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        url: str = "",
    ) -> list[ParsedPage]:
        """Fetch a URL and parse the response as HTML."""
        if not url:
            return self._missing_input("url")
        text_data = self._fetch_url(url)
        if text_data is None:
            return [ParsedPage(
                page_number=1,
                text=f"Failed to fetch URL: {url}",
                metadata={"error": "fetch_failed", "url": url},
            )]
        try:
            pages = self._html_to_pages(text_data)
            for p in pages:
                p.metadata["url"] = url
                p.metadata["parser"] = "url"
            return pages or [ParsedPage(
                page_number=1, text="", metadata={"parser": "url", "url": url},
            )]
        except Exception as exc:  # noqa: BLE001
            logger.exception("url parse failed")
            return [ParsedPage(
                page_number=1,
                text=f"Failed to parse URL content: {exc}",
                metadata={"error": str(exc), "url": url},
            )]

    # ------------------------------------------------------------------
    # Parsers — YouTube (transcript placeholder)
    # ------------------------------------------------------------------

    def _parse_youtube(
        self,
        file_path: str | None = None,
        file_bytes: bytes | None = None,
        url: str = "",
    ) -> list[ParsedPage]:
        """Placeholder for YouTube transcript extraction.

        A real implementation would call the YouTube transcript API
        (``youtube-transcript-api``) or the Data API ``captions.download``.
        For now we return a single instructional page so the pipeline remains
        callable end-to-end.
        """
        video_id = self._extract_youtube_id(url or "") or (file_path or "")
        message = (
            "YouTube transcript extraction is a placeholder. "
            "Install youtube-transcript-api and wire a transcript fetcher to enable. "
            f"Video id: {video_id or 'unknown'}"
        )
        return [ParsedPage(
            page_number=1,
            text=message,
            metadata={
                "parser": "youtube",
                "video_id": video_id,
                "placeholder": True,
            },
        )]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _read_bytes(file_path: str | None, file_bytes: bytes | None) -> bytes | None:
        if file_bytes is not None:
            return file_bytes
        if file_path:
            try:
                with open(file_path, "rb") as fh:
                    return fh.read()
            except OSError as exc:
                logger.warning("failed to read %s: %s", file_path, exc)
                return None
        return None

    @staticmethod
    def _read_text(file_path: str | None, file_bytes: bytes | None) -> str | None:
        if file_bytes is not None:
            try:
                return file_bytes.decode("utf-8", errors="replace")
            except Exception as exc:  # noqa: BLE001
                logger.warning("failed to decode bytes: %s", exc)
                return None
        if file_path:
            try:
                with open(file_path, "r", encoding="utf-8", errors="replace") as fh:
                    return fh.read()
            except OSError as exc:
                logger.warning("failed to read %s: %s", file_path, exc)
                return None
        return None

    @staticmethod
    def _fetch_url(url: str) -> str | None:
        """Fetch a URL using httpx if available, else urllib."""
        httpx = _import_optional("httpx")
        if httpx is not None:
            try:
                resp = httpx.get(url, timeout=30.0, follow_redirects=True)
                resp.raise_for_status()
                return resp.text
            except Exception as exc:  # noqa: BLE001
                logger.warning("httpx fetch failed for %s: %s", url, exc)
                return None
        # Stdlib fallback.
        try:
            from urllib.request import Request, urlopen

            req = Request(url, headers={"User-Agent": "PRACHAR-DocumentProcessor/1.0"})
            with urlopen(req, timeout=30) as resp:  # noqa: S310 — URL is user-supplied
                raw = resp.read()
                charset = resp.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except Exception as exc:  # noqa: BLE001
            logger.warning("urllib fetch failed for %s: %s", url, exc)
            return None

    @staticmethod
    def _extract_youtube_id(url: str) -> str:
        """Best-effort YouTube video id extraction."""
        if not url:
            return ""
        parsed = urlparse(url)
        if parsed.hostname in ("youtu.be",):
            return parsed.path.lstrip("/")
        if "youtube" in (parsed.hostname or ""):
            if parsed.path == "/watch":
                return parsed.query.split("v=")[-1].split("&")[0]
            m = re.search(r"/(embed|shorts|v)/([^/?#]+)", parsed.path)
            if m:
                return m.group(2)
        return ""

    @staticmethod
    def _missing_input(file_type: str) -> list[ParsedPage]:
        return [ParsedPage(
            page_number=1,
            text=f"No input provided for {file_type} parser.",
            metadata={"error": "missing_input", "file_type": file_type},
        )]


__all__ = [
    "DocumentProcessor",
    "ParsedPage",
    "ProcessingResult",
    "TextChunk",
]
