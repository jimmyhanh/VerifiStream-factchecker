"""Agreement with authored policy cases, conditional on supplied M6 labels."""
import json
from pathlib import Path
from app.verification.policy import decide


def evaluate() -> dict:
    cases=json.loads(Path(__file__).with_name('cases.json').read_text())
    results=[]
    for case in cases:
        status,rule,_=decide(set(case['labels']),case['unresolved'])
        results.append({'id':case['id'],'expected':case['expected'],'actual':status,
                        'rule_id':rule,'matches_policy_expectation':status==case['expected']})
    return {'dataset':'authored-verification-policy-v1','not_held_out':True,
            'preclassified_evidence':True,'matches':sum(r['matches_policy_expectation'] for r in results),
            'total':len(results),'results':results}


if __name__=='__main__':
    report=evaluate()
    print(json.dumps(report,indent=2))
    raise SystemExit(0 if report['matches']==report['total'] else 1)
