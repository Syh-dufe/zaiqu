# Sundial零样本轨迹预测开发试用

用户授权试用Sundial。官方ICML2025模型thuml/sundial-base-128m，HF revision3212e42564493f520593e5414af4367fc4b49226，Apache2.0。CPU float32冻结推理，无训练、无DeepSeek API、无库存闭环。与旧TimesFM失败开发隔离，不修改旧冻结对象。

复用TimesFM开发固定48窗口、8已暴露需求路径：batch01/06×四类型×通知后0/5/10/15/25/40。输入仅当时已送达完整三期报告均值，age0/1/2；不输入未送达真实需求、未来、事件类型或结束时间。每窗口预测ceil((age+20)/3)个报告块，原Sundial默认生成设置固定，不试多设置择优。

每窗口用两个独立固定torch随机流，各16样本，共32条完整报告块均值轨迹，保存未截断原输出与0..20截断结果。不把逐点分位独立拼接为轨迹。仅为辅助逐期点预测评分，每块均值重复3次后舍弃age前缀；它不能恢复块内真实顺序，不直接作为订货仿真中的整数需求。

原Merton、最新值中心路径、TimesFM中心路径复用已固定阶段A的每窗口32条轨迹；对其每条逐期路径取对齐的完整三期均值，与Sundial在同一报告块层面计算有限样本CRPS和样本均值MAE。另展示20期点预测MAE、总需求CRPS、边界/截断、推理时间、全48窗口及不利例。窗口重叠，8路径不能当48独立样本，32预测样本不是32条真实需求。

只有Sundial总体完整报告块CRPS和样本均值MAE均严格低于原Merton、最新值及TimesFM三个参照，且四类型无任何类型这两指标同时高于原Merton，才支持设计另行登记的闭环适配开发。未通过完整报告，不针对同窗口调采样、输入或噪声至胜出。预测通过也不证明库存成本改善；需要独立设计块内需求构造，不能直接扩展付费批。

新目录experiments/sundial_forecast_pilot；结果results/sundial_forecast_pilot/development_v1，永久启动锁；失败保留新版本处理。独立缓存C:/Users/13384/.cache/zaiqu-sundial-pilot/model/<revision>与deps，不修改原训练venv/TimesFM依赖。先下载并检查固定自定义模型Python代码，再冻结源码、协议、全部模型/依赖/输入hash，首次推理。保存所有原始轨迹、独立指标复算、密钥缺席检查；大权重仅本地，公开revision与SHA及许可证。
