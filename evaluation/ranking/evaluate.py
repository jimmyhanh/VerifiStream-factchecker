"""Authored source-pair fixtures, not a benchmark of real-world independence."""
import hashlib
import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5
from app.models.retrieval import SourceSnapshot
from app.models.ranking import RankingRequest, OriginDeclaration
from app.ranking.algorithm import group_sources


def evaluate() -> dict:
    cases=json.loads(Path(__file__).with_name('cases.json').read_text())
    results=[]
    counts={'tp':0,'fp':0,'fn':0,'tn':0}
    for case in cases:
        sources=[]
        for side in ('a','b'):
            url='https://fixture.example/'+('same' if case.get('same_url') else side)
            body=case[side]
            sources.append(SourceSnapshot(id=uuid5(NAMESPACE_URL,case['id']+side),
                requested_url=url,final_url=url,domain='fixture.example',content_type='text/plain',
                text=body,text_sha256=hashlib.sha256(body.encode()).hexdigest(),raw_sha256='fixture'))
        request=RankingRequest(mapping_run_id=uuid5(NAMESPACE_URL,case['id']))
        if case.get('origin'):
            request.origins={s.id:OriginDeclaration(origin_url=case['origin'],char_start=0,
                char_end=len(s.text),quote=s.text,rationale='Authored shared-origin declaration') for s in sources}
        groups=group_sources(sources,request)
        predicted=len(groups)==1
        expected=case['should_link']
        key='tp' if predicted and expected else 'fp' if predicted else 'fn' if expected else 'tn'
        counts[key]+=1
        results.append({'id':case['id'],'expected_link':expected,'predicted_link':predicted,
                        'reasons':[link.reason for group in groups for link in group.links]})
    return {'dataset':'authored-source-pairs-v1','not_held_out':True,'counts':counts,'results':results}


if __name__=='__main__':
    print(json.dumps(evaluate(),indent=2))
