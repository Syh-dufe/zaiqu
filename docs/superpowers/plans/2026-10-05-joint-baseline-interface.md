# 共同基线接口验证实施计划

按已授权设计依次执行，工作区zaiqu-formal-bc，原源码和训练记录均不改。

- 新增experiments/joint_baseline/frozen.py：读取各seed best模型、配置和审核，核对IPPO身份/criticflag、actor/critic参数SHA，返回原CRunner所需配置。依赖仅作者冻结代码和标准加载。
- 新增experiments/joint_baseline/preflight.py：先独占登记results/joint_baseline/interface_v1，锁定所有新源码/设计/协议/作者Python、原验证20需求、旧v5b batch01输入及全部IPPO档案模型。语法/预算/无API检查。
- 将每seed模型加载到原DummyVecEnv，原20正常需求复算best成本绝对误差<=1e-8。另用记录包装器重放旧batch01正常/冲击4路径，每步成本必须I+B；报告必须在观察后递送，k3，不使用真实未来。24000唯一节点期完整保存，所有模型hash前后不变，不改变或合并训练数据。
- 核对全部140回合、五模型critic7维、seed档案、两个场景的需求索引与动作范围0—20。没有LLM实例或API请求，接口结果不作泛化结论。程序错误保留failed，不自动重跑。
- 完成后公开源码/登记/原始逐期/模型加载核验和报告，脱敏检查、归档Git精确字节核对后推送。正式三方法共同测试使用另目录/协议，先固定具体API预算/新种子/统计/恢复策略再启动，不复用本批旧输入称未见。
