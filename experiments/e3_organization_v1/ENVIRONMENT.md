# 环境与运行约束

项目环境为现有.venv，Python 3.12.3，torch 2.11.0+cu128，transformers 5.16.1，vLLM 0.25.1+cu129，numpy 2.3.5，scipy 1.18.1，matplotlib 3.11.2，jsonschema 4.26.0。未升级或新增全局依赖。

同一Qwen/Qwen3.5-4B，路径 /dataset1/zailong/models/Qwen3.5-4B；revision=851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a。身份清单、权重逐文件hash、tokenizer/chat template见父configs/model_identity.json，本轮freeze锁定该文件。BF16、无量化、temperature=0、thinking=false；vLLM Triton attention/native sampler。模型与提示未改变。

Slurm B300q，每作业一GPU、8 CPU、64G、最长1小时，脚本内部srun执行；遵守调度提供的CUDA可见性。已有GPU作业查询为空，未终止其他作业。工作区可用空间约48T；无新增模型下载。

smoke作业1715。正式作业编号与最终资源用量记录在results/resource_accounting.json；原始日志在logs/、runs/。沙箱内Slurm socket不可访问，已通过获准的沙箱外调度命令执行；未改服务器设置。
