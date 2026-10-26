"""Pure algorithms: no network, clock, provider calls, verdicts or confidence."""
import re
from itertools import combinations
from typing import Protocol
from uuid import UUID, NAMESPACE_URL, uuid5
from app.models.mapping import MappingRun
from app.models.retrieval import SourceSnapshot
from app.models.ranking import (RankingRequest, SourceGroup, DependenceLink,
    RankedPassage, PropositionRanking, UnrankedPassage)
from app.retrieval.fetcher import canonical_url

PARAMETERS = {'shingle_size': 5, 'minimum_tokens': 100, 'minimum_unique_shingles': 50,
    'jaccard_threshold': 0.90, 'diversity_scope': 'within_relationship_tier',
    'sort_order': 'tier,group_round,directness,source_role,lexical_relevance,passage_uuid',
    'metadata_provenance': 'user_supplied_unverified_or_unknown',
    'directness_order': 'direct > indirect > unknown',
    'source_role_order': 'primary > secondary > unknown',
    'relationship_order': 'SUPPORTS = CONTRADICTS = QUALIFIES > CONTEXT'}


class RankingAlgorithm(Protocol):
    ranking_version: str
    grouping_version: str
    parameters: dict[str, str | int | float | bool]
    def analyze(self, mapping: MappingRun, request: RankingRequest) -> tuple[list[SourceGroup], list[PropositionRanking]]: ...


def shingles(text: str) -> set[tuple[str, ...]]:
    tokens = re.findall(r'\w+', text.casefold())
    if len(tokens) < 100:
        return set()
    values = {tuple(tokens[i:i+5]) for i in range(len(tokens)-4)}
    return values if len(values) >= 50 else set()


def group_sources(sources: list[SourceSnapshot], request: RankingRequest) -> list[SourceGroup]:
    ordered = sorted(sources, key=lambda s: str(s.id))
    parents = {s.id: s.id for s in ordered}
    token_sets = {s.id: shingles(s.text) for s in ordered}
    urls = {s.id: canonical_url(s.final_url) for s in ordered}
    origins = {i: canonical_url(a.origin_url) for i, a in request.origins.items()}
    links: list[DependenceLink] = []

    def root(i: UUID) -> UUID:
        while parents[i] != i:
            i = parents[i]
        return i

    for a, b in combinations(ordered, 2):
        reasons = []
        if urls[a.id] == urls[b.id]:
            reasons.append(('same_final_url', None, None, 'deterministic'))
        if a.text.strip() and a.text == b.text:
            reasons.append(('identical_text', 1.0, None, 'deterministic'))
        elif token_sets[a.id] and token_sets[b.id]:
            left, right = token_sets[a.id], token_sets[b.id]
            similarity = len(left & right) / len(left | right)
            if similarity >= .90:
                reasons.append(('near_duplicate_text', round(similarity, 6), None, 'heuristic'))
        # A declaration can point to another retrieved source, or both can cite a
        # common origin. Exact quote checking happens in the service; URL linkage
        # itself remains a user's unverified interpretation.
        a_origins = {urls[a.id]} | ({origins[a.id]} if a.id in origins else set())
        b_origins = {urls[b.id]} | ({origins[b.id]} if b.id in origins else set())
        shared = a_origins & b_origins
        if shared and (a.id in origins or b.id in origins):
            reasons.append(('shared_declared_origin', None, sorted(shared)[0], 'user_supplied_unverified'))
        for reason, similarity, origin, provenance in reasons:
            links.append(DependenceLink(left_source_id=a.id, right_source_id=b.id,
                reason=reason, similarity=similarity, origin_url=origin, provenance=provenance))
            parents[root(b.id)] = root(a.id)
    components: dict[UUID, list[UUID]] = {}
    for source in ordered:
        components.setdefault(root(source.id), []).append(source.id)
    groups = []
    for ids in components.values():
        members = set(ids)
        groups.append(SourceGroup(id=uuid5(NAMESPACE_URL, 'verifistream:source-dependence-v1:'+','.join(map(str,ids))),
            source_ids=ids, independence='unknown' if len(ids)==1 else 'dependence_detected_or_suspected',
            links=[link for link in links if link.left_source_id in members and link.right_source_id in members]))
    return sorted(groups, key=lambda g: str(g.id))


