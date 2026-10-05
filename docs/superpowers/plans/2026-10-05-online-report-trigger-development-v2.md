# 报告触发开发：v2预检修复登记

沿用[设计](../specs/2026-10-05-online-report-trigger-design.md)及[实施计划](2026-10-05-online-report-trigger-development.md)的全部调度、输入、方法、预算与开发门槛。v1只完成freeze/manifest登记，在无API预检的入口核验阶段失败：将manifest里的字符串path直接传给需要Path.read_bytes的digest函数。没有API调用、仿真或性能结果，错误登记保留在 `results/online_llm_report_trigger/development_v1/preflight_failed.json`，原v1三份源文件不改。

新独立目录 `experiments/online_llm_report_trigger_v2`，新输出 `results/online_llm_report_trigger/development_v2`。唯一行为无关修复为 `digest(Path(entry['path']))`；另调整版本入口与冻结本附录。v1与v2的controller源文件必须SHA一致，SYSTEM、Client及evaluate行为一致。固定复用原确认batch01/06作为开发，五模型和240回合/144000节点期均不变。首轮1280HTTP/640语义，含一次402任务恢复累计2560/1280。v1用量为0。

启动前重新完成10任务无API预检并保存证据，核对所有三方法数量及调度边界/回合重置，保存v1失败登记/源文件SHA。提交推送后最多首次启动一条驱动。v1不重启。报告和归档须披露此预检失败，不将v2重放既有输入称为新未见确认。其他异常继续先诊断保留产物，不盲目重启。
