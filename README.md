# 灾害冲击下多级物资补给研究

本项目先建立 Liu 官方库存模型的业务解释兼容版本，再逐项研究洪灾需求变化与 LLM 生成补货规则。兼容启动器只增加业务命名与命令行种子列表适配，验证记录见 docs。

## 当前版本

投稿准备材料：

- [模型假设与参数来源](docs/2026-10-03-model-assumptions-and-sources.md)
- [正式实验协议v1](docs/2026-10-03-formal-experiment-protocol.md)
- [分阶段执行计划](docs/superpowers/plans/2026-10-03-submission-experiments.md)

正式协议先登记80回合确认，再扩展多训练种子与消融；目前是设计交付，尚未启动该正式实验。

直接调用官方原始 `train_env.py`，只指定独立的场景和实验名称。库存状态转移、需求、奖励、网络、HAPPO 顺序更新、默认训练预算及早停均使用官方实现。

| 官方节点与变量 | 业务解释 |
|---|---|
| 下游节点 | 社区物资供应点 |
| 中间节点 | 区域物资仓库 |
| 上游节点 | 物资供应中心 |
| 订货量 | 向上游申请补充的标准批次 |
| 库存 | 尚未发放的储备物资 |
| 欠货 | 允许后续补供的未满足需求 |

数量和时间采用归一化批次与仿真期。上述兼容训练入口保持原模型规则；另有需求冲击和DeepSeek补货修正实验入口。尚未加入车辆、道路或真实灾区数据，不声称具有真实灾区验证结果。

## 上游来源

