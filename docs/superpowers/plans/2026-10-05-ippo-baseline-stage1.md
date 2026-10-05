# IPPO基线阶段1：适配与5000步短程验证

用户授权依原投稿路线继续基线对比。本阶段不调用LLM API、不改变原HAPPO或灾区环境，不启动旧Liu复现。五模型正式训练需短程验证及完整协议通过后另登记。

## 源码核对与设计

固定作者commit a7e5a3e83e21565a5799483bc534e39635ec65dd。serial.py的ALPHA=0.5，训练奖励r_i'=0.5r_i+0.5平均r，评估返回原始r_i；runner.insert直接保存该奖励。不能称原训练奖励为纯系统平均或纯自身成本。IPPO保留完全相同混合奖励、环境、actor局部观测与动作0—20。

两项算法变化：use_centralized_V=False使critic/buffer使用各agent局部观测；每个agent更新前buffer.factor全1，不乘其他agent更新的动作概率比。保留原PPO损失、优化器、网络参数、采样轨迹5、训练环境和原20正常验证轨迹。保留随机agent遍历顺序，但它不影响其他agent的重要性权重。未加入参数共享。

这是本项目从作者HAPPO/PPO组件适配的IPPO基线，不是作者现成官方IPPO，也不称论文IPPO精确复现。内部config.algorithm_name仍为happo以复用作者唯一已实现的Policy/Trainer加载分支；manifest与结果明确标actual_algorithm=ippo，不能把内部标签误认算法。模型目录沿用兼容启动器，但使用唯一ippo run-name隔离。

新增独立experiments/ippo_baseline/update.py与run.py，不编辑作者或旧实验文件。run.py复制已验证learning_curve观察框架，只改局部critic参数、更新调用、结果目录与局部critic检查点重载维度。所有额外审核读参数/数组，不额外调用RNG。

## 无API预检与短程

固定seed11、5000环境步（5轨迹×200期=每次1000步），patience40，不启用额外平台提前终止。输出results/ippo_learning_curve/ippo_seed11_smoke5k_v1；拒绝覆盖。记录每次更新的三个actor对应factor最小/最大必须均1，share_obs最后维度必须等于本地obs维度且少于集中维度，训练奖励处理函数/ALPHA哈希。checkpoint重载误差必须0。

预检先核对config中--use_centralized_V是store_false且不附True/False字符串。短程结果只验证实现/步数/加载，不能报告收敛或基线排名。训练初始/最终、所有学习曲线、快照、因子审核保留。程序错误先诊断保留原始结果，不覆盖重跑。

## 进入下一阶段

5000步、五次采样更新（共15agent更新）、局部critic维度、因子恒1、奖励不改、模型加载和作者tracked源码干净均通过，才登记seed11—15正常需求正式训练。每种子300万步上限、patience40、同固定经验稳定标准、原正常验证选择模型，最大并发2。不能用灾情结果筛训练种子/调超参数；旧HAPPO五模型不重新训练，所有不稳定与不利结果保留。正式新比较另冻结/生成未见冲击路径，并明确双方可见信息及额外LLM观测差异。阶段2协议和审计未写完前不启动正式训练。
