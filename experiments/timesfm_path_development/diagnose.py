"""Stage A only: cached frozen causal centers, no API or inventory rollout."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
from paths import generate

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/timesfm_path_development/development_v1'
PILOT=ROOT/'results/timesfm_forecast_pilot/development_v1'
def read(p):return json.loads(p.read_text(encoding='utf-8-sig'))
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2),encoding='utf-8')

def run():
    assert not OUT.exists(),'Preserve previous attempt'
    ready=read(ROOT/'results/timesfm_path_development/readiness_v1/readiness.json')
    assert ready['prior_pilot_complete']
    cases=read(PILOT/'cases.json');saved=read(PILOT/'predictions.json')
    assert len(cases)==len(saved)==48
    predictions={p['case_id']:p for p in saved}
    files=list(Path(__file__).parent.glob('*.py'))+[PILOT/'cases.json',PILOT/'predictions.json',PILOT/'freeze.json',ROOT/'docs/superpowers/specs/2026-10-14-timesfm-closed-loop-design.md',ROOT/'docs/superpowers/plans/2026-10-14-timesfm-closed-loop.md']
    OUT.mkdir(parents=True)
    write(OUT/'freeze.json',dict(sha256={str(p):digest(p) for p in files},uses_verified_frozen_pilot_centers=True,api=0,training=0))
    (OUT/'started.lock').write_text('one stage-A attempt\n',encoding='utf-8')
    records=[]
    try:
        for case in cases:
            prediction=predictions[case['id']]
            centers={name:prediction['methods'][name] for name in ('merton','naive','timesfm')}
            assert len(case['block_history'])*3==len(case['reconstructed_history'])
            assert len(case['reconstructed_history'])+case['report_age']==case['decision_period']-1
            methods={}
            for method in ('original_merton','merton','naive','timesfm'):
                center=centers['merton' if method=='original_merton' else method]
                params=(center,case['block_history'][-1],case['report_age'],case['id'])
                result=generate(*params,original=method=='original_merton')
                assert result==generate(*params,original=method=='original_merton')
                paths=np.asarray(result['paths']);assert paths.shape==(32,20)
                assert np.issubdtype(paths.dtype,np.integer) and ((paths>=0)&(paths<=20)).all()
                result['center']=center;methods[method]=result
            # Generation never receives future_label or event type.
            records.append(dict(case_id=case['id'],type=case['type'],methods=methods,actual=case['future_label']))
        write(OUT/'paths.json',records)
        write(OUT/'generated.json',dict(cases=48,methods=4,paths_per_method=32,generated_values=122880,api=0,training=0,stream_split='16 search + 16 review; deployment first 3 each',original_distribution='Public original Merton transition with 32 diagnostic paths; not exact original six-path random draws'))
        print('STAGE_A_GENERATED_48_CASES_NO_API')
    except Exception as exc:
        write(OUT/'failed.json',dict(type=type(exc).__name__,message=str(exc)))
        raise
if __name__=='__main__':run()
