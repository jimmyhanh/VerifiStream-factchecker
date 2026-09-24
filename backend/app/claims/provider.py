"""Deterministic English baseline. Rules select candidates, never truth values."""
import re
from typing import Protocol
from app.models.claim import ClaimProviderInfo, ClaimSpan
from app.models.transcript import TranscriptResult


class ClaimProvider(Protocol):
    def info(self) -> ClaimProviderInfo: ...
    def extract(self, transcript: TranscriptResult) -> list[ClaimSpan]: ...


_ABBREVIATIONS = {'mr.', 'mrs.', 'ms.', 'dr.', 'prof.', 'sr.', 'jr.', 'vs.', 'e.g.', 'i.e.'}
_BOUNDARY = re.compile(r'[.!?]["\u201d\u2019\']*(?=\s|$)')
_ASSERTION = re.compile(
    r"\b(?:is|are|was|were|has|have|had|did|does|do|can|cannot|"
    r"increased|decreased|declined|fell|rose|grew|reduced|created|added|lost|"
    r"passed|signed|approved|banned|opened|closed|founded|owns|contains|"
    r"employs|costs|caused|causes|causing|resulted|results|led|leads|"
    r"produces|reported|reports|said|says|announced|announces|"
    r"isn't|aren't|wasn't|weren't|didn't|doesn't|don't)\b", re.I)
_NUMBER = re.compile(r'\d|\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|hundred|thousand|million|billion|percent|half|doubled|tripled)\b', re.I)
_CAUSAL = re.compile(r'\b(?:caused|causes|causing|because|due to|led to|leads to|resulted in|results in)\b', re.I)
_EVENT = re.compile(r'\b(?:passed|signed|approved|banned|opened|closed|founded|owns|contains|employs|produces|located|increased|decreased|declined|fell|rose|grew|reduced|created|added|lost|reported|announced)\b', re.I)
_SUBJECTIVE = re.compile(r"\b(?:i|we)\s+(?:think|believe|feel|hope|wish|prefer)|\b(?:hopefully|in my opinion|best|worst|amazing|terrible|beautiful)\b", re.I)
_FUTURE = re.compile(r'\b(?:will|would|should|might|may|could)\b', re.I)
_INSTRUCTION = re.compile(r'^\s*["\u201c\']*(?:please|imagine|suppose|ignore|return|output|write|list|give|show|tell|subscribe|buy)\b', re.I)
_QUESTION = re.compile(r'^\s*["\u201c\']*(?:who|what|when|where|why|how|did|does|do|is|are|was|were|has|have|can|could|should|would)\b', re.I)


def sentence_spans(text: str) -> list[tuple[int, int]]:
    """Simple punctuation splitter; decimal numbers and common abbreviations survive."""
    spans = []
    start = 0
    for match in _BOUNDARY.finditer(text):
        prefix = text[:match.start() + 1]
        token = prefix.split()[-1].lower()
        # Initialisms such as U.S. and initials are not reliable sentence ends.
        if match.group()[0] == '.' and (token in _ABBREVIATIONS or re.fullmatch(r'(?:[a-z]\.)+', token)):
            continue
        end = match.end()
        while start < end and text[start].isspace():
            start += 1
        if start < end:
            spans.append((start, end))
        start = end
    end = len(text.rstrip())
    while start < end and text[start].isspace():
        start += 1
    if start < end:
        spans.append((start, end))
    return spans


class EnglishRuleClaimProvider:
    def info(self) -> ClaimProviderInfo:
        return ClaimProviderInfo(name='english-rules', version='english-rules-v1',
            parameters={'splitter': 'punctuation-v1', 'language': 'en',
                        'exclude_forecasts': True, 'deduplicate_occurrences': False})

    def extract(self, transcript: TranscriptResult) -> list[ClaimSpan]:
        text = transcript.text
        selected = []
        for start, end in sentence_spans(text):
            sentence = text[start:end]
            if ('?' in sentence or _QUESTION.search(sentence) or _SUBJECTIVE.search(sentence)
                    or _FUTURE.search(sentence) or _INSTRUCTION.search(sentence)):
                continue
            if not _ASSERTION.search(sentence):
                continue
            signals = []
            if _NUMBER.search(sentence):
                signals.append('numerical')
            if _CAUSAL.search(sentence):
                signals.append('causal')
            if _EVENT.search(sentence):
                signals.append('factual_event')
            if signals:
                selected.append(ClaimSpan(char_start=start, char_end=end, signals=signals))
        return selected
