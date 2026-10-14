import gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_scenario_development/v1';TARGET=ROOT/'docs/artifacts/sundial_scenario_development_v1'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
done=read(OUT/'completed.json');assert done['rows']==1440 and done['paths']==60 and not TARGET.exists()
assert read(OUT/'independent_verification.json')['independent_bootstrap']
with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
files=[p for p in OUT.glob('*') if p.is_file()]+list((ROOT/'experiments/sundial_scenario_development').glob('*.py'))
files += [ROOT/'docs/superpowers/specs/2026-10-14-sundial-scenarios-design.md',ROOT/'docs/superpowers/plans/2026-10-14-sundial-scenarios.md',Path(__file__)]
files += [Path(p) for p in read(OUT/'freeze.json')['sha256'] if Path(p).is_relative_to(ROOT)]
TARGET.mkdir(parents=True);entries={}
for i,p in enumerate(dict.fromkeys(files)):
 blob=p.read_bytes();assert key not in blob
 dest=TARGET/'files'/f'{i:04d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(blob,mtime=0));assert gzip.decompress(dest.read_bytes())==blob
 entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=hashlib.sha256(blob).hexdigest(),gzip_sha256=hashlib.sha256(dest.read_bytes()).hexdigest())
(TARGET/'manifest.json').write_text(json.dumps(dict(files=entries,lossless=True,credential_absent=True,all_negative_cases_kept=True,checkpoint_weights_local_only=True),ensure_ascii=False,indent=2),encoding='utf-8')
m=read(OUT/'metrics.json');text='# Sundial跨需求背景开发结果\n\n'
text+='冻结旧24参数适配器，Sundial不训练，API0。三背景×四冲击×五路径=60路径，360重叠窗口。Poisson均值分别为10、6到14线性趋势、10加振幅4周期40；需求截断0..20。四冲击和通知后窗口定义沿用登记方案。这是合成压力测试，不能称现实数据或订货成本结果。方法先冻结，后生成并历史查重。\n\n'
text+='|范围|方法|CRPS|MAE|\n|---|---|---:|---:|\n'
for bg,values in [('总体',m['overall'])]+list(m['by_background'].items()):
 for method,scores in values.items():text+=f"|{bg}|{method}|{scores['crps']:.6f}|{scores['mae']:.6f}|\n"
text+='\n## 探索性配对比较\n\n按12背景×冲击格内的独立路径重采样20000次，保留每路径全部窗口。两CRPS比较的Bonferroni97.5%区间，不把360窗口当独立需求。\n\n'
for method,v in m['contrasts'].items():text+=f"- adapted减{method}：均值{v['mean']:.6f}，区间{v['ci_97_5']}。\n"
text+='\n## 全部类型与退化\n\n|背景/类型|原Sundial CRPS|适配CRPS|Merton CRPS|最新值CRPS|\n|---|---:|---:|---:|---:|\n'
for cell,values in m['by_cell'].items():text+='|'+cell+'|'+ '|'.join(f"{values[k]['crps']:.6f}" for k in ('sundial','adapted','merton','naive'))+'|\n'
for method in ('sundial','merton','naive'):
 n=sum(p['means']['adapted']['crps']>p['means'][method]['crps'] for p in m['paths']);text+=f'\n适配CRPS高于{method}的路径：{n}/60。\n'
text+='\n本试验没有重新拟合适配器，检验原参数跨背景表现。旧Merton生成背景下失败结果不覆盖；不能将背景切换后的结果改称通过旧门槛。即使预测更好也需另行登记闭环成本试验。全部原始样本、路径评分、预测记录与源码无损归档；模型大权重仅本地，公开依赖revision与SHA。独立排序恒等式CRPS复算与冻结SHA检查通过。\n'
text+='\n## 解释与下一步\n\n固定适配器的总体CRPS和MAE均低于Merton及最新值参照，两探索性CRPS区间上界均低于零；支持在这组预先固定合成背景中继续研究。平稳背景两指标均改善，趋势背景CRPS略高于Merton且最新值更好，周期背景明显低于Merton但原Sundial比适配方案更好。总体适配MAE也高于原Sundial，因此不能称修正模块全面有效或Sundial必需。下一步可另登记小型订货闭环开发，保持需求背景和全部负例，先明确报告块到逐期需求的生成假设及预算；此处尚未实施成本实验。\n'
(ROOT/'docs/2026-10-14-sundial-scenario-results.md').write_text(text,encoding='utf-8')
print('SCENARIO_ARCHIVED',len(entries))
