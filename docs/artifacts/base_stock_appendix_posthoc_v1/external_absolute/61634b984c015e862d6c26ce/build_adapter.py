"""One-time construction of the new adapter from preserved confirmation sources.

Not an experiment entry point. Exact replacements fail if the source changes.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).parent


def change(text,old,new):
    assert old in text,old
    return text.replace(old,new)


def main():
    target=HERE/'run_online.py'
    assert not target.exists()
    s=(ROOT/'experiments/demand_shock_confirmation_v5/run_online.py').read_text(encoding='utf-8')
    s=change(s,'Frozen HAPPO online draft; no training and no API access during preflight.','Frozen HAPPO/IPPO and original online LLM common-path confirmation.')
    s=change(s,"METHODS = ('happo','online_feedback')","sys.path.insert(0,str(ROOT/'experiments/joint_baseline'))\nimport frozen\n\nMETHODS = ('happo','ippo','online_feedback')")
    s=change(s,"files += list(UPSTREAM.rglob('*.py'))","files += [ROOT/'experiments/joint_baseline/frozen.py',\n              ROOT/'docs/superpowers/plans/2026-10-05-joint-baseline-confirmation.md',\n              ROOT/'docs/superpowers/specs/2026-10-05-joint-baseline-design.md']\n    files += list(UPSTREAM.rglob('*.py'))")
    s=change(s,"return dict(input_sha256=digest(input_file)","_,ippo_contract=frozen.load('ippo',done['seed'])\n    _,happo_contract=frozen.load('happo',done['seed'])\n    assert happo_contract['expected_parameter_sha256']==audit['model_matches']['official_best']['sha256']\n    return dict(ippo_contract=ippo_contract,happo_contract=happo_contract,input_sha256=digest(input_file)")
    s=change(s,"EventController(self.group,client,library,random_rules,dict(group=self.group", "EventController('happo' if self.group=='ippo' else self.group,client,library,random_rules,dict(group=self.group")
    s=change(s,"happo_order=proposed[node],actual_order=actual[node]","policy_order=proposed[node],actual_order=actual[node]")
    s=change(s,"args=argparse.Namespace(**config);args.model_dir=str(model_dir)","algorithm='ippo' if group=='ippo' else 'happo'\n        args,group_contract=frozen.load(algorithm,contract['training_seed'])\n        expected=contract['ippo_contract' if algorithm=='ippo' else 'happo_contract']\n        assert group_contract==expected")
    s=change(s,"assert before==contract['expected_parameter_sha256']","assert before==expected['expected_parameter_sha256']")
    s=change(s,"assert len(episodes)==16 and len(rows)==9600","assert len(episodes)==24 and len(rows)==14400\n    assert len({(r['group'],r['scenario'],r['trace'],r['period'],r['node']) for r in rows})==14400")
    s=change(s,"for group in METHODS[1:]:","for group in ('online_feedback',):")
    s=change(s,"    assert source_hashes()==contract['source_sha256']", "    for trace,event in enumerate(data['events']):\n        for group in METHODS:\n            left=[(r['cost'],r['actual_order']) for r in rows if r['group']==group and r['scenario']=='base' and r['trace']==trace and r['period']<=event['start_index']]\n            right=[(r['cost'],r['actual_order']) for r in rows if r['group']==group and r['scenario']=='shock' and r['trace']==trace and r['period']<=event['start_index']]\n            assert left==right,'Own normal/shock prefix differs'\n    assert source_hashes()==contract['source_sha256']")
    target.write_text(s,encoding='utf-8')
    s=(ROOT/'experiments/demand_shock_confirmation_v5b/batch.py').read_text(encoding='utf-8')
    s=change(s,'Registered independent confirmation of frozen HAPPO and original online LLM.','Registered common unseen-path comparison: frozen HAPPO, IPPO and original online LLM.')
    s=change(s,"experiments/demand_shock_confirmation_v5/run_online.py","experiments/joint_baseline_confirmation/run_online.py")
    s=change(s,"docs/superpowers/plans/2026-10-05-independent-shock-confirmation-v5b.md","docs/superpowers/plans/2026-10-05-joint-baseline-confirmation.md")
    s=change(s,"results/online_llm_shock_types/confirmation_v5b","results/joint_baseline_confirmation/confirmation_v1")
    s=change(s,"METHODS=('happo','online_feedback')","METHODS=('happo','ippo','online_feedback')")
    s=change(s,'range(20271402,20271452)','range(20271501,20271551)')
    s=change(s,'BOOTSTRAP_SEED=20271003','BOOTSTRAP_SEED=20271551')
    s=change(s,"    return used,sources", "    import numpy as np\n    for path in sorted((core.UPSTREAM/'test_data/test_demand_merton').glob('*.txt')):\n        trace=tuple(map(int,np.loadtxt(path).reshape(-1)[:200]))\n        assert len(trace)==200\n        used.add(trace);sources.append(dict(path=str(path),sha256=digest(path),traces=1,origin='normal_model_selection'))\n    assert len(list((core.UPSTREAM/'test_data/test_demand_merton').glob('*.txt')))==20\n    return used,sources")
    s=change(s,'New-path independent confirmation of the original real-time LLM across four demand shock shapes','Common unseen-path comparison of HAPPO, IPPO and the original real-time LLM across four demand shock shapes')
    s=change(s,'expected_episodes=800','expected_episodes=1200')
    s=change(s,'expected_node_periods=480000','expected_node_periods=720000')
    s=change(s,'expected_rows=480000','expected_rows=720000')
    s=change(s,'Equal-weight pooled online_feedback minus HAPPO cost and downstream backlog on shocked episodes; both 95% crossed-bootstrap interval upper endpoints must be below zero for evidence of joint improvement.','Equal-weight pooled online_feedback minus IPPO shock cost and downstream backlog; both means and 97.5% two-sided crossed-bootstrap upper endpoints must be below zero.')
    s=change(s,'By-type paired estimates and normal/shock difference-in-differences; descriptive, all cases retained.','online_feedback-HAPPO and IPPO-HAPPO are descriptive 95% comparisons; all normal/shock, DID, type, seed and unfavorable cases retained.')
    s=change(s,'five HAPPO model seeds','five paired HAPPO/IPPO model seeds')
    s=change(s,"interval='percentile 95% two-sided'","interval='primary percentile 97.5% two-sided (.0125,.9875); secondary95%'" )
    s=change(s,"prior_exposed_inputs_excluded=True,previous_development_resource_use=dict(http=PRIOR_DEVELOPMENT_HTTP,\n            semantic=PRIOR_DEVELOPMENT_SEMANTIC,tokens=PRIOR_DEVELOPMENT_TOKENS)","prior_exposed_inputs_excluded=True,historical_api_costs_excluded_from_batch=True")
    s=s.replace("==16 and done['rows']==9600","==24 and done['rows']==14400").replace('len(episodes)==16','len(episodes)==24').replace('len(rows)==9600','len(rows)==14400')
    s=change(s,"row['group']=='happo' or row['scenario']=='base'","row['group'] in ('happo','ippo') or row['scenario']=='base'")
    s=change(s,"    calls=read(directory/'calls.json')","    import analyze\n    analyze.audit_raw(rows,episodes,data,read(directory/'information_audits.json'),read(directory/'parameter_checks.json') if (directory/'parameter_checks.json').exists() else done['parameter_checks'],entry['contracts'][str(seed)])\n    calls=read(directory/'calls.json')")
    start=s.index('\ndef crossed_bootstrap(');end=s.index('\ndef main():',start)
    s=s[:start]+'''\ndef summarize(out,manifest,finished):
    import analyze
    return analyze.summarize(out,manifest,finished,audit_child,all_recorded_calls,usage_totals)

'''+s[end:]
    s=change(s,"done.get('episodes')!=16 or done.get('rows')!=9600","done.get('episodes')!=24 or done.get('rows')!=14400")
    s=change(s,'episodes=16,node_periods=9600','episodes=24,node_periods=14400')
    s=change(s,"                finished[task]=item;", "                audit_child(directory,entry,seed)\n                finished[task]=item;")
    s=change(s,"dict(overall=summary['overall'],by_type=summary['by_shock_type'])","dict(primary=summary['primary'],comparisons=summary['comparisons'])")
    (HERE/'batch.py').write_text(s,encoding='utf-8')


if __name__=='__main__':main()
