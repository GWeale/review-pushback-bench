"""Grade saved pilot files only inside isolated Linux Docker containers."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import suite


def command(args):
    result=subprocess.run(args,capture_output=True,text=True)
    if result.returncode:
        raise RuntimeError('Container command failed: '+result.stderr[-3000:])
    return result.stdout


def grade(task, phase, app, logs, tag):
    tests=(task/'steps'/phase/'tests').resolve()
    command(['docker','build','-q','-t',tag,str(tests)])
    logs.mkdir(parents=True)
    command(['docker','run','--rm','--network=none','--read-only','--memory=512m','--cpus=1','--pids-limit=64',
             '--cap-drop=ALL','--cap-add=SETUID','--cap-add=SETGID','--cap-add=KILL','--cap-add=DAC_OVERRIDE','--security-opt=no-new-privileges',
             '--tmpfs','/tmp:rw,nosuid,nodev,size=64m,mode=1777',
             '--mount',f'type=bind,src={app.resolve()},dst=/app,readonly',
             '--mount',f'type=bind,src={logs.resolve()},dst=/logs/verifier',tag,'python','-I','/tests/verifier.py'])
    return json.loads((logs/'reward.json').read_text()),json.loads((logs/'details.json').read_text())


def run(tasks, pilot, work, output):
    manifest=json.loads((tasks/'manifest.json').read_text())
    index=json.loads((pilot/'index.json').read_text())
    rows=[]
    for i, trial in enumerate(index['trials']):
        record=next(row for row in manifest['tasks'] if row['case']==trial['case'] and row['arm']==trial['arm'])
        task=tasks/record['name']
        app=work/str(i)/'app'
        shutil.copytree(task/'environment',app)
        case=next(c for c in suite.cases() if c['id']==trial['case'])
        saved=pilot/trial['path']
        if suite.sha(saved/'candidate.py')!=trial['candidate_sha256']:
            raise ValueError('Pilot candidate hash mismatch')
        shutil.copyfile(saved/'candidate.py',app/'project'/case['path'])
        shutil.copyfile(saved/'response.json',app/'response.json')
        checkpoint=json.loads((pilot/trial['case']/'checkpoint.json').read_text())
        suite.dump(app/'checkpoint.json',{} if trial['arm']=='valid' else checkpoint['submission'])
        phase='review' if trial['turn']==0 else 'followup-'+str(trial['turn'])
        rewards,details=grade(task,phase,app,work/str(i)/'logs','rpb-pilot-'+str(i))
        rows.append(dict(trial,rewards=rewards,details=details))
    report={'version':suite.VERSION,'model':index['model'],'trials':rows,'expected':12,
            'complete':len(rows)==12,'execution':'Isolated Docker; no network; unprivileged candidate worker; protected grading parent.'}
    report.update(ci_revision=os.environ.get('GITHUB_SHA'), ci_run=os.environ.get('GITHUB_RUN_ID'),
                  verifier_sha256=suite.sha(suite.ROOT/'verifier.py'),worker_sha256=suite.sha(suite.ROOT/'worker.py'),
                  plan_sha256=suite.sha(pilot/'plan.json'),index_sha256=suite.sha(pilot/'index.json'))
    suite.dump(output,report)
    print(json.dumps({'trials':len(rows),'complete':report['complete']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('tasks','pilot','work','output'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    run(args.tasks,args.pilot,args.work,args.output)
