"""Explicit opt-in paid semantic smoke evaluation; never called by normal CI."""
import argparse
import json
from pathlib import Path
from app.evidence.provider import OpenAIMappingProvider, MappingError
from app.shared.config import Settings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help='Send 12 authored cases to configured provider (API cost)')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not args.live:
        parser.error('Explicit --live is required; this makes paid external requests')
    config = Settings.from_env()
    if not config.openai_api_key.get_secret_value() or not config.mapping_model:
        parser.error('Set OPENAI_API_KEY and MAPPING_MODEL in the process environment')
    if args.output.exists():
        parser.error('Choose a new output filename; evaluation runs are not overwritten')
    provider = OpenAIMappingProvider(config.openai_api_key.get_secret_value(), config.mapping_model)
    cases = json.loads(Path(__file__).with_name('cases.json').read_text())
    results = []
    for case in cases:
        payload = {'proposition': {'text':case['claim'], 'kind':case['kind'],
                    'source_quote':case['claim'], 'attribution':None, 'context':None,
                    'needs_context':case['expected'] is None},
                   'unverified_user_search_context':None, 'passage':case['passage'],
                   'unverified_source_metadata':{'title':None,'publisher':None,'publication_date':None}}
        result = {'id':case['id'], 'expected':case['expected'], 'payload':payload}
        try:
            reply = provider.map(payload)
            decision = reply.decision
            exact = decision.evidence_quote is None or decision.evidence_quote in case['passage']
            causal_ok = not (case['kind']=='causal' and decision.relationship=='SUPPORTS'
                            and decision.causal_basis!='explicit_causal_evidence')
            result.update(decision=decision.model_dump(), exact_quote=exact,
                model=reply.model, response_id=reply.response_id, usage=reply.usage,
                correct=exact and causal_ok and decision.relationship==case['expected'])
        except MappingError as exc:
            result.update(error_code=exc.code, correct=False)
        results.append(result)
    report = {'dataset':'authored-mapping-smoke-v1', 'not_held_out':True,
              'requested_model':provider.model, 'prompt_version':provider.prompt_version,
              'prompt':provider.prompt, 'parameters':provider.parameters,
              'correct':sum(r['correct'] for r in results), 'total':len(cases), 'results':results}
    args.output.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'correct':report['correct'],'total':report['total'],'not_held_out':True}))


if __name__ == '__main__': main()
