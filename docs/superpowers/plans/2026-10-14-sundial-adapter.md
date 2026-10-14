# Sundial output adapter Implementation Plan

**Goal:** 固定独立训练开发与新验证，检验24参数门控位置/尺度校正是否改善概率预测。

**Architecture:** 冻结Sundial先生成离线样本，只训练轻量适配器；冻结最佳参数后生成新测试，四方法完整比较。

- [ ] common.py固定IO/模型/历史索引与因果窗口生成；prepare.py冻结源后按种子顺序生成24训练+8开发路径。
- [ ] forecast.py对train/dev各窗口以冻结Sundial生成32报告轨迹，保存完整原始样本、两stream与参数hash。
- [ ] adapter.py实现24参数门控位置尺度变换；fit.py固定Adam/lr/200epoch/patience25，开发CRPS选模型，保存epoch0、全曲线、best/final、SHA与重载一致。
- [ ] prepare-test在best参数冻结后生成20查重验证路径；forecast.py首次预测、evaluate.py比较四方法并按路径分层配对bootstrap。
- [ ] verify.py独立重算样本变换、指标、模型SHA与成熟报告因果，核对新输入不碰撞和所有负例。
- [ ] 无损归档、Git精确字节与密钥缺席核验，README/报告提交push。失败停诊断不盲重跑，不新增API。
