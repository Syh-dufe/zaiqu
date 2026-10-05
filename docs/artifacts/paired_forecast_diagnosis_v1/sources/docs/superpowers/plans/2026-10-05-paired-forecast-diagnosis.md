# 同状态配对预测诊断（无API）

沿用用户授权的失败机制排查。固定分析report-trigger development_v2的十个已完成任务、两个方法全部320个生成事件；不得按误差选窗口或删除事件。输入属于已用开发资料，不是新确认；不训练、不调用API、不改变模型或控制器。

每事件用当时完整已送达报告重建history：每个k=3报告demand_mean重复三次。period=decision_period−1，age=period−delivered_through。先用冻结shadow.forecasts原定义的merton方式重现保存的六条预测路径，要求320事件逐值一致；之后同事件调用该定义已有residual方式，六条路径、相同随机种子规则、最多20期。residual实现不额外推进age，是现有代码行为，不能称完整不确定性滤波或新算法。不会用真实隐藏历史构造预测。

真实后续需求仅用于事后误差标签，按CSV的node0/shock相同group、trace与decision_period起读取，不向API或控制器反馈。主诊断量是六路径均值的逐期MAE；同时记录平均预测偏差、平均路径MAE、六路径最小到最大覆盖率（仅描述，不能称置信覆盖）。所有320事件独立配对，按事件原方法、类型、模型/批次汇总；同一路径多个窗口、五模型重复不作为独立样本。不做显著性。

输出新目录 `results/forecast_diagnosis/paired_v1`，脚本 `experiments/online_llm_artifacts/paired_forecast_diagnosis.py`。先保存freeze/manifest再执行；锁定脚本、该计划、原shadow、十任务scores/delivered_reports/periods/demands/completed及父completed/summary哈希。拒绝覆盖已执行产物。源码/输入变化或原预测无法重现即停止保存failed，不盲重跑。

如果残差方式在合并以及四个类型的MAE均严格低于Merton，且两种事件来源方法分组也均低于，才认为有充分开发理由设计下一项预测替换小型闭环比较。否则不启动此替换的付费开发，不调历史窗口/残差采样到胜出；完整报告后按现有投稿路线准备基线和机制消融，保持原实时主方法。此门槛只控制后续资源投入，不宣称预测改善必然改善补货。

核验原预测320/320重现、报告可见性、未来标签索引、全部案例/来源哈希及汇总算术后，归档输入来源manifest、逐事件两组预测与标签、源码/计划、结果与不利案例，字节保护/导出/Git哈希核对；更新报告并推送。
