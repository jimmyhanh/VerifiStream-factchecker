"""Small synthetic passage-selection regression; not a search benchmark."""
import hashlib
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'backend'))
from app.retrieval.fetcher import FetchedPage
from app.retrieval.passages import LexicalPassageExtractor

CASES = [
    ('London opened 2 schools in 2024.', 'London opened 2 schools in 2024.', True),
    ('London opened 2 schools in 2024.', 'Bananas grow in warm climates.', False),
    ('The policy caused unemployment to decline.', 'Unemployment declined; researchers did not study the policy.', False),
    ('The Moon orbits Earth.', 'Earth has one natural satellite, the Moon.', True),
    ('Water freezes at 0 degrees Celsius.', 'H₂O solidifies at zero centigrade.', True),
    ('The city created 500 jobs.', 'The city discussed jobs but released no employment data.', False),
]

def evaluate():
    extractor=LexicalPassageExtractor(); outcomes=[]
    for query,text,relevant in CASES:
        body=text.encode(); page=FetchedPage('https://fixture.example/source','text/plain',body,hashlib.sha256(body).hexdigest())
        source=extractor.snapshot(page.final_url,page)
        passages=extractor.passages(source,query)
        exact=all(source.text[p.char_start:p.char_end]==p.text for p in passages)
        outcomes.append({'query':query,'source':text,'expected_useful':relevant,
            'returned':bool(passages),'exact_passages':exact})
    tp=sum(o['returned'] and o['expected_useful'] for o in outcomes)
    fp=sum(o['returned'] and not o['expected_useful'] for o in outcomes)
    fn=sum(not o['returned'] and o['expected_useful'] for o in outcomes)
    return {'scope':'Authored six-case development regression; no live search; not independent evaluation',
        'true_positive':tp,'false_positive':fp,'false_negative':fn,
        'precision':tp/(tp+fp) if tp+fp else 0,'recall':tp/(tp+fn) if tp+fn else 0,
        'exact_passage_checks':all(o['exact_passages'] for o in outcomes),'outcomes':outcomes}

if __name__=='__main__':
    print(json.dumps(evaluate(),indent=2))
