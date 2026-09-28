# 本轮运行状态

规格与实现冻结hash：7ff5685f5d43838b10f483c0ee4b655068020f50538c1b12e4e216e7f0fd5e62。

- CPU生成/求解/协议不变量检查：通过。
- 独立smoke：Slurm 1715 COMPLETED，4世界、8查询、40条件；44真实请求、3046生成token、108单GPU秒。解析100%，无截断。P0答案75%，证据必需joint25%；未修改提示或条件。
- 正式：Slurm 1716 COMPLETED，100世界、200查询、1000/1000条件，1118实际请求（A/B/C各100，D 818）；182个相同输入的D条件精确缓存复用。
- 主统计与审计已完成：P3−P2 required joint=-0.02，95%世界配对区间[-0.09,0.05]，精确双侧p=0.7905。无分组改善证据，不宣称等效。
- 含smoke累计1162实际请求、77122生成token、490单GPU秒；所有预算内，无解析失败、截断或基础设施故障。模型、原提示与冻结实验源码均未修改。
- 最终结果见REPORT.md；决策解读见DECISION.md。事后e3事实库存描述单独标注，不增加推理或检验条件。

监控：`squeue -j 1716`；日志：`logs/e3-organization-1716.out`。
中断续跑（项目根目录）：`sbatch experiments/e3_organization_v1/job.slurm formal`。
