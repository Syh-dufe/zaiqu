"""Independent cost recomputation and complete focused-completion export."""
import csv,gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_focus_completion/v1';OLD=ROOT/'results/sundial_closed_loop_development/development_v2/runs'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
digest=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
done=read(OUT/'completed.json');assert done['total_episodes']==40 and done['new_episodes']==24
f=read(OUT/'freeze.json');summary=read(OUT/'summary.json');lookup={(e['seed'],e['group'],e['trace'],e['scenario']):e for e in summary['all_episodes']};count=0
for seed in range(11,16):
 directory=OLD/f'batch01_seed{seed}' if seed<13 else OUT/'runs'/next(t['label'] for t in done['completed_tasks'] if t['seed']==seed)
 with (directory/'periods.csv').open(encoding='utf-8',newline='') as stream:rows=list(csv.DictReader(stream))
 selected=[r for r in rows if r['group'] in ('original_merton','adapted_sundial') and int(r['trace']) in (2,3)]
 identities={(r['group'],r['scenario'],int(r['trace']),int(r['period']),int(r['node'])) for r in selected};assert len(selected)==len(identities)==4800
 for method in ('original_merton','adapted_sundial'):
  for scenario in ('base','shock'):
   for trace in (2,3):
    local=[r for r in selected if r['group']==method and r['scenario']==scenario and int(r['trace'])==trace];assert len(local)==600
    assert all(float(r['cost'])==int(r['inventory'])+int(r['backlog']) for r in local)
    cost=sum(float(r['cost']) for r in local)/600;assert abs(cost-lookup[seed,method,trace,scenario]['cost'])<1e-12;count+=1
 c=read(directory/'completed.json');expected=f['contracts'][str(seed)]['expected_parameter_sha256']
 for method in ('original_merton','adapted_sundial'):assert c['parameter_checks'][method]['before']==c['parameter_checks'][method]['after']==expected
 model=read(directory/'forecast_model_checks.json');assert model['unchanged'] and model['before']==model['after']
for p in summary['pairs']:
 old=lookup[p['seed'],'original_merton',p['trace'],'shock']['cost'];new=lookup[p['seed'],'adapted_sundial',p['trace'],'shock']['cost']
 assert abs(p['difference']-(new-old))<1e-12 and abs(p['reduction_percent']-(old-new)/old*100)<1e-10
for kind,v in summary['type_means'].items():
 ps=[p for p in summary['pairs'] if p['type']==kind];assert len(ps)==5
 assert abs(sum(p['old_cost'] for p in ps)/5-v['old_cost'])<1e-12 and abs(sum(p['new_cost'] for p in ps)/5-v['new_cost'])<1e-12
for path,sha in f['reused_sha256'].items():assert digest(Path(path))==sha,path
assert count==40
(OUT/'independent_summary_verification.json').write_text(json.dumps(dict(status='passed',raw_cost_episodes=40,selected_node_periods=24000,paired_costs=10,all_five_seeds=True,reused_hashes_unchanged=True,model_hashes_unchanged=True,post_selected_development=True),indent=2),encoding='utf-8')
TARGET=ROOT/'docs/artifacts/sundial_focus_completion_v1_completed';assert not TARGET.exists();TARGET.mkdir(parents=True)
with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
files=[p for p in OUT.rglob('*') if p.is_file() and 'archive' not in p.relative_to(OUT).parts]
files+=list((ROOT/'experiments/sundial_focus_completion').glob('*.py'))+[Path(__file__),ROOT/'docs/superpowers/specs/2026-10-15-sundial-focus-completion-design.md',ROOT/'docs/superpowers/plans/2026-10-15-sundial-focus-completion.md']
entries={}
for i,p in enumerate(dict.fromkeys(files)):
 raw=p.read_bytes();assert key not in raw;dest=TARGET/'files'/f'{i:04d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
 entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=digest(p),gzip_sha256=digest(dest))
(TARGET/'manifest.json').write_text(json.dumps(dict(files=entries,lossless=True,credential_absent=True,all_attempts_kept=True,reused_raw_files_in_preregistration=True,checkpoint_weights_local_only=True),ensure_ascii=False,indent=2),encoding='utf-8')
text=(OUT/'report.md').read_text(encoding='utf-8')
text+='\n## 独立核验与归档\n\n40回合/24000节点期成本从原始CSV独立重算，10配对差与百分比、五模型hash、复用文件SHA均一致。完整新增及部分/恢复记录无损gzip公开；seed11/12原始记录在本批事前包和原停止批归档均保留。本结果是事后选择两个已暴露场景的模型seed补齐，不能将五个模型当五条需求路径，不能宣称所有突发场景或普遍泛化改善。\n'
(ROOT/'docs/2026-10-15-sundial-focus-completion-results.md').write_text(text,encoding='utf-8')
print('FOCUS_INDEPENDENT_SUMMARY_AND_LOSSLESS_EXPORT',count,len(entries),summary['type_means'])
