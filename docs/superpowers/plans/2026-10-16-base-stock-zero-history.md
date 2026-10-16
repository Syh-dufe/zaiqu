# Base-stock零历史执行计划

**Goal:** 隔离初始历史40个0相对40个10对Base-stock成本的影响。
**Architecture:** 新独立驱动复用原episode(initial_history参数)及标量审核；18回合，原Sundial固定三路径，不改任何冻结源。
**Tech Stack:** 现有Python/NumPy、原库存环境，API0。

1. 新目录experiments/base_stock_zero_history，根results/base_stock_zero_history/v1，固定z2/3/8，不新增选参。
2. 注册源/协议/旧结果/输入SHA，归档推送、Git字节核对后exclusive started.lock首次运行。
3. 运行18回合，保存每回合600行CSV.gz及完整正常/冲击成本；逐期审核零历史、库存/账本/动作和正常/冲击前缀。
4. 列出同z的零历史与旧10历史，Sundial只读参考；不混称独立路径或神经网络训练种子，不按结果替换主基线。
5. 独立进程重读全部原始记录、重算表格/源SHA/归档字节；完整报告、README、归档提交推送。
