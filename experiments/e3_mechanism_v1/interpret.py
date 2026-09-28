"""Post-hoc descriptive interpretation; preserves all prespecified tests/conditions."""
import csv,collections
from protocol_pilot.common import rows,read,write,digest
from analyze import HERE,savecsv,bootstrap,table

def main():
 out=rows(HERE/'runs/formal/outcomes.jsonl');idx={(o['world_id'],o['demand'],o['condition']):o for o in out};worlds=sorted({o['world_id'] for o in out});summary=[]
 for c in ['original','original_without_answer','original_without_evidence','no_e3','natural','natural_without_answer','natural_without_evidence']:
  os=[o for o in out if o['condition']==c];required=[o for o in os if o['demand']==1]
  summary.append(dict(condition=c,n=len(os),answer_accuracy=sum(o['metrics']['answer_accuracy'] for o in os)/len(os),joint_success=sum(o['metrics']['joint_success_strict'] for o in os)/len(os),required_answer_correct=sum(o['metrics']['answer_accuracy'] for o in required),required_joint_correct=sum(o['metrics']['joint_success_strict'] for o in required),required_correct_answer_but_incomplete_citations=sum(o['metrics']['answer_accuracy'] and not o['metrics']['joint_success_strict'] for o in required)))
 savecsv('interpretation_components.csv',summary)
 effects=[]
 for changed,base in [('original_without_answer','original'),('original_without_evidence','original'),('no_e3','original'),('natural_without_answer','natural'),('natural_without_evidence','natural')]:
  rr=[dict(world_id=w,gain=idx[w,d,changed]['metrics']['answer_accuracy']-idx[w,d,base]['metrics']['answer_accuracy']) for w in worlds for d in [0,1]];effects.append(dict(changed=changed,base=base,endpoint='answer_accuracy_gain',scope='exploratory paired descriptive endpoint',**bootstrap(rr,'gain')))
 savecsv('answer_ablation_effects.csv',effects)
 decomposition=[];four=['original','original_without_evidence','drop_e5','drop_e3_evidence_and_e5'];adequate_worlds=[]
 for w in worlds:
  def J(d,key):
   losses=[1-idx[w,d,c]['metrics'][key] for c in four];return losses[3]-losses[1]-losses[2]+losses[0]
  joint=J(1,'joint_success_strict')-J(0,'joint_success_strict');answer=J(1,'answer_accuracy')-J(0,'answer_accuracy')
  decomposition.append(dict(world_id=w,joint_demand_interaction=joint,answer_demand_interaction=answer,citation_component=joint-answer))
  if all(idx[w,0,c]['metrics']['source_evidence_sufficient'] for c in four[:3]):adequate_worlds.append(w)
 savecsv('interaction_metric_decomposition.csv',decomposition)
 decomp=[dict(component=k,**bootstrap(decomposition,k)) for k in ['joint_demand_interaction','answer_demand_interaction','citation_component']];savecsv('interaction_metric_decomposition_summary.csv',decomp)
 clean=[r for r in decomposition if r['world_id'] in adequate_worlds];clean_summary=dict(subset='both single-deletion paths retain authentic proof; post-hoc exploratory',**bootstrap(clean,'joint_demand_interaction'));savecsv('redundancy_eligible_subset.csv',[clean_summary])
 required_missing=[o for o in out if o['demand']==1 and o['condition']=='drop_e3_evidence_and_e5'];assert all(not o['metrics']['source_evidence_sufficient'] for o in required_missing)
 first=effects[0];accounting=read(HERE/'results/resource_accounting.json');lookup={r['condition']:r for r in summary}
 t=f'''\n## 机制解读：哪些可以解释，哪些仍不能（事后描述性补充）

**证据不足不是完整直达路径下的解释。** 所有50世界的e4/e5都有真实充分来源集合；该组失败属于接收者没有正确利用信息，或被e3改变了行为。屏蔽e3后仍有 {100-sum(idx[w,d,'no_e3']['metrics']['answer_accuracy'] for w in worlds for d in [0,1])}/100 查询答案错误，因此“e3干扰”也不能解释全部错误。

**显式结论更像答案错误的一项来源，但不能说是唯一来源。** 保留e3证据、仅删除显式结论，答案正确率由 {lookup['original']['answer_accuracy']:.0%} 升到 {lookup['original_without_answer']['answer_accuracy']:.0%}，配对增益 {first['estimate']:.3f}，95%world区间 [{first['ci_low']:.3f},{first['ci_high']:.3f}]。仅删除e3证据时答案正确率 {lookup['original_without_evidence']['answer_accuracy']:.0%}；完全屏蔽e3为 {lookup['no_e3']['answer_accuracy']:.0%}。这是探索性端点分析，不替代四项主检验；原始e3相对no_e3的平均joint损害经过Holm校正未显著（p=0.112）。受控swap的原结论本来就有一半错误，swap也并非总是变坏，应看成对损害/改善数，不能把其均值小解释成D对错误结论免疫。

**答案正确与引用完整是两种不同失败。** 证据必需的50查询里，原始e3有 {lookup['original']['required_answer_correct']} 个正确答案、仅 {lookup['original']['required_joint_correct']} 个joint成功；删除结论后正确答案增加到 {lookup['original_without_answer']['required_answer_correct']}，但joint仅 {lookup['original_without_answer']['required_joint_correct']}。完全屏蔽e3时分别为 {lookup['no_e3']['required_answer_correct']} 和 {lookup['no_e3']['required_joint_correct']}。所以保留C证据、去掉结论对答案有帮助，却没有同步解决来源核验；也不能据此制定“永远删结论、永远留证据”的规则。

{table(summary,['condition','n','answer_accuracy','joint_success','required_answer_correct','required_joint_correct','required_correct_answer_but_incomplete_citations'])}

**需求交互复现主要落在证据达标这个端点。** 按loss恒等式，ΔJ_joint=ΔJ_answer+引用未达标项，本轮均值为0.32=0.02+0.30。它是指标分解，不是因果中介分解；答案交互的需求差异区间跨零。证据双路径都去掉后，必需需求下50/50没有来源证明，joint为0，但模型仍有14/50答案碰巧或借proposal正确；50/50均未输出insufficient。这表明固定D还存在“缺证据却不拒答/不给出完整支持”的协议执行问题，不能仅以信息是否可恢复概括。

{table(decomp,['component','n','worlds','estimate','ci_low','ci_high'])}

两条单独删边之后都仍有真实证据证明的世界只有 {len(adequate_worlds)}/50（原始C未必转述完整证据）；因此全部四格混合了真正双备份与原本只靠直达路径的世界。事后对这个纯结构充分性子集的复验：ΔJ={clean_summary['estimate']:.3f}，区间[{clean_summary['ci_low']:.3f},{clean_summary['ci_high']:.3f}]，仅探索性；主分母仍为50世界，没有换成这个子集。

**下一步最有价值的一项验证**：保持模型和新世界生成规则，比较原D与一个固定“先按entity key从来源事实形成project–code支持对、再输出答案及这对ID”的D协议。保留本轮e3分量对照；同时检查答案和真实来源配对，不再只看裸答案或citation ID。先验证该接收者核验程序能否减少错误结论干扰及引用遗漏，再考虑预测特征或第二模型。本轮没有执行这一新方案。

最终资源：两个Slurm作业均COMPLETED，本轮 {accounting['requests']} 请求、{accounting['generated_tokens']} 生成token、{accounting['total_gpu_seconds']} GPU秒（{accounting['gpu_hours']:.4f}小时）；单卡B300。所有主检验代码/数据哈希保持冻结版本；本节标为事后解释，相关CSV和脚本独立保存。
'''
 p=HERE/'REPORT.md';s=p.read_text().split('\n## 机制解读：哪些可以解释，哪些仍不能（事后描述性补充）\n')[0];s=s.replace('预算账本GPU时间 0.1110 小时','Slurm核对GPU时间 0.1136 小时');p.write_text(s+t)
 write(HERE/'results/mechanism_summary.json',dict(conditions=1400,worlds=50,direct_sufficient_worlds=50,answer_components=summary,answer_ablation=effects,interaction_decomposition=decomp,structurally_redundant_worlds=len(adequate_worlds),resource=accounting,interpretation_scope='post-hoc descriptive, all preregistered primary tests preserved'))
 print('INTERPRETATION COMPLETE; redundancy subset',len(adequate_worlds),'answer gain',first)
if __name__=='__main__':main()
