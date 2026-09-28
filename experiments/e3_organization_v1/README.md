# e3消息组织实验

保持Qwen3.5-4B、全部角色提示与workflow不变。100全新世界/200查询/1000条件；P3对P2是唯一主要比较。预注册见SPEC.md，冻结版本见freeze.json；旧实验不覆盖。

**已完成，未得到分组改善联合成功的证据。** 证据必需时P2=28%、P3=26%，差-2个百分点，95%区间[-9,+5]。报告见[REPORT.md](REPORT.md)，按预设目标的继续/暂停决策见[DECISION.md](DECISION.md)。正式1118请求，含smoke1162请求、490 GPU秒。

从项目根目录执行：

```bash
# 只在尚未冻结时生成，已冻结则安全拒绝覆盖
PYTHONPATH=src .venv/bin/python experiments/e3_organization_v1/run.py prepare
PYTHONPATH=src .venv/bin/python experiments/e3_organization_v1/run.py validate
sbatch experiments/e3_organization_v1/job.slurm smoke
PYTHONPATH=src .venv/bin/python experiments/e3_organization_v1/run.py analyze smoke
# smoke检查通过且BUDGET_ESTIMATE.md已记录后
sbatch experiments/e3_organization_v1/job.slurm formal
# 中断续跑：同一formal命令，按完整可见输入精确缓存，不覆盖结果
PYTHONPATH=src MPLCONFIGDIR=.cache/matplotlib .venv/bin/python experiments/e3_organization_v1/run.py analyze formal
# 可选：事后描述性e3事实库存，不是额外协议实验
.venv/bin/python experiments/e3_organization_v1/describe_evidence.py
```

Slurm脚本内部使用srun，单GPU B300q。运行日志逐条落盘在runs/{smoke,formal}/；原始日志按已有.gitignore留服务器，源码/数据/逐样本统计/报告提交仓库。模型路径、revision及文件hash沿用configs/model_identity.json；本轮freeze锁定该文件及全部提示。

分组保留每条原事实的key/id/name/kind/value/qualifier，展开P3逐条等于P2。没有修改D提示教它读分组；记录多出的结构token。P1/P2/P3仍保留相同原support_links。所有noops、C错答、引用错误纳入主分母。引用错误类型可以重叠。
