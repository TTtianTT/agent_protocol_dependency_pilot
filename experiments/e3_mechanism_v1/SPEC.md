# e3干扰与证据需求机制复验：事前规格

本轮保持Qwen3.5-4B、本地权重revision、四角色提示词、temperature=0、BF16、vLLM Triton backend与JSON schema解码不变，不修改第一轮数据/源码/预算账本。50全新正式世界，另4个debug世界；每世界2个D需求、14个条件。新seed=20261001，生成器固定，每世界独立seed。25世界唯一姓名，25世界同名实体；两者均需project→entity key→code关联，每侧5记录含重复独立source ID，承认多个合法证据集合。新实体key/名称/项目/code与第一轮不重叠，source IDs随机不编码答案。

## 接收者需求的隔离

A/B/C只在每世界一个共同基础问题上执行，A/B各一次、C一次，保存实际输出。D看到相同基础问题加“citations optional”或“verifiable evidence required”，两需求的答案相同、所有边消息字节相同。相较第一轮，这是有意冻结上游来隔离接收者需求，不能与端到端各角色都响应需求的实验混为同一估计量。e4/e5保持实际A/B全量输出；不以oracle补事实。若A/B漏抽/错抽导致直达证据不充分，全体样本仍保留，另报oracle认证充分的预声明子集。

## e3分量干预

原始O是实际C输出及其来源解引用。脚本扰动S只能使用C实际可见的e1/e2 facts与O，不读取gold或D输出。按发送方顺序选第一个kind=code、value未出现在O.answer的候选；若不存在则noop。S.answer是这个候选code；S.evidence是C输入里该候选key的已有事实，全部保留原文，source ID不伪造；support_links只重建对这些已有事实的引用。此操作可能使真事实成为与当前问题不相关的依据，不新增假事实。不保证S.answer必错，实际正确性只在事后评分，全部样本保留。

交叉使用O/S结论和O/S证据得到original、swap_answer、swap_evidence、swap_both；再分别删除O/S的结论或证据，外加完全屏蔽e3。删除结论是absent，绝不替换成insufficient；删除证据同时删evidence与support_links；屏蔽e3时D输入不出现e3键。

自然上游干预N：确定性删除e1每个实体key（其他重复位置无key隐藏），e2与e4/e5不变，真实重算C；得到natural、natural_without_answer、natural_without_evidence。此路径不属于“仅改e3的纯分量干预”，用于核验真实受损上游输出是否干扰D。所有条件仅复用不受影响节点。

## 证据双路径四格

00=original，10=original_without_evidence（仅去e3证据，保留proposal），01=drop_e5，11=drop_e3_evidence_and_e5。e4不变，两个需求版本共用同一C和同一四格payload。J=L11−L10−L01+L00，以joint_success及answer_accuracy分别计算，再按同世界计算J_required−J_optional。另对完全相同输出交叉评分，区分答案变化、拒答变化与仅证据评分差异。

## 指标、充分性与归因

主分母全部50世界/100查询；按world聚类bootstrap 5000次，两个需求和所有条件始终绑定。主成功需答案正确，且在required需求下至少一个合法证据集合完整、引用的实际可见来源内容真实支持答案。分别报告原第一轮ID集合评分与更严格的内容/可见性评分，若不同明确说明，不悄然改变复验口径。原始事实真实性以完整六字段逐条匹配验证；可逆/缺失字段不自动当作虚假断言，仅不能充当完整来源证明。source_evidence_sufficient仅在可见真实事实包含一个完整充分集合时为真，并保存witness。

正确proposal_present另报，不把正确候选等同可验证证据；无充分性证明不宣称不可恢复。关键归因：direct e4/e5充分且no_e3成功，但某e3条件失败，构成接收者受该消息干扰的配对案例；充分且no_e3也失败，说明D自身使用困难，不能独归因e3。直达证据不充分单列抽取路径限制。对自然e3以及纯结论/证据干预分别计数，避免笼统归因。

四个主要比较（全体样本；bootstrap双侧近似p并Holm校正）：1 original相对no_e3的joint loss差；2 swap_answer相对original；3 swap_evidence相对original；4 J_required−J_optional。其余恢复/子集/分层/答案交互探索性。即使区间跨零也不声称安全/非劣。本轮不拟合预测器、不换模型、不根据结果挑世界或操作。案例按类别world_id/demand/condition字典序首项，约10例；类别不存在则明示。

## 执行和预算

全部plan冻结后运行4世界独立smoke（全部条件）及正式50世界。最多1728个请求（正式1600，smoke128；缓存可减少）、300万生成token、2 GPU小时；仍不超过原全项目9000请求余量。单张B300经sbatch/srun。逐条fsync与完整依赖hash缓存；本轮独立账本，旧记录只读。运行、分析、冻结与checkpoint均位于本目录，真实模型输出不能由规则求解替代。
