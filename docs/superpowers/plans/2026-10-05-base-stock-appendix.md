# Base-stock事后追加比较

用户已将方案改为复用已完成的共同确认，不生成新需求输入、不重新运行HAPPO/IPPO/LLM、不调用API。原results/joint_baseline_confirmation/confirmation_v1及历史开发文件保持只读。当前追加是在已暴露共同确认数据上计算传统基线，属于posthoc additional baseline comparison，不是新一轮前瞻独立确认。

旧完成摘要与completed哈希是最终50任务标签的权威来源，包括seed15_batch02_quota_recovery_recharge1，不能根据目录名猜测最终成功尝试。全部10批原输入及50任务逐期文件、调用、评分、协议、模型合同与原始完成元数据锁定SHA。将旧任务直属文件复制到新结果目录仅供统计接口只读复核，原目录不改动。失败尝试的已发生调用也保留为历史成本。

追加策略完全沿用原Base-stock episode和NumPy运算：本地40期已完成需求历史，初始[10]*40，L=4，原math.ceil与[0,20]限幅，保留未发货账本并与供应节点欠货独立核对。开发选择z=2与参考z=8各在原10批四类正常/冲击路径计算80回合、48000节点期，共新增160回合、96000节点期。原1200回合720000节点期只复用，总比较1360回合816000节点期。不给确定性Base-stock复制训练种子。

每个600行Base-stock回合使用已锁定数值诊断verify_episode独立重建状态、成本、目标、动作及供应账本，枚举NumPy与独立标量离散边界，保持原数值规则；核对同路径正常/冲击前缀。原50任务再次完整audit_child以及统计输入逐期复算。任何hash、账本、逐期、程序错误立即停止，保留所有产物且不盲重启。

原分析接口执行20000次模型/路径交叉bootstrap，seed20271651。追加比较online_feedback−z2、−z8及旧HAPPO/IPPO比较全部为探索性描述；即使沿用97.5%区间，也不宣称该Base-stock比较已事前登记或形成新的前瞻性显著证据。均值、区间、各类/种子和所有改善/持平/退化保留。

输出results/base_stock_appendix/posthoc_v1。登记先冻结新源码/本协议/旧来源/原输入/模型合同与运行时，再永久exclusive started.lock和launch标记。socket层封禁联网。本次api_requests/new_api_requests均0，旧API请求、token及计算资源单列historical字段，不计为本次新增开销。本轮不启动尚未登记的base_stock_confirmation，不提交Git。
