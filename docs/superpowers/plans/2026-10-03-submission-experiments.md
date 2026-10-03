# 投稿正式实验 Implementation Plan

> **For agentic workers:** 使用 executing-plans 在当前任务内逐项执行；本计划不要求派生子代理。步骤采用复选框登记。

**Goal:** 将已登记的模型假设和固定库方案转成可审计的小规模正式确认，再逐步扩展多模型与机制实验。

**Architecture:** 继续调用固定作者环境与冻结Actor；开发实验保持归档。单独创建正式执行入口，配置驱动模型、方法、报告间隔和种子，输入先保存后重放，各模型/方法复用对应需求与预测随机数。

**Tech Stack:** 现有Python、NumPy、PyTorch、原作者环境与标准库JSON/CSV；绘图沿用现有matplotlib。

## 已完成的设计交付

- [x] 核对实际库存、需求、奖励及信息接口。
- [x] 写入 `docs/2026-10-03-model-assumptions-and-sources.md`。
- [x] 写入 `docs/2026-10-03-formal-experiment-protocol.md`。
- [x] 固定先80回合再扩大的分阶段预算，区分现成模块与待实现消融。

## Task 1：输入与冻结登记

- [x] 检索 `results`、`docs/artifacts` 中全部需求/事件种子；核对协议20261201..20261210尚未使用，记录检索范围和结果。
- [x] 新建 `experiments/formal_evaluation/prepare.py`：调用原生成器写完整5批需求与事件，仅序列生成，不加载控制器；保存201项来源、200项消费区间、冲击与截断比例，拒绝覆盖输入目录。
- [x] 保存最终执行代码、原模型/算子库哈希及依赖版本至新运行manifest；生成时记录协议哈希与输入摘要。

## Task 2：小规模正式执行入口

- [x] 新建 `experiments/formal_evaluation/run.py`，从输入文件读取需求，不边运行边重新生成；支持 `--training-directory`、`--methods`、`--report-interval`、`--input-directory`、`--run-name`，移除现有入口硬编码seed11模型目录的限制。
- [x] 复用 `experiments/deepseek_refinement/shadow.py` 与 `reports.py`，仅选择 `happo`/`llm_library`，对每模型方法重新初始化RNN、报告器和环境。正式入口不请求API。
- [x] 在单独开发输出目录做2条流程检查，核对输入哈希一致、每回合600节点期、通知前动作一致、无训练更新、信息审核和零修正影子回放。流程检查使用既有开发输入，不能消耗正式测试数据调实现。
- [x] 运行阶段A完整80回合；输出全部 `periods.csv`、`episodes.json`、`scores.json`、信息审核、失败记录与完成状态。

## Task 3：分析与阶段A报告

- [x] 新建 `experiments/formal_evaluation/analyze.py`：读取所有20配对，计算协议指标、20000次重采样及95%/97.5%区间，保存抽样种子、单位和完整配对CSV。
- [x] 生成全部20条配对图与平均时序PNG/PDF；复算归一化成本和总成本关系，显示退化个案。
- [x] 写 `docs/formal-evaluation-stage-a-results.md`，区分系统改善与LLM独立贡献，记录计算成本及停止原因；技术检查完成后提交推送。

## Task 4：正常需求下多训练种子

- [x] 使用已有 `experiments/learning_curve/run.py` 分别运行种子12..15，预算3000000、patience40、until-stable，run-name为 `curve_seed{seed}_formal_v1`。先查进程与完成记录，防止重复启动。
- [x] 完整保存每模型学习曲线、停止理由、实际最佳模型快照和加载审计；不能把预算耗尽称为稳定。仅在正常原需求上训练和选检查点。
- [x] 对同一已保存20轨迹评估新模型320回合，汇总五模型交叉配对与双向重采样结果。无需再次运行A的80回合，只有实现变化需另登记重跑理由。

## Task 5：机制诊断

- [x] 追加LLM首条无筛选、仅搜索无复核、固定随机候选同筛选三组；库首条索引0与随机种子20261230预先固定。随机诊断不冒充强基线。
- [x] 执行k=1/5全量敏感性；方法间同路径随机数，共享20轨迹不扩充独立样本数。
- [x] 汇总阶段C及局限。竞争算法、更多灾情或实时API路线另登记后再启动。

本次授权首先完成参数来源与正式协议文档。本计划中的训练、API及正式评估未在文档整理阶段启动；后续执行先完成现成入口的隔离适配与流程检查，再按协议增加规模。

阶段A于2026-10-03完整执行并审阅，具体记录见 docs/2026-10-03-formal-stage-a-implementation.md。历史输入查重和分析健壮性修订不改变本次控制结果。
