# TimesFM闭环实验 Implementation Plan

> For agentic workers: Use executing-plans in the current session, task by task. No subagent dispatch is required. User authorized sequential execution.

**Goal:** 检验冻结TimesFM预测经因果路径构造后是否降低完整订货成本。

**Architecture:** 新目录实现预测器与路径接口，独立适配既有guard_pool；旧冻结源不修改。A无API诊断、B闭环开发、C独立确认分别有不可覆盖结果根及启动锁。

**Tech Stack:** 现有Python3.12/Torch CPU、TimesFM2.5独立缓存、原DeepSeek Client、JSON/CSV与SHA256。

## 文件映射

- 新建experiments/timesfm_path_development/predictor.py：报告块到中心，加载冻结模型，缓存仅限同一回合同一报告身份。
- 新建experiments/timesfm_path_development/paths.py：固定随机种子、累计扰动、取整、3+3分流。
- 新建experiments/timesfm_path_development/diagnose.py：48窗口/32路径/CRPS与边界诊断，不读未来生成路径。
- 新建experiments/timesfm_path_development/audit.py：独立因果、身份、参数hash与指标复算。
- 新建experiments/timesfm_closed_loop_development/controller.py、runner.py、batch.py、analyze.py：四组分派、原核心控制行为保持、预算锁、配对完整成本统计。
- 新建experiments/timesfm_closed_loop_confirmation/：仅开发门槛通过后创建，独立冻结与新输入生成。
- 结果根分别results/timesfm_path_development/development_v1、results/timesfm_closed_loop_development/development_v1、results/timesfm_closed_loop_confirmation/confirmation_v1。

## Task 1：登记范围并核对已有试用

- [x] 写完整设计、两种替代路线及固定阶段门槛。
- [ ] 只读核对试用completed、48 cases、192方法窗口指标、freeze SHA；将结论写独立readiness.json。
- [ ] 核对原controller生成与重新筛选两处forecast调用，明确注入只影响paths，不进入LLM提示。

## Task 2：无API路径开发

- [ ] 实现predictor和paths；接口输入仅报告块、age、H与公开身份，输出search/review路径和审计metadata。
- [ ] paths算法逐步生成独立z/n/z2，累加W及v，按设计转换、截断与floor(x+0.5)取整；新中心的原Merton预测使用独立流。
- [ ] 登记源码、模型、依赖、输入、协议SHA后，唯一首次生成48×4×32路径；硬检查与真实未来评分分离。
- [ ] audit从原始路径重算CRPS/MAE/总需求误差与边界统计；保留全部窗口。完成报告并根据固定门槛作go/no-go，不重调该版本。

## Task 3：开发接线与预登记

- [ ] 独立controller在generation/rescreen都分派四forecast provider；原SYSTEM、Client、候选、修订、复核与执行逻辑逐项核对。
- [ ] normal和通知前四组等HAPPO；冻结参数前后相同；短程无API接线保存输出，不冒称性能试验。
- [ ] 注册320回合、192000节点期与2560/1280首次API预算；402恢复累计5120/2560。独立清单锁定后提交推送，再首次运行唯一batch。

## Task 4：开发收尾

- [ ] 核对320回合/192000唯一节点期与四方法×五seed×两batch×四类型×两regime全集；失败attempt另计费用。
- [ ] 逐期重算成本、通知与报告因果、模型hash、格式失败、真实修正、API/tokens及耗时。
- [ ] 比较全部四组；按设计固定开发门槛判断。不通过则停止该版本确认，写诊断；不启动自动付费调参。

## Task 5：独立确认（条件步骤）

- [ ] B通过后冻结C源码/参数，再按设计种子顺序生成并查重最先10合格批；保持全部五模型。
- [ ] 登记1600回合/960000节点期、三主比较多重性、12800/6400首次API预算与失败恢复总额。
- [ ] 无API合同审核及注册包提交推送后，首次唯一驱动开跑。
- [ ] 20000交叉bootstrap与独立复算；完整不利结果、失败、额外算力及公开归档范围报告。

## Task 6：每阶段收尾

- [ ] 报告阶段实际开销和限制，无损归档、脱敏及Git精确字节审核。
- [ ] README与报告提交推送。冻结后新增修复另版本保留旧失败，不覆盖、不吞审核错误。

执行原则：阶段推进取决于已登记门槛；单元测试不额外启动，实验契约与独立指标核验属于本实验。此流程不要求重复询问已授权的常规阶段操作。
