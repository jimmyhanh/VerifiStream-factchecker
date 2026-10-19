"""Opt-in public-source fetch trial. No paid search; not an independence check."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'backend'))
from app.retrieval.fetcher import PublicHTTPSFetcher, RetrievalError
from app.retrieval.passages import LexicalPassageExtractor

fetcher=PublicHTTPSFetcher(); extractor=LexicalPassageExtractor()
results=[]
for url in ['https://docs.python.org/3/faq/general.html','https://www.python.org/doc/essays/foreword/']:
    try:
        page=fetcher.fetch(url); source=extractor.snapshot(url,page)
        passages=extractor.passages(source,'Python was released in 1991.')
        results.append({'url':url,'status':'fetched','chars':len(source.text),
            'text_sha256':source.text_sha256,'passage_count':len(passages),
            'exact_offsets':all(source.text[p.char_start:p.char_end]==p.text for p in passages)})
    except RetrievalError as exc:
        results.append({'url':url,'status':'failed','code':exc.code})
print(json.dumps(results,indent=2))
if not all(r['status']=='fetched' and r['passage_count'] for r in results):sys.exit(1)
