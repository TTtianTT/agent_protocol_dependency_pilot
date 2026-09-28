# 本轮运行状态

规格与实现冻结hash：7ff5685f5d43838b10f483c0ee4b655068020f50538c1b12e4e216e7f0fd5e62。

- CPU生成/求解/协议不变量检查：通过。
- 独立smoke：Slurm 1715 COMPLETED，4世界、8查询、40条件；44真实请求、3046生成token、108单GPU秒。解析100%，无截断。P0答案75%，证据必需joint25%；未修改提示或条件。
- 正式：Slurm 1716，100世界、200查询、1000条件，运行中；作业提交不等于完成。
- 正式完成后运行冻结的统计与审计，状态以STATUS.json和results/formal_audit.json为准。

监控：`squeue -j 1716`；日志：`logs/e3-organization-1716.out`。
中断续跑（项目根目录）：`sbatch experiments/e3_organization_v1/job.slurm formal`。