- [Liu 官方仓库](https://github.com/xiaotianliu01/Multi-Agent-Deep-Reinforcement-Learning-on-Multi-Echelon-Inventory-Management)
- 固定提交：`a7e5a3e83e21565a5799483bc534e39635ec65dd`
- [正式论文](https://doi.org/10.1177/10591478241305863)

上游源码由脚本获取到本地忽略目录，本仓库不复制发布它。上游使用权限及依赖要求以其提供的信息为准；本仓库未对上游代码授予许可。

## 使用

需要 Git 和 Python。在仓库根目录执行：

```powershell
python scripts/setup_upstream.py
python -m venv .venv
& .venv/Scripts/python.exe -m pip install -r external/liu-inventory/requirements.txt
& .venv/Scripts/python.exe experiments/emergency_compatibility/train.py --describe
```

官方说明使用 Python 3.8。依赖兼容性需要按实际环境确认，不把不同依赖版本的运行称为完全一致复现。

在需要训练时执行（默认十个种子、每个最多三百万步，原始早停）：

```powershell
& .venv/Scripts/python.exe -u experiments/emergency_compatibility/train.py
```

短预算流程验证使用独立审计脚本：

```powershell
& .venv/Scripts/python.exe -u scripts/verify_compatibility.py
```

结果由官方脚本写到 `external/results/MyEnv/Emergency_Replenishment_Compatibility/happo/<run-name>/`，包含来源记录、模型和原始训练输出。已有同名目录拒绝重跑。模型、原始数据、日志、API 密钥和上游源码均不上传。

官方 `--seed` 参数默认是列表，但显式传值会变成整数；兼容入口将显式种子解析为列表，保持默认值不变。官方 runner 在预算耗尽且未早停时隐式返回 None；因此直接指定短预算不保证正常结束或保存模型。审计脚本保留官方更新过程，只在运行完成后保存最终模型并评估，记录为 `audit_final_policy_not_official_best`，不冒充官方最佳检查点。审计源码不修改上游文件。

## 下一步

1. 固定业务解释、单位与假设。
2. 用户要求验证时，用相同参数检查官方入口和兼容入口的一致性。
3. 逐步增加训练预算，检查学习稳定性。
4. 单独加入洪灾需求变化。
5. 研究 LLM 生成、筛选与冻结补货调整规则。

当前暂不开展基线排名；历史实验和停止的复现记录保留在原本地工作区。

## 学习曲线实验

用户授权后的扩大预算观察入口（默认种子 11、50,000 步）：

```powershell
& .venv/Scripts/python.exe -u experiments/learning_curve/run.py
```

本地结果写入 `results/learning_curve/curve_seed11_50k_v1/`，模型写入官方结果目录的 `curve_snapshots/` 和 `final_models/`。保留原始训练、奖励、评估频率和早停；额外记录曲线及保存快照。最终评估与最终模型另存，不替代官方已选模型。

绘图依赖可安装固定的 `matplotlib==3.10.8`，同时保持现有 `numpy==1.26.4`，避免绘图安装改变训练依赖：

```powershell
& .venv/Scripts/python.exe scripts/plot_learning_curve.py results/learning_curve/curve_seed11_50k_v1
```

## DeepSeek与冻结HAPPO

采用已训练的250000步最佳模型，现场通知后生成补货规则；影子仿真仅使用已观察状态及历史需求预测，筛选后执行有限修正，无HAPPO重训。

- [预定协议](docs/2026-10-03-llm-refinement-protocol.md)
- [全部开发结果与验证登记](docs/2026-10-03-llm-refinement-results.md)
- [首轮失败与原因分析](docs/2026-10-03-llm-improvement-design.md)
- [v3新观测后的反馈修订](docs/2026-10-03-llm-refinement-v3.md)
- [20条确认实验预定协议](docs/2026-10-03-llm-confirmation-20.md)
- [接口与写作可声明范围](docs/2026-10-03-llm-method.md)

需先存在本地训练模型，并将API密钥提供给子进程（不要写入代码或结果）：

```powershell
$env:DEEPSEEK_API_KEY = [Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY','User')
python experiments/deepseek_refinement/run.py --run-name my_unique_run
python experiments/deepseek_refinement/summarize.py results/deepseek_refinement/my_unique_run
```

入口拒绝覆盖已有目录。本轮最多12次API请求，系列累计最多120次，无自动重试。默认两条开发需求；正常情形无现场通知，不能据此验证自动报警或虚假通知鲁棒性。成本下降须连同缺货和额外计算开销报告，全部不利结果保留。

## 当前已验证的LLM算子库版本

先在开发阶段由DeepSeek生成可复用补货算子，在线用当前状态与因果预测筛选；HAPPO保持冻结。它与每事件实时请求LLM的路线分别记录。

20条全新需求测试中，相对同一原HAPPO，平均系统成本下降2.45%，下游平均积压下降1.86%，两项配对bootstrap95%区间均低于0。仍有个案退化，人工规则的平均成本和缺货更低，不能称LLM在所有对照中最佳。仅单训练种子、固定仿真需求冲击与可靠通知，不是真实灾区验证。

- [独立测试完整报告](docs/2026-10-03-llm-library-confirmation-results.md)
- [固定库设计及语法修复记录](docs/2026-10-03-llm-operator-library.md)
- [运行前登记](docs/2026-10-03-llm-library-confirmation-20.md)

当前库在开发中调用API，测试不请求API；无需密钥，可对已有本地模型运行小型库实验：

```powershell
python experiments/deepseek_refinement/run.py --run-name my_unique_library_run --operator-library docs/artifacts/operator_discovery_v1/repaired_library.json --correction-periods 5 --predictor merton
python experiments/deepseek_refinement/summarize.py results/deepseek_refinement/my_unique_library_run
```

全部历史失败/不显著结果、缓存预测诊断和新确认结果均保留。后续需要等候选数手工对照、多训练种子、独立重复及可靠性实验进一步分析LLM贡献。

## 定期灾区需求报告（已完成小型开发实验）

在固定库模式增加 `--report-interval 1`、`3` 或 `5`，仅用已送达的需求区间汇总计算规则特征和预测。HAPPO保持原本地观测，不重新训练；不传该选项保留旧信息模式。新模式人工对照提供三档固定修正强度，匹配库的三候选筛选预算。

时间顺序、信息边界、预测近似及小型配对实验命令见[接入说明](docs/2026-10-03-periodic-demand-reports.md)。

同一组4条新需求轨迹、报告间隔1/3/5周期，共72回合（含正常参照），训练更新和API请求均为0。LLM组合平均成本分别比原HAPPO低4.95%/2.52%/4.38%，下游平均积压低1.92%/2.02%/1.60%；人工规则组合三档均更好，3周期档存在一条LLM成本退化。仅开发敏感性结果，不作显著性或LLM最优结论；三档共享4条轨迹。

[完整实验报告](docs/2026-10-03-periodic-demand-reports-results.md)包含全部逐轨迹差异、信息核查和原始压缩产物。旧20条轨迹的提升不能直接外推到本场景。
