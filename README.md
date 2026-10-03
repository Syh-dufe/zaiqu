# 灾害冲击下多级物资补给研究

本项目先建立 Liu 官方库存模型的业务解释兼容版本，再逐项研究洪灾需求变化与 LLM 生成补货规则。目前已编写兼容启动器，尚未运行兼容验证或新的训练。

## 当前版本

直接调用官方原始 `train_env.py`，只指定独立的场景和实验名称。库存状态转移、需求、奖励、网络、HAPPO 顺序更新、默认训练预算及早停均使用官方实现。

| 官方节点与变量 | 业务解释 |
|---|---|
| 下游节点 | 社区物资供应点 |
| 中间节点 | 区域物资仓库 |
| 上游节点 | 物资供应中心 |
| 订货量 | 向上游申请补充的标准批次 |
| 库存 | 尚未发放的储备物资 |
| 欠货 | 允许后续补供的未满足需求 |

数量和时间采用归一化批次与仿真期。当前没有加入洪灾冲击、车辆、道路、LLM 或真实数据，不声称具有真实灾区验证结果。

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

或使用独立名称做小预算流程检查：

```powershell
& .venv/Scripts/python.exe -u experiments/emergency_compatibility/train.py --run-name smoke_seed11 --seed 11 --num_env_steps 5000
```

结果由官方脚本写到 `external/results/MyEnv/Emergency_Replenishment_Compatibility/happo/<run-name>/`，包含来源记录、模型和原始训练输出。已有同名目录拒绝重跑。模型、原始数据、日志、API 密钥和上游源码均不上传。

## 下一步

1. 固定业务解释、单位与假设。
2. 用户要求验证时，用相同参数检查官方入口和兼容入口的一致性。
3. 逐步增加训练预算，检查学习稳定性。
4. 单独加入洪灾需求变化。
5. 研究 LLM 生成、筛选与冻结补货调整规则。

当前暂不开展基线排名；历史实验和停止的复现记录保留在原本地工作区。
