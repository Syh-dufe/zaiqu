# Base-stock重新开发执行计划

**Goal:** 新开发路径选z，独立留出检查，固定后补当前Sundial路径传统基线。
**Architecture:** 复用冻结BaseStock策略、episode与独立数值审核，新的输入划分、有限扫描、唯一驱动及原始记录。
**Runtime:** 已有CPU Python/NumPy；API0；不训练神经网络。

- 新目录experiments/base_stock_recalibration，根results/base_stock_recalibration/v1。
- 固定H40/L4/z整数0..19，初始历史、取整、台账不变。来源与选择目标依设计。
- 注册前冻结代码与协议，历史查重后生成开发24/留出30路径；正反条件均运行。
- 逐回合保存完整CSV.gz并独立复算，正常/冲击前缀一致。
- 开发上限960回合；留出上限180；固定路径新增上限12，合计1152回合691200节点期。
- selected、reference8、historical2三标签；重复配置共享同一次真实仿真，不当新增样本。
- 选择仅看开发等权成本，固定SHA后运行留出与原固定路径，不据留出重选参数。
- 所有20个配置和退化保留；错误保留failed及进度，不自动重试。
- 无损注册包推送且Git字节核验后启动，完成后独立复核/完整归档/报告README推送。

此为用户已明确批准设计的实施；不是放弃或替换旧z2成绩，也不修改任何旧冻结文件。
