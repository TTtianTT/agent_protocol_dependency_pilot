# e3机制复验

本轮在独立子目录保存全部产物，不覆盖第一轮。Qwen3.5-4B和角色提示保持不变；50新世界、双D需求、每题14条件。规则求解器只认证证据/评分，不替代LLM。

从项目根目录运行：

```bash
# 已生成并冻结，勿重复覆盖
PYTHONPATH=src .venv/bin/python experiments/e3_mechanism_v1/run.py validate
sbatch experiments/e3_mechanism_v1/job.slurm smoke
sbatch experiments/e3_mechanism_v1/job.slurm formal
# 精确缓存续跑也是上面的formal命令
bash experiments/e3_mechanism_v1/restat.sh
```

正式作业必须已有smoke completed.json且解析门槛通过。SPEC.md是事前规格，freeze.json锁定源码/数据/模型/提示/参数。runs为真实上下文、模型输出、来源证明和变换日志；results为5000次world bootstrap统计、图及案例。相同需求版本共享完全相同边payload，只改变D的问题。本轮不训练任何预测器。

“完整直达证据”是保留A/B实际全部输出，不偷偷用gold补事实；缺失情况不删样本，充分子集另报。受控错误候选不按gold挑选；natural条件则实际运行受上游删键影响的C。联合成功采用实际可见的真实证据内容，同时保留第一轮ID评分复验口径。

已完成：正式1400条件、1522次实际请求；含debug共1646请求、76342生成token、409 GPU秒。Slurm作业1713和1714均完成。报告见REPORT.md，审计见results/completion_audit.json。restat.sh依次重建冻结主分析、事前分层展示、明确标注的事后机制解释；不会调用模型。原始逐节点日志保留于本机runs/，按项目既有.gitignore不上传GitHub；仓库中的源码、数据、逐样本统计和报告可供检查。
