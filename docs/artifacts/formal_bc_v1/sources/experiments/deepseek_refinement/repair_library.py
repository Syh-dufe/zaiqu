"""One explicitly recorded semantic repair; do not relax arbitrary validation."""
import copy
import json
from pathlib import Path
import subprocess
import sys
from run import ROOT,write,compile_rule


def main():
    p=ROOT/'results/deepseek_refinement/operator_discovery_v1'
    target=p/'repaired_library.json'
    if target.exists():raise SystemExit('Refuse overwrite')
    calls=json.loads((p/'calls.json').read_text())
    assert len(calls)==2 and calls[0]['status']=='failed' and calls[1]['status']=='failed'
    candidates=calls[0]['candidates'];assert len(candidates)==3
    repaired=[];audit=[]
    for i,c in enumerate(candidates):
        r=copy.deepcopy(c)
        assert r['rules'][-1]=={'when':'true','delta':'0'}
        # Default is zero when no predicate matches. A final always-true zero rule
        # has identical intended output, and no side effects or mutable state.
        removed=r['rules'].pop();compile_rule(r)
        repaired.append(r);audit.append(dict(candidate=i,removed=removed,reason='Redundant terminal zero; default no-match output is zero'))
    write(target,dict(candidates=repaired,stage='explicit_syntax_repair_before_testing',
                      source_request=0,repair_audit=audit,excluded_request1='Wrong candidate count; not incorporated',
                      scope='No new API; raw failed responses and empty original libraries retained'))
    command=[sys.executable,'-u',str(Path(__file__).with_name('run.py')),'--run-name','library_development_repaired_v1','--cases','2',
             '--demand-seed','20261062','--event-seed','20261063','--correction-periods','5','--predictor','merton',
             '--operator-library',str(target)]
    with (p/'repaired_development.log').open('w',encoding='utf-8') as f:result=subprocess.run(command,cwd=ROOT,stdout=f,stderr=subprocess.STDOUT)
    if result.returncode:raise SystemExit(result.returncode)
    result=subprocess.run([sys.executable,str(Path(__file__).with_name('summarize.py')),str(ROOT/'results/deepseek_refinement/library_development_repaired_v1')],cwd=ROOT,capture_output=True,text=True)
    if result.returncode:raise SystemExit(result.stderr)
    print(result.stdout,flush=True)


if __name__=='__main__':main()
