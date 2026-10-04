# 原实时LLM布尔大小写兼容：启动记录

用户要求只修复大小写，其他机制不变。源码4d266ea已推送codex/llm-current-v2；实际驱动PID167952，包装PID164352。2026-10-04启动核查seed11 evaluating，外层错误日志为空。

原提示、原Client.generate源代码、格式修复提示、HTTP参数、事件控制器、候选0替换、预测与独立复核、模型和场景不改。只在单独加载的兼容客户端中替换compile_rule引用：表达式NAME true/false转True/False，保留其他文本、输入长度/AST约束、原验证顺序，原回复和候选记录不改。旧解析器没有被修改。

沿用上一批四条固定路径，复用为开发输入，不称新独立确认。模型11/12，纯HAPPO/原实时反馈/兼容反馈，正常与冲击共48回合28800节点期，上限256HTTP。预计约10—15分钟运行，另有审核归档时间，API波动可延长。

启动前编译、静态审阅及不调用API预检均通过。历史回复核验3186候选，2902原合法解析AST不变、209因布尔兼容恢复、75其他错误仍失败且保持原错误文字。统计包含重试候选，不等于独立样本、节省调用数或闭环收益；原始审计见[历史回复审计](2026-10-04-boolean-case-archived-reply-audit.json)。

输出results/online_llm_case_only/development_v1；外层development_v1_driver.log/error.log；入口experiments/online_llm_case_only/batch.py。每半小时跟进，完成独立审核、报告、无损归档及上传后暂停。新的API输出有随机差异，实验差异不能全部解释为解析器的单独因果贡献；所有不利配对和失败保留。

[固定实施协议](superpowers/plans/2026-10-04-online-llm-bool-case-only.md)。
