"""Descriptive presentation only: no retraining, refitting or condition selection."""
import csv,collections
import numpy as np
from protocol_pilot.common import *
from protocol_pilot.reporting import csvout
run=ROOT/'runs/pilot-v1';out=rows(run/'outcomes.jsonl');tr=rows(run/'traces.jsonl');trace={t['cache_key']:t for t in tr};index={(o['query_id'],o['condition']):o for o in out};queries={q['query_id']:q for q in rows(ROOT/'data/queries.jsonl')};gold={g['query_id']:g for g in rows(ROOT/'data/gold.jsonl')}
edge_summary=[];local=[]
for cond in sorted({o['condition'] for o in out}):
 os=[o for o in out if o['condition']==cond]
 for edge in ['e1','e2','e3','e4','e5']:
  ts=[o['edge_tokens'][edge] for o in os];edge_summary.append(dict(condition=cond,edge=edge,n=len(ts),mean_tokens=np.mean(ts),total_tokens=sum(ts),min_tokens=min(ts),max_tokens=max(ts)))
 for edge in ['e1','e2','e4','e5']:
  local.append(dict(condition=cond,edge=edge,n=len(os),precision=np.mean([o['local'][edge]['precision'] for o in os]),recall=np.mean([o['local'][edge]['recall'] for o in os]),F1=np.mean([o['local'][edge]['f1'] for o in os]),C_answer_accuracy=np.mean([o['c_metrics']['answer_accuracy'] for o in os]),visible_evidence_sufficient_rate=np.mean([o['recovery']['oracle_visible_sufficient'] for o in os]),edge_schema_legal=np.mean([o['schema_legal'] for o in os])))
csvout('edge_tokens.csv',edge_summary);csvout('local_and_intermediate_metrics.csv',local)
resource=[]
for role in 'ABCD':
 ts=[t for t in tr if t['role']==role];resource.append(dict(role=role,actual_requests=len(ts),input_tokens=sum(t['input_tokens'] for t in ts),generated_tokens=sum(t['output_tokens'] for t in ts),max_input=max(t['input_tokens'] for t in ts),max_output=max(t['output_tokens'] for t in ts),generation_seconds=sum(t['seconds'] for t in ts),length_stops=sum(t['finish_reason']=='length' for t in ts)))
csvout('node_resources.csv',resource)
# Enrich the already selected, preregistered lexicographic examples without replacing them.
case_details=[]
for c in rows(ROOT/'results/cases.jsonl'):
 if not c.get('query_id'):continue
 key=(c['query_id'],c.get('condition','restore'));o=index[key];b=index[(key[0],'full')];q=queries[key[0]]
 case_details.append(dict(**c,question=q['question'],gold=gold[key[0]],reference_D=trace[b['nodes']['D']]['parsed'],modified_D=trace[o['nodes']['D']]['parsed'],reference_C=trace[b['nodes']['C']]['parsed'],modified_C=trace[o['nodes']['C']]['parsed'],reference_local=b['local'],modified_local=o['local'],audit=o['audit'],reference_edges=b['edges'],modified_edges=o['edges'],node_keys=o['nodes']))
jsonl(ROOT/'results/case_details.jsonl',case_details)
def loadcsv(name):return list(csv.DictReader((ROOT/'results'/name).open()))
def table(rs,fields):return '| '+' | '.join(fields)+' |\n|'+'|'.join(['---']*len(fields))+'|\n'+'\n'.join('| '+' | '.join(str(r.get(f,'')) for f in fields)+' |' for r in rs)
comparisons=loadcsv('primary_comparisons.csv');aps=next(r for r in comparisons if r['group']=='all' and r['measure']=='AUPRC');estimate=float(aps['difference_M3_minus_M2']) if aps['difference_M3_minus_M2'] else None
if estimate is None:h3='有害事件类别不足，H3 的 AUPRC 优势无法识别。'
else:
 significant=float(aps['ci_low'])>0 and float(aps.get('p_holm') or 1)<.05
 h3=f"M3−M2 的总体有害事件 AUPRC 差为 {estimate:.4f}，95%世界聚类区间 [{float(aps['ci_low']):.4f}, {float(aps['ci_high']):.4f}]，Holm校正p={aps.get('p_holm','N/A')}；"+('本合成设置下支持依赖特征有增益。' if significant else '未达到预注册主要比较的优势证据标准，不能宣称依赖特征有效提升。')
pair=loadcsv('pair_interactions.csv');stable=[r for r in pair if r['split']=='all' and r['subset']=='all' and float(r['ci_low'])>0 and int(r['worlds'])>=20];h2=f"共有 {len(stable)} 个≥20世界的组合出现正J且未校正95%区间不跨零（探索性，不等于跨任务普遍规律）。"
dem=loadcsv('demand_effects.csv');demhits=[r for r in dem if float(r['ci_low'])>0 or float(r['ci_high'])<0];h1=f"同世界双需求的删除效果差有 {len(demhits)} 个family×condition切片的未校正95%区间不跨零；这是探索性H1证据，完整分母和多重性不能忽略。"
text='\n## 结果解读与补充审计\n\n'+h1+'\n\n'+h2+'\n\n'+h3+'\n\n'
text+='原始模型调用统计见node_resources.csv，通信量见edge_tokens.csv，本侧precision/recall/F1、C正确率和可用依据见local_and_intermediate_metrics.csv。\n\n'+table(resource,['role','actual_requests','input_tokens','generated_tokens','max_input','max_output','length_stops'])+'\n\n'
text+='全部独立smoke共320个成功节点调用（v1与v2各160），另64次失败基础设施请求无可用输出；自动报告开头smoke请求数指最终v2版本，预算账本包括所有版本和失败。\n\n'
text+='### 条件化保留规则（预声明规则的观测支持）\n\n'+table(loadcsv('retention_rules.csv'),['condition','retain','n_worlds','n_queries','removal_delta_L','ci_low','ci_high'])+'\n\n'
text+='### 案例详情\n\n以下沿用cases.jsonl的预定字典序选样，未按恢复或预测成功重选。完整边消息、局部指标、改动审计与节点key见case_details.jsonl。\n\n'
for c in case_details:
 text+=f"- `{c['query_id']}` / `{c.get('condition','restore')}`：类别 {c['category']}；gold={c['gold']['answer']}；full D={c['reference_D']}；modified D={c['modified_D']}。\n"
report=(ROOT/'REPORT.md').read_text();marker='\n## 结果解读与补充审计\n';report=report.split(marker)[0];(ROOT/'REPORT.md').write_text(report+text)
write(ROOT/'results/interpretation.json',dict(H1=h1,H2=h2,H3=h3))
print(h1,h2,h3,sep='\n')
