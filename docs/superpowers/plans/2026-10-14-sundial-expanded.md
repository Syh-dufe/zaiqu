# Sundial expanded validation Implementation Plan

**Goal:** 固定新20路径，检验Sundial与原Merton报告块预测均值和分布的差异。

**Architecture:** 冻结旧预测实现/官方权重/依赖，新prepare生成查重输入；独立首次run预测；按路径聚合并分层配对bootstrap，不进入库存闭环。

**Tech Stack:** 既有Python3.12/Torch CPU/Sundial缓存，numpy、JSON、SHA256。

- [ ] prepare.py验证旧试用freeze、锁定本轮源码/设计，再查历史路径并按20271701..50顺序接受5批四类型输入；保存20路径与120因果窗口。
- [ ] run.py使用固定官方模型与两个16样本流，Merton复用原公开路径实现；保存全部逐窗口原样本和运行时间，前后参数hash一致，启动锁防重跑。
- [ ] analyze.py在完整对齐报告块重算CRPS/MAE，六窗口先聚合到路径，四类型五路径分层重采样20000次，两97.5%主指标CI、所有退化和各类型均保留。
- [ ] verify.py以独立标量算法和独立bootstrap迭代复核指标与区间、120身份及因果输入，核对冻结hash。
- [ ] 无损公开全部输出与源/输入/权重revision、SHA，权重仅本地；脱敏缺席/Git精确字节核对，报告README提交push。
