"""Lossless calibration development and user-stopped cost batch exports."""
import gzip,hashlib,json,winreg
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'results/sundial_matured_calibration/v1';OLD=ROOT/'results/sundial_closed_loop_development/development_v2'
read=lambda p:json.loads(p.read_text(encoding='utf-8-sig'))
digest=lambda b:hashlib.sha256(b).hexdigest()
assert read(OUT/'independent_verification.json')['status']=='passed' and read(OUT/'completed.json')['new_windows']==180
assert read(OLD/'user_stopped.json')['status']=='stopped_by_user'
with winreg.OpenKey(winreg.HKEY_CURRENT_USER,'Environment') as e:key=winreg.QueryValueEx(e,'DEEPSEEK_API_KEY')[0].encode()
def export(target,files):
 assert not target.exists();target.mkdir(parents=True);entries={}
 for index,p in enumerate(dict.fromkeys(files)):
  blob=p.read_bytes();assert key not in blob;dest=target/'files'/f'{index:04d}.gz';dest.parent.mkdir(exist_ok=True);dest.write_bytes(gzip.compress(blob,mtime=0));assert gzip.decompress(dest.read_bytes())==blob
  entries[dest.relative_to(ROOT).as_posix()]=dict(source=str(p),source_sha256=digest(blob),gzip_sha256=digest(dest.read_bytes()))
 (target/'manifest.json').write_text(json.dumps(dict(files=entries,lossless=True,credential_absent=True,negative_and_partial_results_preserved=True,pretrained_weights_local_only=True),ensure_ascii=False,indent=2),encoding='utf-8')
 return len(entries)
files=[p for p in OUT.glob('*') if p.is_file()]+list((ROOT/'experiments/sundial_matured_calibration').glob('*.py'))
files += [ROOT/'docs/superpowers/specs/2026-10-14-sundial-matured-calibration-design.md',ROOT/'docs/superpowers/plans/2026-10-14-sundial-matured-calibration.md',ROOT/'results/sundial_matured_calibration_run_v1.log',Path(__file__)]
new_count=export(ROOT/'docs/artifacts/sundial_matured_calibration_v1',files)
old_count=export(ROOT/'docs/artifacts/sundial_closed_loop_stopped_v2',[p for p in OLD.rglob('*') if p.is_file() and 'archive' not in p.relative_to(OLD).parts])
m=read(OUT/'validation_metrics.json');cached=read(OUT/'cached_metrics.json');done=read(OUT/'completed.json')
text='# Sundial成熟报告误差校准结果\n\n'
text+='用户停止的成本批未重启。本轮只增加回合内统计校准，Sundial128M和24参数适配器不更新，API0、没有新订货成本实验。参考COSA冻结输出校正、DSOF延迟标签思路，但不是其官方实现。\n\n'
text+='## 原持续突增诊断\n\n两个已完成seed在同一持续突增路径上，旧adapter成本18.738333/20.478333高于Merton17.506667/19.818333。完全在高需求区间的六个20期窗口，native逐期均值偏差约-2.04/-2.09，adapter仍-1.70/-1.61。旧模型输出存在偏低迹象，但不同LLM候选与筛选/复核也影响成本，不作单因归因；这不是尚未跑到的线性趋势背景结论。\n\n'
text+='## 实现与固定范围\n\n只登记第一个完全未来三期块预测；报告完整送达后才使用真实报告均值计算残差。每报告块最多一个标签，最近3成熟误差、最多18期陈旧，半幅中位数校准、最大±3；旧新共享原始样本和整数逐期分配。无成熟误差则原样，每路径清空，不读取冲击类别或结束时点。没有根据成绩扫描超参。\n\n'
text+='缓存回放两个完成seed全部四类，共214窗口、8个路径×模型组合（仅4条不同物理需求路径）。另冻结后生成12新Poisson10路径，四类各3，180重叠窗口。全部五参照使用6部署路径逐期CRPS/MAE，和旧32样本报告块指标不同，不能直接跨表比较。\n\n'
text+='|范围|预测器|逐期CRPS|逐期MAE|平均偏差|\n|---|---|---:|---:|---:|\n'
for scope,values in [('旧记录回放总体',cached['overall']),('新12路径总体',m['overall']),('新路径持续突增',m['by_type']['sustained_surge'])]:
 for method,v in values.items():text+=f"|{scope}|{method}|{v['crps']:.6f}|{v['mae']:.6f}|{v['bias']:.6f}|\n"
text+='\n## 全类型与结果\n\n|类型|旧适配CRPS|新校准CRPS|旧适配MAE|新校准MAE|\n|---|---:|---:|---:|---:|\n'
for kind,v in m['by_type'].items():text+=f"|{kind}|{v['adapted']['crps']:.6f}|{v['calibrated']['crps']:.6f}|{v['adapted']['mae']:.6f}|{v['calibrated']['mae']:.6f}|\n"
text+=f"\n固定门槛通过：{done['fixed_gate_passed']}。新校准总体与四类型CRPS/MAE均高于旧adapter，持续突增偏差绝对值只略减，预测准确度反而下降。完整失败保留，不进入付费成本验证，不根据同12路径调参数到胜出。\n"
text+='\n结果表明简单近期误差平移不足以解决问题：报告含随机波动，成熟误差有延迟，校准仅由近期块误差估计，不能保证20期预测分布或规则排名改善。该解释仍是机制推测，未证明所有在线适配无效。下一种设计需先区分持续水平变化与短期噪声、预测距离及块转逐期分布误差，另登记训练/开发选择与新验证，不直接强行抬高预测。\n'
text+='\n独立审核：成熟时间、首个完全未来块、标签去重、路径状态隔离、真实需求变换/查重/报告因果、scalar CRPS/MAE和路径聚合、所有冻结source/model/adapter SHA。最大数值差2.6645352591003757e-15。新试验和用户停止成本批完整原始/部分/API费用分别无损gzip归档；大预训练权重仅本地，公开revision/SHA。\n'
(ROOT/'docs/2026-10-14-sundial-matured-calibration-results.md').write_text(text,encoding='utf-8')
print('LOSSLESS_CALIBRATION_AND_STOPPED_EXPORT',new_count,old_count)
