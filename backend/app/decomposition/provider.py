"""Conservative grammar planner. Unsupported structures abstain instead of guessing."""
import re
from typing import Protocol
from app.models.claim import ClaimCandidate, ClaimProviderInfo
from app.models.proposition import ClausePlan, DecompositionPlan, TextSpan


class DecompositionProvider(Protocol):
    def info(self) -> ClaimProviderInfo: ...
    def decompose(self, candidate: ClaimCandidate) -> DecompositionPlan: ...


# Finite predicates, including explicit local negation. Longer forms come first.
VERB = r"(?:did not (?:reduce|increase|create|open|close|cause)|does not (?:own|contain|cause)|was not|were not|is not|are not|reduced|increased|created|opened|closed|caused|causes|declined|decreased|fell|rose|grew|added|lost|passed|signed|approved|banned|founded|owns|contains|contain|employs|produces|treated|received|collapsed|costs|was|were|is|are|has|have|had)"
PREDICATE = re.compile(r'\b'+VERB+r'\b', re.I)
CONNECTOR = re.compile(r'\s+(?:and|but)\s+', re.I)
UNSAFE = re.compile(r"\b(?:or|nor|if|unless|whether|although|while|because|due to|which|who|whose|that|when|after|before|since|until|despite|except|without|respectively|together|combined|only|neither|either|not only|may|might|could|would|should|will|allegedly|reportedly|possibly|probably|suggests|believes|thinks|hopes|wishes)\b|[;:?!\"“”()]", re.I)
ATTRIBUTION = re.compile(r'(?P<prefix>[A-Z][\w .\-]{0,60}? (?:said|reported|claimed) that)\s+')
CONTEXT = re.compile(r'(?P<prefix>In (?:[A-Z][A-Za-z \-]+ in )?\d{4},)\s+')
AMOUNT = r'(?:approximately |about |at least |at most |more than |less than |over |under )?\d[\d,]*(?:\.\d+)?'
CHANGE = re.compile(r'(?P<verb>reduced|increased) (?P<outcome>unemployment|employment|inflation|emissions|poverty) by (?P<amount>'+AMOUNT+r'\s*(?:%|percent|percentage points))(?P<scope> in \d{4})?$', re.I)
JOBS = re.compile(r'created (?P<amount>'+AMOUNT+r'(?: million| thousand| billion)? jobs)(?P<scope> in \d{4})?$', re.I)
POLICY = re.compile(r'(?:the|this|that) (?:policy|program|law|reform)$', re.I)


def effect(predicate: str, subject: str) -> tuple[str, str] | None:
    """Only positive, explicitly bounded policy patterns derive an occurrence."""
    if not POLICY.fullmatch(subject):
        return None
    change = CHANGE.fullmatch(predicate)
    if change:
        direction = 'declined' if change['verb'].lower() == 'reduced' else 'increased'
        return (f"{change['outcome']} {direction} by {change['amount']}{change['scope'] or ''}", 'policy_change_outcome')
    jobs = JOBS.fullmatch(predicate)
    if jobs:
        return (f"{jobs['amount']} were created{jobs['scope'] or ''}", 'policy_jobs_outcome')
    return None


def _review(reason: str) -> DecompositionPlan:
    return DecompositionPlan(review_reason=reason)


def _span(start: int, end: int) -> TextSpan:
    return TextSpan(start=start, end=end)


class EnglishRuleDecompositionProvider:
    def info(self) -> ClaimProviderInfo:
        return ClaimProviderInfo(name='english-atomic-rules', version='english-atomic-v1',
            parameters={'grammar': 'conservative-coordination-v1', 'max_clauses':10,
                        'causal_projection':'positive-policy-quantity-v1', 'language':'en'})

    def decompose(self, candidate: ClaimCandidate) -> DecompositionPlan:
        text = candidate.quote
        end = len(text.rstrip().rstrip('.'))
        start = len(text)-len(text.lstrip())
        attribution = context = None
        match = ATTRIBUTION.match(text, start)
        if match:
            attribution = _span(match.start('prefix'), match.end('prefix'))
            start = match.end()
        match = CONTEXT.match(text, start)
        if match:
            context = _span(match.start('prefix'), match.end('prefix'))
            start = match.end()
        body = text[start:end]
        if not body or len(text) > 4000:
            return _review('Empty or overlong candidate; inspect the original transcript.')
        if UNSAFE.search(body) or re.search(r'(?<!\d),|,(?!\d)', body):
            return _review('Unsupported scope, modality, attribution, subordination or punctuation.')
        if re.search(r'\b(?:said|reported|claimed|according to)\b',body,re.I):
            return _review('Attribution is not in the supported explicit prefix form.')
        # An interior sentence boundary is not a coordination; ASR can merge sentences.
        if re.search(r'\.\s+[A-Z]', body):
            return _review('Multiple sentences require a separate segmentation review.')
        joins = list(CONNECTOR.finditer(body))
        if len(joins) >= 10:
            return _review('Too many coordinated clauses.')
        if joins and re.search(r"\b(?:not|no|never|without|neither)\b|n't", body, re.I):
            return _review('Negation scope across coordination is ambiguous.')
        # A trailing adjunct may modify one or all coordinated predicates. Do not guess.
        if joins and re.search(r'\b(?:in|during|between|from|since|by|at)\s+(?:\d{4}\b|[A-Z][a-z])', body):
            return _review('Trailing time or location scope across coordination needs review.')
        bounds = [start] + [start+j.end() for j in joins]
        ends = [start+j.start() for j in joins] + [end]
        plans = []
        inherited = None
        for a,b in zip(bounds,ends):
            while a < b and text[a].isspace(): a += 1
            while b > a and (text[b-1].isspace() or text[b-1] == ','): b -= 1
            chunk = text[a:b]
            verb = PREDICATE.search(chunk)
            if verb is None:
                return _review('Unrecognized predicate or coordinated noun phrase.')
            pred_start = a+verb.start()
            subject_end = pred_start
            while subject_end > a and text[subject_end-1].isspace(): subject_end -= 1
            if subject_end > a:
                subject = _span(a,subject_end)
                subject_text = text[a:subject_end]
                if re.search(r'\b(?:not|never|and|but)\b', subject_text, re.I):
                    return _review('Unsupported subject structure.')
                # Explicit pronouns stay unresolved; no entity is invented.
                inherited = subject
            elif inherited is not None:
                subject = inherited
            else:
                return _review('Missing explicit subject.')
            predicate = text[pred_start:b]
            if len(predicate.split()) < 2 or predicate.lower() == verb.group().lower():
                return _review('Incomplete predicate.')
            # Multiple finite predicates inside one clause imply nested assertions.
            tail = predicate[len(verb.group()):]
            if PREDICATE.search(tail):
                return _review('Nested predicates require semantic decomposition.')
            separate = effect(predicate,text[subject.start:subject.end]) is not None
            if (POLICY.fullmatch(text[subject.start:subject.end])
                    and re.match(r'(?:reduced|increased|created)\b',predicate,re.I) and not separate):
                return _review('Policy effect wording is outside the supported quantity projection grammar.')
            plans.append(ClausePlan(subject=subject,predicate=_span(pred_start,b),
                attribution=attribution, context=context,
                separate_effect=separate))
        return DecompositionPlan(clauses=plans)
