from typing import Protocol
from app.models.mapping import Relationship
from app.models.ranking import RankingRun
from app.models.verification import (EvidenceStatus, EvidenceCoverage,
    PropositionVerification, VerificationCitation)

PARAMETERS = {'scope':'selected_retrieved_evidence', 'majority_vote':False,
    'unresolved_selected_blocks_unopposed_status':True, 'unmapped_passages':'reported_outside_scope',
    'rule_order':'conflict,unresolved,contradiction,qualification,support,insufficient',
    'rank_and_quality_annotations_determine_status':False}


def decide(labels: set[Relationship], unresolved: bool) -> tuple[EvidenceStatus, str, str]:
    """No counts, score, reputation or external knowledge enter this policy."""
    if 'CONTRADICTS' in labels and labels & {'SUPPORTS','QUALIFIES'}:
        return ('Conflicting Evidence','opposing_evidence',
            'Selected passages contain contradictory and supporting or qualifying interpretations. '
            'Neither repetition nor ranking resolves this disagreement.')
    if unresolved:
        return ('Insufficient Evidence','unresolved_selected_mappings',
            'Some selected passages failed mapping or need review. Their unresolved relationships '
            'prevent an unopposed evidence status; resolved citations remain available.')
    if 'CONTRADICTS' in labels:
        return ('Contradicted','contradictory_evidence',
            'Selected evidence contradicts this proposition, with no supporting or qualifying '
            'relationship in the selected set.')
    if 'QUALIFIES' in labels:
        return ('Partially Supported','qualified_evidence',
            'Selected evidence supports only part of the proposition or adds material qualifications. '
            'Inspect the quoted limitations before drawing a broader conclusion.')
    if 'SUPPORTS' in labels:
        return ('Supported','supporting_evidence',
            'Selected evidence supports the proposition as mapped, with no contradictory or '
            'qualifying relationship in the selected set.')
    return ('Insufficient Evidence','no_decisive_evidence',
        'No selected mapped passage supports, contradicts or qualifies this proposition. '
        'Missing evidence is not evidence that the proposition is false.')


class VerificationPolicy(Protocol):
    version: str
    parameters: dict[str, str | int | float | bool]
    def evaluate(self, ranking: RankingRun) -> list[PropositionVerification]: ...


class SelectedEvidencePolicy:
    version = 'selected-evidence-v1'
    parameters = PARAMETERS

    def evaluate(self, ranking: RankingRun) -> list[PropositionVerification]:
        mapping = ranking.mapping_snapshot
        retrieval = mapping.retrieval_snapshot
        propositions = {p.id:p for r in retrieval.decomposition_snapshot.results for p in r.propositions}
        sources = {s.id:s for s in retrieval.sources}
        groups = {s:g.id for g in ranking.groups for s in g.source_ids}
        results = []
        for retrieved in sorted(retrieval.results, key=lambda r:str(r.proposition_id)):
            proposition = propositions[retrieved.proposition_id]
            selected = sorted((r for r in mapping.results if r.proposition_id==proposition.id),
                              key=lambda r:str(r.passage_id))
            resolved = [r for r in selected if r.status=='mapped']
            unresolved = [r.passage_id for r in selected if r.status!='mapped']
            selected_ids = {r.passage_id for r in selected}
            unmapped = sorted((p.id for p in retrieved.passages if p.id not in selected_ids),key=str)
            citations = []
            labels: set[Relationship] = set()
            group_labels: dict = {}
            decisive_sources, decisive_groups = set(), set()
            for result in resolved:
                decision = result.decision
                source = sources[result.source_id]
                group = groups[source.id]
                label = decision.relationship
                labels.add(label)
                group_labels.setdefault(group,set()).add(label)
                if label in ('SUPPORTS','CONTRADICTS','QUALIFIES'):
                    decisive_sources.add(source.id);decisive_groups.add(group)
                citations.append(VerificationCitation(passage_id=result.passage_id,source_id=source.id,
                    group_id=group,relationship=label,url=source.final_url,quote=decision.evidence_quote,
                    char_start=result.quote_char_start,char_end=result.quote_char_end,title=source.title,
                    publisher=source.publisher,publication_date=source.publication_date,
                    source_type=source.source_type,primary_secondary=source.primary_secondary,
                    metadata_origin=source.metadata_origin,mapping_explanation=decision.explanation,
                    mapping_caveats=list(decision.caveats)))
            status, rule, explanation = decide(labels,bool(unresolved))
            limitations = ['Status summarizes the selected retrieved evidence, not universal truth.',
                'M6 relationships are model interpretations; exact quotes establish provenance, not semantic accuracy.',
                'Source independence is unknown. Dependence groups are not independent confirmations.',
                'No new retrieval, temporal adjudication or causal analysis was performed by this policy.']
            if unmapped:
                limitations.append(f'{len(unmapped)} retrieved passages were not selected for mapping and are outside this status scope.')
            if unresolved:
                limitations.append(f'{len(unresolved)} selected mappings are unresolved; inspect their saved errors or review reasons.')
            if retrieved.status!='retrieved' or any(a.status=='failed' for a in retrieved.attempts):
                limitations.append('Retrieval was incomplete, empty or unsuccessful for this proposition; inspect its saved outcome.')
            if retrieved.user_context:
                limitations.append('User-supplied search context is unverified and does not amend the original claim.')
            if not selected:
                limitations.append('No passages were selected for mapping for this proposition.')
            results.append(PropositionVerification(proposition_id=proposition.id,
                parent_candidate_id=proposition.parent_candidate_id,proposition_text=proposition.text,
                source_quote=proposition.source_quote,start_seconds=proposition.start_seconds,
                end_seconds=proposition.end_seconds,evidence_status=status,rule_id=rule,explanation=explanation,
                coverage=EvidenceCoverage(retrieved_passages=len(retrieved.passages),selected_passages=len(selected),
                    mapped_passages=len(resolved),unresolved_passage_ids=unresolved,unmapped_passage_ids=unmapped,
                    retrieval_status=retrieved.status,failed_fetch_count=sum(a.status=='failed' for a in retrieved.attempts)),
                citations=citations,group_relationships={g:sorted(v) for g,v in sorted(group_labels.items(),key=lambda kv:str(kv[0]))},
                decisive_source_count=len(decisive_sources),decisive_dependence_group_count=len(decisive_groups),
                limitations=limitations))
        return results
