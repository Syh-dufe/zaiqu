# Sundial固定路径Base-stock追加比较

用户授权：在当前Sundial固定路径上先进行Base-stock对照。继续执行既有2026-10-05非平稳Base-stock及追加比较设计，不改变策略、调参或重跑旧方法。

## 固定合同

- 现有experiments/base_stock_baseline/policy.py、batch.py的episode原样复用，z=2来自先前独立开发选择，历史40、L=4、initial[10]*40、NumPy总体方差、ceil、动作0..20。
- 每节点仅用已完成的本地需求，含因果未发订单账本；供应商欠货仅供审核，不作直接决策输入。不是作者官方Base-stock代码。
- 输入results/submission_required/v1/inputs/confirmation01_main.json，前三类single/sustained/double、原trace0/1/2；不使用移动双峰路径或成本适配器的新路径。
- 新增Base-stock3类×正常/冲击=6回合、3600节点期，API0、训练0。确定性策略不重复五个训练种子，不增加虚假需求样本。
- 五模型纯HAPPO和guard_pool Merton从results/online_llm_guard_pool/development_v1/runs/development_batch01_seedN复用；Sundial11/12从sundial_six_rules/development_v1，13..15从sundial_six_rules_extension/v1复用。
- 每个历史任务输入前三条、原始periods成本、episodes和completed参数不变声明重新审核，原文件SHA全部绑定。不把Sundial6规则/Merton4规则视作纯预测器因果对照。
- 三场景是事后范围，单类一条物理路径；本次是已暴露输入的追加描述，不是新的未见确认。不选择当前路径上的z、不声称显著或等信息等算力。

## 执行步骤

1. 新目录experiments/sundial_fixed_base_stock，输出results/sundial_fixed_base_stock/v1；冻结源、旧输入/结果、环境和参数。
2. 无损gzip注册包、密钥缺席及Git存储字节核验，提交推送后再启动唯一驱动。
3. 网络socket连接禁止；复用原episode，正常/冲击都运行，原始逐期记录永久保留。
4. 使用既有独立标量verify_episode重建库存、在途、未发账本、目标与动作，按先前已公开规则枚举浮点整数边界；不能改旧审核吞错。
5. 核对自身冲击前正常前缀、全部成本与输入SHA；汇总按场景以及五模型配对。基线在每模型表中广播只为配对，明示仅运行6次。
6. 完整新增记录、源码、协议、历史绑定和报告无损归档，核对Git字节及凭据缺席；README、报告提交推送。失败停止保留、不盲重启覆盖。

本任务不会修改或中断正在运行的3参数成本适配训练。
