# Sundial pilot Implementation Plan

**Goal:** 检验冻结Sundial生成的报告块未来轨迹是否更适合规则评价的预测分布。

**Architecture:** 原48因果窗口与固定三参照重用；官方Sundial两个独立16样本流，完整报告块公平评分，无API与库存仿真。

**Tech Stack:** Python3.12/Torch CPU float32，独立transformers4.40.1依赖及固定HF权重。

- [ ] 下载官方revision3212e42564493f520593e5414af4367fc4b49226配置、Python代码和safetensors，保留README许可证与SHA；审查自定义代码不发送网络或读取实验未来。
- [ ] 独立deps安装transformers4.40.1及所需包，不更新既有venv。固定官方生成默认值及CPU2线程。
- [ ] run.py在冻结完整协议、源码、模型、依赖和48输入后首次generate，保存32条原始报告块轨迹、截断与辅助逐期对齐输出；不同流seed由SHA256身份生成，原种子不择选。
- [ ] analyze.py逐窗口对齐完整报告块，对三原参照和Sundial重算CRPS/MAE与所有负例。真实未来只在评分过程读取。
- [ ] 独立标量排序CRPS与样本均值误差复算，检查48身份/192方法窗口及source/model/input SHA，生成报告。
- [ ] 公开无损产物与Git精确字节核验；若门槛通过，另登记块内需求适配开发；不直接启动API。
