# 后五种子比较执行计划

**Goal:** 补纯HAPPO/Merton/Sundial种子16..20同固定三路径，并保留全部旧对照。
**Architecture:** 新runner/audit/batch目录；模式分进程保持Merton4规则、Sundial6规则；冻结原evaluate的3trace副本及本批模型合同；不修改旧对象。
**Tech Stack:** 原CPU Python、Torch、Sundial本地权重、DeepSeek Windows User API。

1. runner加载原live/six引擎，显式训练路径extension_v1，3trace合同；IPPO合同排除但HAPPO与部署全审核保留。
2. audit复用冻结标量成本/因果/规则/forecast审计，3trace计数适配；Sundial读本批同seed Merton原始记录作前缀对照。
3. 无API模型16完整18回合接线，各五模型合同检查；假DSL不作成绩。
4. 注册模型/输入/全部源/协议/fixture SHA，按480HTTP/240语义首轮、960/480含恢复登记归档并先push。
5. 隐藏后台唯一batch run，10串行任务，永久锁、状态/attempts/日志及部分文件不覆盖。402按一次恢复规则，其他异常停止。
6. 完成90回合后逐期审核、后五/全十成本表、旧Base-stock重用标注、全部调用与失败费用；无损归档/独立核验/报告README推送。

预检恢复：v1夹具在首个方法运行前，被旧evaluate内部重复合同检查缺少API key拦停，API0、完成回合0。保存v1原源字节/日志/失败，v2仅把离线require_key=False透传到内部重复检查，付费模式仍强制key；独立v2根重新核验。旧注册方法源不变。正式注册包采用v2并包含v1完整失败记录。
