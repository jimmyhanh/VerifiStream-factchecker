"""Synthetic decomposition assessment; includes abstentions in the denominator."""
import argparse
import json
from pathlib import Path
from uuid import uuid4
from app.claims.service import transcript_hash
from app.decomposition.provider import EnglishRuleDecompositionProvider
from app.decomposition.service import render_plan
from app.models.claim import ClaimCandidate, ClaimRun, ClaimProviderInfo
from app.models.transcript import Segment, TranscriptResult


def evaluate(path: Path) -> dict:
    dataset=json.loads(path.read_text(encoding='utf-8'))
    provider=EnglishRuleDecompositionProvider()
    resolved=expected_resolvable=exact=correct_abstentions=unsafe=0
    total_expected=matched=produced=0
    outcomes=[]
    for case in dataset['cases']:
        text=case['text']
        snapshot=TranscriptResult(language='en',duration_seconds=4,
            segments=[Segment(id=0,start=0,end=4,text=text)],provider='fixture',
            provider_version='1',model='none',model_revision='none',engine_version='none',parameters={})
        candidate=ClaimCandidate(id=uuid4(),quote=text,char_start=0,char_end=len(text),signals=['numerical'],
            segment_ids=[0],start_seconds=0,end_seconds=4,reason='Fixture',needs_context=False)
        source=ClaimRun(id=uuid4(),video_id=uuid4(),transcript_run_id=uuid4(),status='completed',
            provider=ClaimProviderInfo(name='fixture',version='1',parameters={}),
            transcript_sha256=transcript_hash(snapshot),transcript_snapshot=snapshot,candidates=[candidate])
        result=render_plan(candidate,provider.decompose(candidate),source)
        actual={(p.text,p.kind) for p in result.propositions}
        gold={(p['text'],p['kind']) for p in case['expected']}
        reviewed=result.status=='needs_review'
        if not reviewed: resolved+=1
        if case['needs_review']:
            correct_abstentions+=reviewed
            unsafe+=not reviewed
        else:
            expected_resolvable+=1
            exact+=not reviewed and actual==gold
            total_expected+=len(gold)
        matched+=len(actual & gold)
        produced+=len(actual)
        outcomes.append({'id':case['id'],'status':result.status,'review_reason':result.review_reason,
            'expected_review':case['needs_review'],'exact_match':(reviewed if case['needs_review'] else not reviewed and actual==gold),
            'actual':[{'text':t,'kind':k} for t,k in sorted(actual)],
            'missing':[{'text':t,'kind':k} for t,k in sorted(gold-actual)],
            'extra':[{'text':t,'kind':k} for t,k in sorted(actual-gold)]})
    return {'dataset_version':dataset['version'],'provider':provider.info().model_dump(),
        'scope':'Synthetic authored regression/evaluation examples, not independently annotated or held out; no general accuracy claim.',
        'cases':len(outcomes),'resolved_cases':resolved,'resolution_coverage':resolved/len(outcomes) if outcomes else None,
        'expected_resolvable_cases':expected_resolvable,'exact_resolved_cases':exact,
        'exact_success_over_resolvable':exact/expected_resolvable if expected_resolvable else None,
        'correct_abstentions':correct_abstentions,'unsafe_resolutions':unsafe,
        'proposition_precision':matched/produced if produced else None,
        'proposition_recall':matched/total_expected if total_expected else None,'outcomes':outcomes}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--dataset',type=Path,default=Path(__file__).with_name('dataset.json'))
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    report=json.dumps(evaluate(args.dataset),indent=2)
    if args.output: args.output.write_text(report+'\n',encoding='utf-8')
    print(report)
