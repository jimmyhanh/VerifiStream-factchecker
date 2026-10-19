import hashlib
import re
from html.parser import HTMLParser
from typing import Protocol
from uuid import uuid4
from urllib.parse import urlsplit
from app.models.retrieval import SourceSnapshot, EvidencePassage
from app.retrieval.fetcher import FetchedPage, RetrievalError


class VisibleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.hidden: list[str] = []
        self.title_parts: list[str] = []
        self.in_title = False
        self.metadata: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript', 'template', 'svg'):
            self.hidden.append(tag)
        if self.hidden:
            return
        attrs = dict(attrs)
        if tag == 'title': self.in_title = True
        if tag == 'meta':
            key = (attrs.get('property') or attrs.get('name') or '').lower()
            value = attrs.get('content')
            if key in ('og:title', 'og:site_name', 'article:published_time', 'date') and value:
                self.metadata.setdefault(key, value[:1000])
        if tag in ('p', 'div', 'br', 'li', 'h1', 'h2', 'h3', 'tr', 'section', 'article'):
            self.parts.append('\n')

    def handle_endtag(self, tag):
        if self.hidden:
            if tag == self.hidden[-1]: self.hidden.pop()
            return
        if tag == 'title': self.in_title = False
        if tag in ('p', 'div', 'li', 'h1', 'h2', 'h3', 'tr', 'section', 'article'):
            self.parts.append('\n')

    def handle_data(self, data):
        if self.hidden: return
        if self.in_title: self.title_parts.append(data)
        else: self.parts.append(data)


class PassageExtractor(Protocol):
    def snapshot(self, requested_url: str, page: FetchedPage) -> SourceSnapshot: ...
    def passages(self, source: SourceSnapshot, query: str) -> list[EvidencePassage]: ...


STOPWORDS = set('the a an and or but of to in on at by for from with is are was were be been it that this as'.split())


def tokens(text: str) -> set[str]:
    return set(re.findall(r'[a-z0-9]+', text.lower())) - STOPWORDS


class LexicalPassageExtractor:
    def snapshot(self, requested_url: str, page: FetchedPage) -> SourceSnapshot:
        # UTF-8 only for v1. Invalid bytes fail explicitly instead of corrupting quotations.
        try:
            decoded = page.body.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise RetrievalError('unsupported_text_encoding') from None
        parser = VisibleText()
        if page.content_type == 'text/plain':
            raw = decoded
        else:
            parser.feed(decoded)
            parser.close()
            raw = ''.join(parser.parts)
        text = '\n'.join(' '.join(line.split()) for line in raw.splitlines() if line.strip())
        if not text:
            raise RetrievalError('empty_source')
        if len(text) > 200000:
            raise RetrievalError('source_text_too_large')
        return SourceSnapshot(id=uuid4(), requested_url=requested_url, final_url=page.final_url,
            domain=urlsplit(page.final_url).hostname, content_type=page.content_type, text=text,
            raw_sha256=page.raw_sha256, text_sha256=hashlib.sha256(text.encode()).hexdigest(),
            title=parser.metadata.get('og:title') or ''.join(parser.title_parts).strip()[:1000] or None,
            publisher=parser.metadata.get('og:site_name'),
            publication_date=parser.metadata.get('article:published_time') or parser.metadata.get('date'))

    def passages(self, source: SourceSnapshot, query: str) -> list[EvidencePassage]:
        query_tokens = tokens(query)
        if not query_tokens: return []
        ranked = []
        # Non-overlapping exact windows. Character offsets refer to saved normalized text.
        start = 0
        while start < len(source.text):
            end = min(start + 1000, len(source.text))
            if end < len(source.text):
                boundary = source.text.rfind(' ', start + 500, end)
                if boundary > start: end = boundary
            passage = source.text[start:end]
            score = len(tokens(passage) & query_tokens) / len(query_tokens)
            if score > 0:
                ranked.append((score, start, end))
            start = end
        ranked.sort(key=lambda item: (-item[0], item[1]))
        return [EvidencePassage(id=uuid4(), source_id=source.id, char_start=start,
            char_end=end, text=source.text[start:end], lexical_relevance=round(score, 4))
            for score, start, end in ranked[:3]]
