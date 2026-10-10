# 混合冲击HAPPO训练登记

用户批准进行正常训练策略、完整实时策略与冲击训练策略的后续对比。本阶段只从头训练HAPPO种子11..15，训练无需API。模型不是在已用测试需求上微调。

方案：docs/superpowers/specs/2026-10-10-mixed-shock-happo-design.md；执行计划：docs/superpowers/plans/2026-10-10-mixed-shock-happo.md。

每次训练生成正常/单峰/持续/双峰/回落之一，概率各20%；发生时点、长度和倍率随机。原Merton基础生成器、库存环境、局部actor7维、集中critic21维、奖励和HAPPO更新不变。新100条平衡混合验证只用于模型选择，与原20正常验证的选择目标和计算开销不同。同seed不保证同初始权重或训练轨迹；不能称完全等计算预算。

最大串行并发1、每seed3m步上限、patience40、原经验稳定标准、全部种子保留。最终灾情比较需各方法冻结后另生成未见路径；本阶段不会调用LLM或自动进行该测试。

独立静态审阅未发现接口/预算/保存/审计阻断；作者SubprocVecEnv实际同进程实例化Env，进程内需求覆盖能作用于训练和验证；完成审计在独立进程中覆盖相同验证输入后重新加载原best/final审核。新路径防覆盖和永久启动锁。

冻结核验覆盖旧11..20 scheduled-best共60文件；旧final与中间快照依靠隔离输出保持，不宣称其全部字节均已逐次hash核验。继承的compatibility_manifest及curve/config原注释指向正常需求，新mixed_demand_override.json、manifest与本说明明确实际需求覆盖，不能根据继承注释误认训练正常需求。

模型选择数据不是性能测试结果；训练结束/早停不是收敛证明。完整训练ledger、曲线、快照、best/final、停止与审核记录全部保留，完成后另出报告。
