# agent_protocol_dependency_pilot

单模型、四固定角色、五类程序生成跨文档任务。模型在 `/dataset1/zailong/models/Qwen3.5-4B`，项目仅保存配置、模型hash与运行产物。真实推理通过Slurm单张B300；不调用外部付费API。

在项目目录执行（CPU命令无需GPU）：

```bash
cd /dataset1/zailong/workspace/agent_protocol_dependency_pilot
PYTHONPATH=src .venv/bin/python -m protocol_pilot.generate
PYTHONPATH=src .venv/bin/python tests/validate.py
PYTHONPATH=src .venv/bin/python tests/test_replay.py
bash scripts/run_smoke.sh
# smoke通过、规格审核后，仅首次冻结：
PYTHONPATH=src .venv/bin/python scripts/freeze.py
bash scripts/run_pilot.sh
# 中断后，保持已冻结代码/配置/数据：
bash scripts/resume_pilot.sh
# 仅重做统计，不调用模型：
PYTHONPATH=src MPLCONFIGDIR=.cache/matplotlib .venv/bin/python -m protocol_pilot.reporting
```

正式冻结后不要重生成或覆盖数据；同样种子生成是确定性的，但应保留冻结哈希验证。脚本必须在本服务器B300q可用、Slurm授权下执行。`scripts/job.slurm`先申请1 GPU，再用srun执行。run_smoke/pilot/resume仅封装相应sbatch命令；成功提交不是实验完成。

运行状态见RUN_STATUS.md、runs/pilot-v1/stages.jsonl与Slurm日志。异常见failures.jsonl；budget_ledger.json记录全项目累计实际请求、生成token和GPU时长（含失败初始化）。每批检查9000请求/1200万生成token/8小时限制，超限前写PAUSED.json。缓存key包含完整可见输入、角色提示、模型、配置、执行代码hash。每条成功推理逐条落盘；续跑可复用同版本未受影响节点。若修改代码必须另开版本并重跑受影响范围，不能混接。

A/B的JSON只包含本侧facts，`id,key,name,kind,value,qualifier`均明确；同一信息不会暗藏在未处理的自由摘录。e1/e2承载facts，e4/e5承载evidence，e3承载C结论及C实际引用的输入事实（确定性解引用，C从未读取其他数据）。多个facts表达alternatives；key和qualifier为事实内信息单元。空list=明确无条目，null=未知，absent=未供给。删除后仍维持可解析消息。format_only仅改变顺序/缩进。通信token按每条边实际独立JSON序列化计数，节点input_tokens另含消息包装及公共规则，二者不要混同。

严格顺序：冻结→全体full→train/validation干预→训练/验证M0–M3→只读test预测快照→test干预→2000次world bootstrap及报告。feature函数不接收gold或修改后输出；模型及validation选择记录存predictors.joblib和prediction_freeze.json。人工可控任务的oracle只用于标签/验证，不代替任何LLM节点。

图的底层CSV和全样本表在results；案例通过query_id/condition链接outcomes中的node keys，再找到traces的完整可见输入与原始输出。信息不可恢复只能由完整边界反事实碰撞证书证明；solver未证充分不能当不可恢复。

报告生成后补充详细资源、案例及验收审计（不调用模型、不重新拟合）：

```bash
PYTHONPATH=src .venv/bin/python scripts/supplement_report.py
PYTHONPATH=src .venv/bin/python scripts/audit_completed.py
```

`results/presentation_scripts_preregistered.json`记录这两个描述性脚本在测试干预前的hash。`results/frozen_source.tar.gz`保存正式启动前源码/配置/提示/规格快照。

最终交付的统计重跑一行命令（已实际验证，CPU执行，不产生LLM请求）：

```bash
bash scripts/restat.sh
```

该命令重算全部统计/图表与描述性案例，重新验收，并恢复基于同一outcomes哈希的最终中文解读。若outcomes改变，旧解读不会被静默复用。最终GPU资源以results/final_accounting.json的Slurm账单为准。
