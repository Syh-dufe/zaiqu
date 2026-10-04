# 中性格式实时LLM v3：启动记录

2026-10-04启动已批准的小型开发批次。源码4fef02f已推送codex/llm-current-v2，包装PID161324、实际驱动PID91028；启动核查进度为seed11 evaluating，外层错误日志为空。

- 入口experiments/online_llm_neutral/batch.py；输出results/online_llm_neutral/development_v3。
- 冻结模型11/12，4条固定新需求，4方法正常/冲击，共64回合38400节点期，最多384HTTP。
- 三LLM版本使用原事件控制器，分别为原提示、v2格式提示、中性格式提示；不含精英留存或随机比较。
- 中性提示只保留格式/DSL语法约束，首次及修复请求不建议规则写法或提供带数值业务示例。HAPPO与DeepSeek权重均不训练。
- 编译通过、代码静态审阅通过，NeutralClient请求函数AST与v2严格客户端仅附录名不同。不调用API预检通过，源码/输入/模型已登记冻结，四条路径无历史/跨路径碰撞，均有实际需求变化。
- 恢复每半小时跟进，完成原始复核、独立审阅、归档和上传后暂停。预计运行约15分钟，受API速度与修复次数影响；报告核验另计。

本轮为8个开发配对；无论结果如何都保留全部原始记录、失败和不利配对，不自动宣称机制更优或启动正式确认。旧结果不覆盖。

[批准计划](superpowers/plans/2026-10-04-online-llm-neutral-v3.md)；[诊断与方向](2026-10-04-online-llm-neutral-v3-rationale.md)。
