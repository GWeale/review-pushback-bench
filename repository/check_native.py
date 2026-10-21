"""Validate Harbor loading and assert native staged oracle/no-op trial results."""
import argparse
import importlib.metadata
import json
from pathlib import Path
import suite


def schema(tasks):
    from harbor.models.task.task import Task
    manifest=json.loads((tasks/'manifest.json').read_text())
    for row in manifest['tasks']:
        task=Task(tasks/row['name'])
        if task.config.verifier.environment_mode.value!='separate':
            raise ValueError('Separate verifier required')
        if len(task.config.steps)!=len(row['steps']):
            raise ValueError('Step count mismatch')
    return {'passed':True,'tasks_loaded':len(manifest['tasks']),'families':manifest['families'],
            'harbor_version':importlib.metadata.version('harbor'),'source_hash':manifest['source_hash'],
            'case_hash':manifest['case_hash'],'docker_trials':'separate CI check'}


def smoke(tasks,jobs):
    expected={row['name']:len(row['steps']) for row in json.loads((tasks/'manifest.json').read_text())['tasks']}
    report={}
    for agent,reward in [('oracle',1),('nop',0)]:
        results=[json.loads(p.read_text()) for p in (jobs/agent).glob('*/result.json')]
        if len(results)!=4 or {r['task_name'].split('/')[-1] for r in results}!=set(expected):
            raise ValueError('Missing or duplicate trials')
        for result in results:
            if result.get('exception_info') or result['verifier_result']['rewards']['reward']!=reward:
                raise ValueError('Unexpected native trial result: '+json.dumps(result)[:600])
            steps=result.get('step_results',[])
            if len(steps)!=expected[result['task_name'].split('/')[-1]]:
                raise ValueError('Expected all staged steps to execute')
        report[agent]={'trials':4,'all_expected':True}
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tasks',type=Path,required=True)
    parser.add_argument('--jobs',type=Path)
    parser.add_argument('--output',type=Path)
    args=parser.parse_args()
    result=smoke(args.tasks,args.jobs) if args.jobs else schema(args.tasks)
    if args.output:
        suite.dump(args.output,result)
    print(json.dumps(result,indent=2))