class TransparentRankingAlgorithm:
    ranking_version = 'transparent-order-v1'
    grouping_version = 'source-dependence-v1'
    parameters = PARAMETERS

    def analyze(self, mapping: MappingRun, request: RankingRequest) -> tuple[list[SourceGroup], list[PropositionRanking]]:
        retrieval = mapping.retrieval_snapshot
        used_sources = {r.source_id for r in mapping.results}
        sources = {s.id: s for s in retrieval.sources if s.id in used_sources}
        groups = group_sources(list(sources.values()), request)
        source_groups = {i: g.id for g in groups for i in g.source_ids}
        passages = {p.id: p for r in retrieval.results for p in r.passages}
        results: dict[UUID, PropositionRanking] = {}
        for item in sorted(mapping.results, key=lambda r: str(r.passage_id)):
            result = results.setdefault(item.proposition_id, PropositionRanking(proposition_id=item.proposition_id))
            label = item.decision.relationship if item.decision else None
            if item.status != 'mapped' or label == 'IRRELEVANT':
                result.unranked.append(UnrankedPassage(passage_id=item.passage_id, source_id=item.source_id,
                    reason='irrelevant' if label=='IRRELEVANT' else item.status))
                continue
            source = sources[item.source_id]
            assessment = request.assessments.get(item.passage_id)
            result.ranked.append(RankedPassage(passage_id=item.passage_id, source_id=item.source_id,
                group_id=source_groups[item.source_id], relationship=label, rank=1,
                tier='context' if label=='CONTEXT' else 'claim_evidence',
                directness=assessment.directness if assessment else 'unknown',
                source_role=assessment.source_role if assessment else 'unknown',
                assessment_origin='user_supplied_unverified' if assessment else 'unknown',
                lexical_relevance=passages[item.passage_id].lexical_relevance, group_repeat=False,
                citation_url=source.final_url, publisher=source.publisher,
                publication_date=source.publication_date, source_type=source.source_type,
                reasons=['Relationship tier comes from the saved M6 interpretation.',
                         'SUPPORTS, CONTRADICTS and QUALIFIES receive equal priority.',
                         'Lexical relevance is a retrieval heuristic, not Evidence Confidence.']))
        for result in results.values():
            output = []
            seen_all: set[UUID] = set()
            for tier in ('claim_evidence', 'context'):
                remaining = sorted((r for r in result.ranked if r.tier==tier), key=lambda r: (
                    -{'direct':2,'indirect':1,'unknown':0}[r.directness],
                    -{'primary':2,'secondary':1,'unknown':0}[r.source_role],
                    -r.lexical_relevance, str(r.passage_id)))
                # Round-robin over groups, within tier. This preserves contradictions
                # even when they share a suspected origin with supportive material.
                while remaining:
                    round_seen: set[UUID] = set()
                    deferred = []
                    for item in remaining:
                        if item.group_id in round_seen:
                            deferred.append(item)
                            continue
                        round_seen.add(item.group_id)
                        item.group_repeat = item.group_id in seen_all
                        seen_all.add(item.group_id)
                        item.rank = len(output)+1
                        item.reasons.append('Repeated dependence group; retained for inspection.' if item.group_repeat
                                            else 'First passage from this dependence group; independence remains unknown.')
                        item.reasons.append('Directness and source role are user-supplied and unverified.' if item.assessment_origin!='unknown'
                                            else 'Directness and primary/secondary role are unknown; no reputation or date bonus.')
                        output.append(item)
                    remaining = deferred
            result.ranked = output
            result.useful_source_count = len({r.source_id for r in output})
            result.useful_dependence_group_count = len({r.group_id for r in output})
        return groups, sorted(results.values(), key=lambda r: str(r.proposition_id))
