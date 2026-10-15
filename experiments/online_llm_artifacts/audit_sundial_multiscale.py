"""Independent path/label/loss/CRPS audit and lossless publication export."""
import csv,gzip,hashlib,json,math,winreg
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_multiscale_adapter/v1'
def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def digest(p):
 h=hashlib.sha256()
 with Path(p).open('rb') as f:
  while b:=f.read(8*1024*1024):h.update(b)
 return h.hexdigest()
def trace_hash(x):return hashlib.sha256(json.dumps(list(map(int,x[:200])),separators=(',',':')).encode()).hexdigest()
def crps(x,y):
 x=np.asarray(x,dtype=float);n=x.shape[0]
 return float(np.mean(np.abs(x-np.asarray(y)[None,:]).mean(0)-((2*np.arange(n)+1-n)[:,None]*np.sort(x,axis=0)).sum(0)/n**2))
def transform(case,raw,weights):
 x=np.clip(np.asarray(raw,dtype=np.float64),0,20);blocks=case['block_history'];mu=x.mean(0);recent=np.array(blocks[-3:],dtype=float);t=np.arange(len(recent));denom=np.sum((t-t.mean())**2)
 slope=np.sum((t-t.mean())*(recent-recent.mean()))/denom if denom else 0
 f=np.array([[1,m/20,blocks[-1]/20,(recent.mean()-np.mean(blocks[-10:]))/20,slope/20,np.std(blocks[-5:])/10,(j+1)/8,case['report_age']/2] for j,m in enumerate(mu)])
 g=1/(1+np.exp(-(f@weights['wg'])));b=6*np.tanh(f@weights['wb']);a=np.exp(np.log(4)*np.tanh(f@weights['wa']))
 return x,np.clip(mu[None,:]+(g*b)[None,:]+(1+g*(a-1))[None,:]*(x-mu[None,:]),0,20)
