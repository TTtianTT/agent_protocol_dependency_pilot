# 本轮执行环境

复用项目 .venv、Qwen/Qwen3.5-4B本地权重及全部原角色提示。权重位于 /dataset1/zailong/models/Qwen3.5-4B，revision和逐文件SHA256见项目 configs/model_identity.json，未新增下载。模型身份hash写入本轮freeze.json与节点记录。

Slurm B300q，每次仅1张B300、8 CPU、64G，srun执行。BF16、temperature0、thinking=false、vLLM Triton attention/native sampler；沿用已验证的后端，未更改服务器全局依赖。smoke作业1713，formal作业1714。各角色输出上限与第一轮一致，无静默截断。

本轮读写均在experiments/e3_mechanism_v1；只读复用父项目代码/模型/提示，预算账本单独保存。git diff已验证旧src/configs/prompts/data/REPORT均未改变。源代码和数据冻结归档 results/frozen_protocol.tar.gz。除GPU占用的原始Slurm核对外，最终统计在CPU上执行。
