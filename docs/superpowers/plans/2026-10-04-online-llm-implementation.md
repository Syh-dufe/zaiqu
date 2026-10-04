# Online LLM Implementation Plan

> **For agentic workers:** Use subagent-driven-development for implementation and read-only review. User approved the draft on2026-10-04. Do not add or run unit tests; research interface audits and pilot evaluations are authorized.

**Goal:** 接入事件触发的DeepSeek在线修正，冻结正常训练HAPPO，完成小型开发批次。

**Architecture:** 独立online_llm模块复用现有shadow、reports、rules和作者库存环境。每回合单独记忆，仅可见状态与搜索预测反馈进入API，独立复核不进入修订。

**Tech Stack:** Python3.12、PyTorch CPU、现有DSL、DeepSeek chat/completions。

## Tasks

- [x] 用户审阅并批准online-llm-draft；检查现有实时原型、报告与需求校验接口。
- [ ] client.py：结构化请求/回复、候选编译、usage/耗时、超时回退、认证余额权限停止，完整记录失败且不存密钥。
- [ ] controller.py：因果状态打包、最多4事件、每5期新报告触发、候选替换与最近2事件记忆、回合清空；每次3候选和最多一次修订，复核不反馈。
- [ ] run.py：复用模型/环境并输出逐期原始数据、参数哈希、信息和模型审核；独立输入校验支持预登记1.25/1.5两种冲击。
- [ ] batch.py：新4轨迹查重、固定种子11/12、每方法相同配对输入、源码与输入冻结；预检后运行，不重复输出。
- [ ] analyze.py：全结果配对汇总、原始成本复算、API和筛选开销、失败及采用；首批开发结果不能作为独立确认。
- [ ] 审阅规格符合与重要代码缺陷，修复后compile/预检。
- [ ] 启动隐藏的唯一小型批次；先记录进程、日志和协议，定时跟进更新到该批，不再启动旧离线演化。
- [ ] 完成时检查原始产物和冻结参数，报告全2x4结果；按证据准备下一开发版本或独立确认，不预设胜者。

首批4基础组（HAPPO、旧LLM、online_once、online_feedback）加预算匹配random诊断；80配对正常/冲击回合。所有4轨迹均开发，包括种子12，无删除。确认批另登记5x20新轨迹。