def objective(cases,predictions,weights,variant,split):
 losses=[]
 for c in cases:
  if c['split']!=split:continue
  x,z=transform(c,predictions[c['id']]['raw_blocks'],weights);age=c['report_age'];starts=[i for i in range(-age,20,3) if i>=0 and i+3<=20];indices=[(i+age)//3 for i in starts];label=np.array(c['future_label'])
  block=crps(z[:,indices],[label[i:i+3].mean() for i in starts]);proxy=np.repeat(z,3,axis=1)[:,age:age+20]
  prefix=crps(np.cumsum(proxy,axis=1)[:,[4,9,19]]/np.array([5,10,20]),np.cumsum(label)[[4,9,19]]/np.array([5,10,20]))
  losses.append(block+(.25*prefix+.05*np.abs(z-x).mean() if variant=='multiscale24' else 0))
 return float(np.mean(losses)+.001*(np.square(weights['wb']).mean()+np.square(weights['wa']).mean()))
def main():
 done=read(OUT/'completed.json');assert done['windows']==900 and done['api']==0
 for p,sha in read(OUT/'freeze.json')['sha256'].items():assert digest(p)==sha,p
 historical=read(OUT/'historical.json');used=set(historical['consumed_hashes'])
 for source in historical['source_files']:assert digest(source['path'])==source['sha256'],source['path']
 inputs=read(OUT/'inputs.json');cases=read(OUT/'cases.json');predictions={p['case_id']:p for p in read(OUT/'predictions.json')};lookup={i['path_id']:i for i in inputs}
 assert len(inputs)==len(lookup)==150 and len(cases)==len(predictions)==900
 new=set()
 for item in inputs:
  pair={trace_hash(item['base'][0]),trace_hash(item['shock'][0])};assert not pair&used and not pair&new
  if item['type']!='normal':assert len(pair)==2
  new.update(pair)
  assert len(item['base'][0])==len(item['shock'][0])==200
 for c in cases:
  item=lookup[c['path_id']];p=c['decision_period'];age=(p-1)%3
  assert c['split']==item['split'] and c['report_age']==age and c['background']==item['background'] and c['type']==item['type']
  delivered=p-1-age;history=item['shock'][0][:delivered]
  expected=[sum(history[i:i+3])/3 for i in range(0,delivered,3)]
  assert c['block_history']==expected and c['future_label']==item['shock'][0][p-1:p+19]
  assert len(c['block_history'])*3+age==p-1
  pred=predictions[c['id']];raw=np.asarray(pred['raw_blocks']);assert raw.shape==(32,math.ceil((age+20)/3)) and np.isfinite(raw).all()
  expected_seeds=[int.from_bytes(hashlib.sha256(f"sundial-closed-loop-v1|{c['id']}|{purpose}".encode()).digest()[:8],'big')%(2**63-1) for purpose in ('search','review')]
  assert pred['sampling_seeds']==expected_seeds and expected_seeds[0]!=expected_seeds[1]
 for split,n in (('train',120),('dev',30)):
  local=[i for i in inputs if i['split']==split];assert len(local)==n
  for item in local:assert sum(c['path_id']==item['path_id'] for c in cases)==6
  cells={(i['background'],i['type']) for i in local};assert len(cells)==15
  assert len({sum((i['background'],i['type'])==cell for i in local) for cell in cells})==1
 initial=read(ROOT/'results/sundial_adapter_development/v1/best_adapter.json')['weights'];loss_checks=[]
 for variant in ('crps24','multiscale24'):
  curve=read(OUT/f'{variant}_curve.json');best=read(OUT/f'{variant}_best.json');final=read(OUT/f'{variant}_final.json')
  assert best['selected_epoch']==min(range(len(curve)),key=lambda i:curve[i]['dev_objective'])
  assert final['epoch']==curve[-1]['epoch'] and len(curve)<=201
  if final['stop_reason']=='patience25':assert len(curve)-1-best['selected_epoch']==25
  for label,weights,row in [('initial',initial,curve[0]),('best',best['weights'],curve[best['selected_epoch']]),('final',final['weights'],curve[-1])]:
   for split in ('train','dev'):
    actual=objective(cases,predictions,weights,variant,split);expected=row[split+'_objective'];error=abs(actual-expected);assert error<1e-9,(variant,label,split,error)
    loss_checks.append(dict(variant=variant,checkpoint=label,split=split,absolute_error=error))
 metrics=read(OUT/'metrics.json');rows={(r['case_id'],r['method']):r for r in metrics['per_case']};scoring=read(OUT/'scoring_values.json');assert len(scoring)==1080
 for r in scoring:
  value=rows[r['case_id'],r['method']]
  assert abs(crps(r['block_samples'],r['block_labels'])-value['block_crps'])<1e-10
  assert abs(crps(r['prefix_samples'],r['prefix_labels'])-value['prefix_crps'])<1e-10
  samples=np.asarray(r['block_samples'],dtype=np.float32 if r['method']=='native_sundial' else np.float64)
  if r['method']=='native_sundial':samples=np.asfortranarray(samples)
  assert abs(np.abs(samples.mean(0)-r['block_labels']).mean()-value['block_mae'])<1e-10
 for p in metrics['paths']:
  for method,value in p['metrics'].items():
   local=[r for r in metrics['per_case'] if r['path_id']==p['path_id'] and r['method']==method];assert len(local)==6
   for key in value:assert abs(sum(r[key] for r in local)/6-value[key])<1e-12
 for method,value in metrics['overall'].items():
  for key in value:assert abs(sum(p['metrics'][method][key] for p in metrics['paths'])/30-value[key])<1e-12
 main=metrics['overall']['multiscale24'];old=metrics['overall']['old24'];checks=dict(block_better_than_old=main['block_crps']<old['block_crps'],prefix_better_than_old=main['prefix_crps']<old['prefix_crps'],prefix_better_than_merton=main['prefix_crps']<metrics['overall']['merton']['prefix_crps'],prefix_better_than_latest=main['prefix_crps']<metrics['overall']['latest_report']['prefix_crps'],no_shock_type_above_old_5_percent=all(v['multiscale24']['prefix_crps']<=1.05*v['old24']['prefix_crps'] for k,v in metrics['by_type'].items() if k!='normal'))
 assert checks==metrics['gate_checks'] and all(checks.values())==metrics['gate_passed']==done['gate_passed']
 model=read(OUT/'model_verification.json');assert model['before']==model['after']=='2a8da165e050f32969561cb0585b901f9423d4a72911fb5e613aefd1ebe6c86d'
 audit=dict(status='passed',paths=150,windows=900,development_scoring_rows=1080,loss_recomputations=loss_checks,causal_history_recomputed=True,whole_path_split_and_history_exclusion=True,sorted_crps_independently_recomputed=True,gate_recomputed=True,api=0)
 (OUT/'independent_audit.json').write_text(json.dumps(audit,indent=2),encoding='utf-8')
 text='# Sundial多尺度适配器再训练开发结果\n\n120条训练路径、30条开发路径，三背景×正常/四冲击等权；900个重叠窗口不是独立需求样本。Sundial/HAPPO冻结，仅24参数适配器训练；API0，无库存成本新成绩。原适配器与代表路径负面结果全部保留。\n\n## 开发预测结果\n\n|方法|块CRPS|块MAE|部署整数前缀CRPS|可微代理前缀CRPS|\n|---|---:|---:|---:|---:|\n'
 for name,v in metrics['overall'].items():text+=f"|{name}|{v['block_crps']:.6f}|{v['block_mae']:.6f}|{v['prefix_crps']:.6f}|{v['proxy_prefix_crps']:.6f}|\n"
 text+='\n## 预先固定的继续门槛\n\n'
 for name,v in checks.items():text+=f'- {name}: {v}\n'
 text+=f"\n整体门槛通过：{metrics['gate_passed']}。主方法始终为multiscale24，不因消融成绩替换。"
 text+='若通过，仅可另登记同状态同候选的无API决策诊断，不能将预测改善称系统成本改善。若失败，本版本收尾，不追加付费或调整阈值至胜出。\n\n## 训练与独立核验\n\n'
 for variant in ('crps24','multiscale24'):
  best=read(OUT/f'{variant}_best.json');final=read(OUT/f'{variant}_final.json');text+=f"- {variant}：best epoch{best['selected_epoch']}，终止epoch{final['epoch']}，{final['stop_reason']}；best/final均保留。\n"
 text+='\n独立重算150路径隔离/历史碰撞、900因果报告与标签、12次初始/best/final训练开发目标、1080条预测评分及继续门槛通过。初次审计以float64重建原生Sundial的float32 MAE而失败，最大差约4.92e-7；仅恢复float32仍因数组C/F布局的归约顺序差异失败，最大1.43e-6。已保留失败、原脚本和布局诊断，恢复原float32及高级索引的Fortran布局后逐值一致，不修改生产数据或门槛。评估按30路径等权，窗口不假独立；当前是开发选模，不是最终未见确认。原生产适配器保持float32样本均值，新适配器float64明示；训练前缀为可微代理，部署整数分配单独评价。\n\n## 类型分解（部署前缀CRPS）\n\n|类型|旧适配器|新CRPS目标|新多尺度目标|\n|---|---:|---:|---:|\n'
 for kind,v in metrics['by_type'].items():text+=f"|{kind}|{v['old24']['prefix_crps']:.6f}|{v['crps24']['prefix_crps']:.6f}|{v['multiscale24']['prefix_crps']:.6f}|\n"
 report=ROOT/'docs/2026-10-15-sundial-multiscale-adapter-results.md';report.write_text(text,encoding='utf-8')
 target=ROOT/'docs/artifacts/sundial_multiscale_adapter_completed_v1';assert not target.exists();target.mkdir(parents=True)
 with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as env:key=winreg.QueryValueEx(env,'DEEPSEEK_API_KEY')[0].encode()
 files=[p for p in OUT.rglob('*') if p.is_file() and 'archive' not in p.relative_to(OUT).parts]+list((ROOT/'experiments/sundial_multiscale_adapter').glob('*.py'))+[Path(__file__),report,ROOT/'docs/superpowers/specs/2026-10-15-sundial-multiscale-adapter-design.md',ROOT/'docs/superpowers/plans/2026-10-15-sundial-multiscale-adapter.md']
 entries={}
 for i,p in enumerate(files):
  raw=p.read_bytes();assert key not in raw;dest=target/'files'/f'{i:03d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(raw,mtime=0));assert gzip.decompress(dest.read_bytes())==raw
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=digest(p),gzip_sha256=digest(dest))
 (target/'manifest.json').write_text(json.dumps(dict(files=entries,lossless=True,credential_absent=True,checkpoint_weights_local_only=True,api=0),ensure_ascii=False,indent=2),encoding='utf-8')
 print('MULTISCALE_INDEPENDENT_AUDIT_EXPORTED',len(entries),metrics['gate_passed'],metrics['overall'])
if __name__=='__main__':main()
