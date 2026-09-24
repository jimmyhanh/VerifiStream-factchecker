"""Run from repository root after installing the backend. No models or network."""
import argparse
import json
from pathlib import Path
from app.claims.provider import EnglishRuleClaimProvider
from app.claims.service import grounded_candidates
from app.models.transcript import Segment, TranscriptResult


def evaluate(path: Path) -> dict:
    dataset = json.loads(path.read_text(encoding='utf-8'))
    provider = EnglishRuleClaimProvider()
    summaries = {}
    for split in ('development', 'held_out'):
        tp = fp = fn = 0
        errors = []
        cases = [case for case in dataset['cases'] if case['split'] == split]
        for case in cases:
            sentences = case['sentences']
            snapshot = TranscriptResult(language='en', duration_seconds=len(sentences)*4,
                segments=[Segment(id=i,start=i*4,end=(i+1)*4,text=item['text'])
                          for i,item in enumerate(sentences)], provider='synthetic-fixture',
                provider_version='1',model='none',model_revision='none',engine_version='none',parameters={})
            gold = set()
            cursor = 0
            for item in sentences:
                if item['check_worthy']:
                    gold.add((cursor,cursor+len(item['text'])))
                cursor += len(item['text'])+1
            candidates = grounded_candidates(snapshot, provider.extract(snapshot))
            predicted = {(c.char_start,c.char_end) for c in candidates}
            tp += len(gold & predicted)
            fp += len(predicted-gold)
            fn += len(gold-predicted)
            for kind, spans in [('false_positive',predicted-gold),('false_negative',gold-predicted)]:
                for start,end in sorted(spans):
                    errors.append({'case_id':case['id'], 'kind':kind,'quote':snapshot.text[start:end]})
        precision = tp/(tp+fp) if tp+fp else None
        recall = tp/(tp+fn) if tp+fn else None
        summaries[split] = {'cases':len(cases), 'true_positives':tp,'false_positives':fp,
            'false_negatives':fn,'precision':precision,'recall':recall,
            'f1': 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else None,'errors':errors}
    return {'dataset_version':dataset['version'], 'provider':provider.info().model_dump(),
            'matching':'Exact half-open canonical transcript character spans; one-to-one set matching',
            'limitations':'Synthetic, single-author labels; held out from rule tuning, not independently annotated or representative of real videos.',
            'splits':summaries}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--dataset', type=Path, default=Path(__file__).with_name('dataset.json'))
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    report = json.dumps(evaluate(args.dataset), indent=2)
    if args.output:
        args.output.write_text(report+'\n', encoding='utf-8')
    print(report)
