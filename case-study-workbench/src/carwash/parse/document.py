from __future__ import annotations

import re
from datetime import UTC, datetime
from html.parser import HTMLParser

from carwash.schemas import ParsedDocument, ParsedDocumentKind, ParsedSection
from carwash.source_registry import normalize_url


class _ContentHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title: str | None = None
        self.sections: list[ParsedSection] = []
        self._tag_stack: list[str] = []
        self._current_text: list[str] = []
        self._current_tag: str | None = None
        self._current_heading: str | None = None
        self._counts: dict[str, int] = {}

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        lowered = tag.lower()
        self._tag_stack.append(lowered)
        if lowered in {"title", "h1", "h2", "h3", "p", "li"}:
            self._flush_current()
            self._current_tag = lowered
            self._current_text = []

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == self._current_tag:
            self._flush_current()
        if self._tag_stack:
            self._tag_stack.pop()

    def handle_data(self, data: str) -> None:
        if self._current_tag is not None:
            self._current_text.append(data)

    def _flush_current(self) -> None:
        if self._current_tag is None:
            return
        text = _clean_text(" ".join(self._current_text))
        tag = self._current_tag
        self._current_tag = None
        self._current_text = []
        if not text:
            return
        self._counts[tag] = self._counts.get(tag, 0) + 1
        locator = f"html:{tag}[{self._counts[tag]}]"
        if tag == "title":
            self.title = text
            return
        if tag in {"h1", "h2", "h3"}:
            self._current_heading = text
            self.sections.append(ParsedSection(locator=locator, heading=text, text=text))
            return
        self.sections.append(ParsedSection(locator=locator, heading=self._current_heading, text=text))


def parse_html(source_id: str, url: str, html: bytes | str) -> ParsedDocument:
    html_text = html.decode("utf-8", errors="replace") if isinstance(html, bytes) else html
    parser = _ContentHTMLParser()
    parser.feed(html_text)
    parser.close()
    return ParsedDocument(
        source_id=source_id,
        canonical_url=normalize_url(url),
        kind=ParsedDocumentKind.HTML,
        title=parser.title,
        sections=parser.sections,
        extracted_at=datetime.now(UTC),
    )


def parse_pdf(source_id: str, url: str, pdf_bytes: bytes) -> ParsedDocument:
    import fitz  # type: ignore[import-untyped]

    document = fitz.open(stream=pdf_bytes, filetype="pdf")
    sections: list[ParsedSection] = []
    for page_index in range(document.page_count):
        page = document.load_page(page_index)
        text = _clean_text_preserve_lines(page.get_text("text"))
        if text:
            sections.append(
                ParsedSection(
                    locator=f"pdf:page={page_index + 1}",
                    heading=None,
                    text=text,
                )
            )
    metadata_title = document.metadata.get("title") if document.metadata else None
    title = _clean_text(metadata_title or "") or None
    document.close()
    return ParsedDocument(
        source_id=source_id,
        canonical_url=normalize_url(url),
        kind=ParsedDocumentKind.PDF,
        title=title,
        sections=sections,
        extracted_at=datetime.now(UTC),
    )


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def _clean_text_preserve_lines(text: str) -> str:
    lines = [_clean_text(line) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)
