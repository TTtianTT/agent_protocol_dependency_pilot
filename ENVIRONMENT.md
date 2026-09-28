# 环境检查

项目父目录 `/dataset1/zailong/workspace`；2026-09-28。检查 `/AGENTS.md`、`/dataset1/AGENTS.md`、`/dataset1/zailong/AGENTS.md`、工作区 AGENTS.md，均不存在。未读取其他项目的代码、历史报告或数据。

系统Python 3.12.3。项目 `.venv` 以本地Python创建，服务器缺ensurepip，通过项目 `.pth` 只读复用 `/dataset1/zailong/envs/peft-sft-lab/lib/python3.12/site-packages`，项目安装统计依赖，无全局升级。torch 2.11.0+cu128、transformers 5.16.1、vLLM 0.25.1、scikit-learn 1.9.1。完整版本和模型文件SHA256见 configs/model_identity.json。

工作区48T可用。登录节点不可见CUDA，Slurm B300q可用（node01 mix、node02/03 idle），RTXq drain。`srun --partition=B300q --gres=gpu:1` 实测 NVIDIA B300 SXM6 AC，275040 MiB，driver595.71.05。每个实验作业只申请单卡，遵守调度器CUDA_VISIBLE_DEVICES，未终止其他作业。

本地既有Qwen2.5-7B等模型。遵照用户后续建议改用官方 `Qwen/Qwen3.5-4B`，约8.70GiB，低于10GiB新增下载预算。下载后遵照用户要求移至 `/dataset1/zailong/models/Qwen3.5-4B`，revision `851bf6e806efd8d0a36b00ddf55e13ccb7b8cd0a`。原项目模型目录不再存权重。许可/配置以官方模型页 https://huggingface.co/Qwen/Qwen3.5-4B 和下载的配置为准。

基础设施事件：Slurm 1704 初始化时 FlashInfer sampler 需要nvcc，计算节点未发现CUDA toolkit；请求数0、输出0，GPU耗时约200.5秒计入预算。修复为明确设置 VLLM_USE_FLASHINFER_SAMPLER=0（原生采样），保留 logs/protocol-pilot-1704.out。尚无可混接的任务结果。此问题未使用测试结果。

1705进一步发现默认attention也选择了FlashInfer，并在首批32请求执行时需要nvcc。32请求已计入预算，但无成功输出，保留失败节点keys与作业日志。现显式将attention_config.backend=FLASH_ATTN；采样器保持native。研究提示词与生成参数未因这些基础设施故障调整。

1706的vLLM日志仍显示自动选择FlashInfer，字典形式attention_config未在实际后端生效。再改用EngineArgs显式attention_backend=TRITON_ATTN、gdn_prefill_backend=triton，并打印实际引擎后端核验。再次32请求无输出计入账本。累计仍未产生任何模型样本结果。

最终兼容后端已由引擎日志验证为TRITON_ATTN，GDN prefill为triton。smoke-v1（1707）160成功请求；提示调试轮1 smoke-v2（1708）160成功请求，解析100%、答案80%、joint75%。另64请求因基础设施失败无输出，计入9000预算。sacct核对1704–1708实际GPU占用689秒，另设备探测2秒；正式前账本校正为691秒，见runs/accounting_reconciliation.json。

smoke-v2测得160请求生成17515 token，批量推理累计34.28秒（不含加载），以各角色实测耗时估算正式推理约1308秒；此估计并非完成时间保证，未包含全部CPU统计和初始化。正式请求保守上界8004，连同已用384不超过9000；保守生成token上界约540万，不超过1200万。保留200世界，无缩减。
