"""Pure, provisional evidence adequacy heuristic. Never a truth probability."""
from math import floor
from typing import Protocol
from app.models.confidence import ConfidenceCap, ConfidenceComponent, PropositionConfidence
from app.models.verification import VerificationRun

PARAMETERS: dict[str, str | int | float | bool] = {
    'component_weight': 20, 'amount_saturation_groups': 3,
    'unknown_signals_cap': 75, 'single_group_cap': 50,
    'conflict_cap': 50, 'incomplete_cap': 25, 'no_evidence_cap': 0,
    'rounding': 'half_up', 'scope': 'selected_retrieved_evidence',
    'calibrated': False, 'unverified_annotations_affect_score': False,
}
DECISIVE = {'SUPPORTS', 'CONTRADICTS', 'QUALIFIES'}


class ConfidenceAlgorithm(Protocol):
    version: str
    parameters: dict[str, str | int | float | bool]
    def evaluate(self, verification: VerificationRun) -> list[PropositionConfidence]: ...


class TransparentConfidenceAlgorithm:
    version = 'evidence-confidence-v1'
    parameters = PARAMETERS

    def evaluate(self, verification: VerificationRun) -> list[PropositionConfidence]:
        ranked = {r.proposition_id: r for r in verification.ranking_snapshot.results}
        results = []
        for proposition in verification.results:
            coverage = proposition.coverage
            group_relevance: dict = {}
            ranking = ranked.get(proposition.proposition_id)
            for passage in ranking.ranked if ranking else []:
                if passage.relationship in DECISIVE:
                    group_relevance[passage.group_id] = max(
                        group_relevance.get(passage.group_id, 0.0), passage.lexical_relevance)
            labels = {c.relationship for c in proposition.citations} & DECISIVE
            conflict = 'CONTRADICTS' in labels and bool(labels & {'SUPPORTS', 'QUALIFIES'})
            groups = len(group_relevance)
            values = {
                'mapping_resolution': (coverage.mapped_passages / coverage.selected_passages
                    if coverage.selected_passages else 0, 'Resolved selected passages / selected passages.'),
                'retrieved_coverage': (coverage.mapped_passages / coverage.retrieved_passages
                    if coverage.retrieved_passages else 0, 'Resolved passages / retrieved passages; not web-wide coverage.'),
                'lexical_relevance': (sum(group_relevance.values()) / groups if groups else 0,
                    'Mean group maximum lexical overlap; not semantic relevance.'),
                'useful_amount': (min(groups / 3, 1),
                    'Distinct decisive dependence groups / 3, capped at 1; independence remains unknown.'),
                'agreement': (float(bool(labels) and not conflict),
                    'No opposing decisive labels; counts cannot outvote conflict.'),
            }
            components = {name: ConfidenceComponent(value=value, weight=20,
                points=value * 20, explanation=explanation)
                for name, (value, explanation) in values.items()}
            raw = sum(c.points for c in components.values())
            caps = [ConfidenceCap(maximum=75, reason='Quality, independence and temporal adequacy are unknown.')]
            if groups == 1:
                caps.append(ConfidenceCap(maximum=50, reason='Only one decisive dependence group.'))
            if conflict:
                caps.append(ConfidenceCap(maximum=50, reason='Opposing decisive evidence remains unresolved.'))
            if (coverage.unresolved_passage_ids or coverage.failed_fetch_count
                    or coverage.retrieval_status != 'retrieved'):
                caps.append(ConfidenceCap(maximum=25, reason='Unresolved selected mapping or incomplete retrieval.'))
            if not groups:
                caps.append(ConfidenceCap(maximum=0, reason='No decisive evidence.'))
            results.append(PropositionConfidence(proposition_id=proposition.proposition_id,
                evidence_status=proposition.evidence_status,
                evidence_confidence=min(floor(raw + 0.5), *(c.maximum for c in caps)),
                raw_score=raw, components=components, caps=caps,
                unknown_signals={key: None for key in ('source_quality', 'directness',
                    'primary_secondary', 'source_independence', 'claim_relative_recency')},
                limitations=[
                    'Uncalibrated evidence adequacy heuristic, not probability of truth or measured accuracy.',
                    'Unknown signals receive no bonus; unverified metadata and caller assessments are not scored.',
                    'Weights and caps are provisional design choices requiring human evaluation.',
                    'M6 mapping errors and undetected source dependence can inflate this score.',
                    *proposition.limitations]))
        return results
