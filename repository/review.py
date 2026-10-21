"""Audit independent human signoffs without substituting agent reviews."""
import argparse
import suite
import json


def audit(packet):
    expected={case['id'] for case in suite.cases()}
    if len(packet['cases'])!=len(expected) or {c['id'] for c in packet['cases']}!=expected:
        raise ValueError('Review packet must cover each case exactly once')
    complete=0
    for case in packet['cases']:
        reviews=case['reviews']
        identities=[r.get('reviewer') for r in reviews if r.get('status')=='approved']
        if len(identities)!=len(set(identities)):
            raise ValueError('Duplicate reviewer identity')
        approved=[r for r in reviews if r.get('status')=='approved' and r.get('independent_human') is True
                  and r.get('reviewer') and r.get('contract_evidence') and r.get('mutation_check') and r.get('test_adequacy')]
        complete+=len(approved)>=2 and not case.get('unresolved_disagreement',False)
    return {'cases':len(expected),'independently_approved':complete,
            'status':'complete' if complete==len(expected) else 'pending',
            'note':'Records are attestations requiring real independent engineers; this audit does not verify personal identities.'}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output')
    args=parser.parse_args()
    result=audit(json.loads((suite.ROOT/'human_review.json').read_text()))
    if args.output:
        from pathlib import Path
        suite.dump(Path(args.output),result)
    print(json.dumps(result,indent=2))
