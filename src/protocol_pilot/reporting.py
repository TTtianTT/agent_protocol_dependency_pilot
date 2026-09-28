import csv,itertools,math
import numpy as np
from scipy.stats import spearmanr
from sklearn.metrics import average_precision_score,brier_score_loss,precision_score,recall_score
from .common import *

def csvout(name,rs):
 p=ROOT/'results'/name
 if not rs:p.write_text('');return
 fields=list(dict.fromkeys(k for r in rs for k in r))
 with p.open('w') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rs)
def cluster_ci(records,field,n=2000):
 groups={}
 for r in records:groups.setdefault(r['world_id'],[]).append(r[field])
 if not groups:return [None,None]
 sums=np.array([sum(v) for v in groups.values()]);counts=np.array([len(v) for v in groups.values()]);rng=np.random.default_rng(2000);idx=rng.integers(0,len(groups),(n,len(groups)));vals=sums[idx].sum(1)/counts[idx].sum(1)
 return [float(x) for x in np.quantile(vals,[.025,.975])]
def ap(y,p):return float(average_precision_score(y,p)) if len(set(y))==2 else None
def main():
 run=ROOT/'runs/pilot-v1';out=rows(run/'outcomes.jsonl');preds=rows(run/'predictions_before_execution.jsonl');lookup={(o['query_id'],o['condition']):o for o in out};full={o['query_id']:o for o in out if o['condition']=='full'}
 derived=[]
 for o in out:
  b=full[o['query_id']];delta=b['metrics']['joint_success']-o['metrics']['joint_success'];pdelta=np.mean([o['local'][e]['precision']-b['local'][e]['precision'] for e in o['local']]);rdelta=np.mean([o['local'][e]['recall']-b['local'][e]['recall'] for e in o['local']]);saving=sum(b['edge_tokens'].values())-sum(o['edge_tokens'].values())
  # Only evidence-backed positive recovery claims are made; no-proof remains unclassified.
  failure='success' if o['metrics']['joint_success'] else 'format_failure' if not o['metrics']['parse_success'] else 'usable_information_agent_failure' if o['recovery']['oracle_visible_sufficient'] else 'undetermined_recoverability'
  derived.append(dict(query_id=o['query_id'],world_id=o['world_id'],split=o['split'],family=o['family'],demand=o['demand'],condition=o['condition'],group=o['group'],joint_success=o['metrics']['joint_success'],reference_success=b['metrics']['joint_success'],delta_L=delta,token_saving=saving,precision_change=float(pdelta),recall_change=float(rdelta),quality_reversal=int(pdelta>0 and delta>0),efficiency_tradeoff=int(saving>0 and delta>0),failure_class=failure,noop=int(bool(o['audit']) and all(a.get('noop',False) for a in o['audit'])),**{k:v for k,v in o['metrics'].items() if k!='joint_success'}))
 csvout('sample_metrics.csv',derived)
 metrics=[]
 for split in ['train','validation','test','all']:
  for cond in sorted({o['condition'] for o in out}):
   rs=[r for r in derived if r['condition']==cond and (split=='all' or r['split']==split)]
   if not rs:continue
   lo,hi=cluster_ci(rs,'delta_L');metrics.append(dict(split=split,condition=cond,n=len(rs),worlds=len({r['world_id'] for r in rs}),joint_success=np.mean([r['joint_success'] for r in rs]),answer_accuracy=np.mean([r['answer_accuracy'] for r in rs]),parse_success=np.mean([r['parse_success'] for r in rs]),evidence_validity=np.mean([r['evidence_validity'] for r in rs]),evidence_coverage=np.mean([r['evidence_coverage'] for r in rs]),insufficient_rate=np.mean([r['insufficient'] for r in rs]),coverage=np.mean([1-r['insufficient'] for r in rs]),selective_accuracy=np.mean([r['answer_accuracy'] for r in rs if not r['insufficient']]) if any(not r['insufficient'] for r in rs) else None,delta_L=np.mean([r['delta_L'] for r in rs]),ci_low=lo,ci_high=hi,success_to_failure=sum(r['delta_L']>0 for r in rs),failure_to_success=sum(r['delta_L']<0 for r in rs),mean_token_saving=np.mean([r['token_saving'] for r in rs]),noops=sum(r['noop'] for r in rs)))
 csvout('condition_metrics.csv',metrics)
 # Complete 00/10/01/11, with query/world bindings retained.
 pairs=[]
 for o in out:
  if o['group'] not in ['seen_pair','held_pair']:continue
  q=o['query_id'];a,b=o['ops']
  if (q,a) not in lookup or (q,b) not in lookup:continue
  vals=[1-lookup[(q,c)]['metrics']['joint_success'] for c in ['full',a,b,o['condition']]]
  pairs.append(dict(world_id=o['world_id'],query_id=q,condition=o['condition'],split=o['split'],group=o['group'],demand=o['demand'],L00=vals[0],L10=vals[1],L01=vals[2],L11=vals[3],J=vals[3]-vals[1]-vals[2]+vals[0],applied=all(not x.get('noop',False) for x in o['audit'])))
 csvout('pair_sample_metrics.csv',pairs);pairagg=[]
 for split in ['all','test']:
  for cond in sorted({r['condition'] for r in pairs}):
   for subset in ['all','applied']:
    rs=[r for r in pairs if r['condition']==cond and (split=='all' or r['split']==split) and (subset=='all' or r['applied'])]
    if not rs:continue
    lo,hi=cluster_ci(rs,'J');pairagg.append(dict(split=split,subset=subset,condition=cond,n=len(rs),worlds=len({r['world_id'] for r in rs}),**{k:np.mean([r[k] for r in rs]) for k in ['L00','L10','L01','L11','J']},ci_low=lo,ci_high=hi))
 csvout('pair_interactions.csv',pairagg)
 # H1: paired demand-specific intervention effects, not unrelated family averages.
 h1=[];dm={(r['world_id'],r['condition'],r['demand']):r for r in derived}
 for r in derived:
  if r['demand']==0 and r['condition']!='full' and (r['world_id'],r['condition'],1) in dm:
   z=dm[(r['world_id'],r['condition'],1)];h1.append(dict(world_id=r['world_id'],family=r['family'],condition=r['condition'],demand0_delta=r['delta_L'],demand1_delta=z['delta_L'],difference=z['delta_L']-r['delta_L']))
 csvout('demand_sample_metrics.csv',h1);h1agg=[]
 for fam,cond in sorted({(r['family'],r['condition']) for r in h1}):
  rs=[r for r in h1 if r['family']==fam and r['condition']==cond];lo,hi=cluster_ci(rs,'difference');h1agg.append(dict(family=fam,condition=cond,n_worlds=len(rs),demand0_delta=np.mean([r['demand0_delta'] for r in rs]),demand1_delta=np.mean([r['demand1_delta'] for r in rs]),difference=np.mean([r['difference'] for r in rs]),ci_low=lo,ci_high=hi))
 csvout('demand_effects.csv',h1agg)
 pm=[];selection=[];testrows=[]
 for p in preds:
  key=(p['query_id'],p['condition'])
  if key not in lookup:continue
  o=lookup[key];b=full[p['query_id']];delta=b['metrics']['joint_success']-o['metrics']['joint_success'];base_tokens=sum(b['edge_tokens'].values());modified_tokens=sum(o['edge_tokens'].values())
  for m,x in p['predictions'].items():testrows.append(dict(world_id=p['world_id'],query_id=p['query_id'],condition=p['condition'],group=p['group'],model=m,y=int(delta>0),delta=delta,p=x['harm_probability'],reg=x['delta_L'],threshold=x['threshold'],accept=x['accept'],reference_success=b['metrics']['joint_success'],modified_success=o['metrics']['joint_success'],policy_change=-delta*int(x['accept']),tokens_saved=(base_tokens-modified_tokens)*int(x['accept']),baseline_tokens=base_tokens))
 csvout('prediction_sample_metrics.csv',testrows)
 for group in ['all','atom','seen_pair','held_pair','held_triple','control']:
  for m in ['M0','M1','M2','M3']:
   rs=[r for r in testrows if r['model']==m and (group=='all' or r['group']==group)]
   if not rs:continue
   y=np.array([r['y'] for r in rs]);p=np.array([r['p'] for r in rs]);delta=np.array([r['delta'] for r in rs]);reg=np.array([r['reg'] for r in rs]);thr=rs[0]['threshold'];binary=p>=thr;auprc=ap(y,p)
   pm.append(dict(group=group,model=m,n=len(rs),worlds=len({r['world_id'] for r in rs}),harm_count=int(y.sum()),AUPRC=auprc,Brier=brier_score_loss(y,p),MAE=float(np.mean(abs(delta-reg))),direction_accuracy=float(np.mean(np.sign(delta)==np.sign(reg))),Spearman=float(spearmanr(delta,reg).statistic) if len(set(delta))>1 and len(set(reg))>1 else None,threshold=thr,precision=float(precision_score(y,binary,zero_division=0)) if len(set(y))==2 else None,recall=float(recall_score(y,binary,zero_division=0)) if len(set(y))==2 else None))
   lo,hi=cluster_ci(rs,'policy_change');tlo,thi=cluster_ci(rs,'tokens_saved');selection.append(dict(group=group,model=m,n=len(rs),acceptance=np.mean([r['accept'] for r in rs]),reference_success=np.mean([r['reference_success'] for r in rs]),policy_success=np.mean([r['reference_success']+r['policy_change'] for r in rs]),success_change=np.mean([r['policy_change'] for r in rs]),ci_low=lo,ci_high=hi,mean_tokens_saved=np.mean([r['tokens_saved'] for r in rs]),token_ci_low=tlo,token_ci_high=thi,token_saving_fraction=sum(r['tokens_saved'] for r in rs)/sum(r['baseline_tokens'] for r in rs),harm_leakage=sum(r['accept'] and r['y'] for r in rs)/sum(y) if sum(y) else None))
 csvout('prediction_metrics.csv',pm);csvout('protocol_selection.csv',selection)
 # Paired world bootstrap of primary M3-M2 comparisons, rejecting single-class AP replicates.
 comparisons=[]
 for group in ['all','seen_pair','held_pair','held_triple']:
  a=[r for r in testrows if r['model']=='M2' and (group=='all' or r['group']==group)];b=[r for r in testrows if r['model']=='M3' and (group=='all' or r['group']==group)]
  assert [(r['query_id'],r['condition']) for r in a]==[(r['query_id'],r['condition']) for r in b]
  if not a:continue
  worlds=sorted({r['world_id'] for r in a});indices=[np.array([i for i,r in enumerate(a) if r['world_id']==w]) for w in worlds];rng=np.random.default_rng(2000)
  yy=np.array([r['y'] for r in a]);p2=np.array([r['p'] for r in a]);p3=np.array([r['p'] for r in b]);s=np.array([rb['policy_change']-ra['policy_change'] for ra,rb in zip(a,b)]);t=np.array([rb['tokens_saved']-ra['tokens_saved'] for ra,rb in zip(a,b)])
  vals={'AUPRC':[],'policy_success':[],'tokens_saved':[]}
  for _ in range(2000):
   idx=np.concatenate([indices[j] for j in rng.integers(0,len(worlds),len(worlds))]);v2=ap(yy[idx],p2[idx]);v3=ap(yy[idx],p3[idx])
   if v2 is not None:vals['AUPRC'].append(v3-v2)
   vals['policy_success'].append(float(s[idx].mean()));vals['tokens_saved'].append(float(t[idx].mean()))
  p2ap=ap(yy,p2);p3ap=ap(yy,p3)
  for measure,vs in vals.items():
   estimate=(p3ap-p2ap if p2ap is not None else None) if measure=='AUPRC' else float((s if measure=='policy_success' else t).mean())
   lo,hi=np.quantile(vs,[.025,.975]) if vs else (None,None)
   # centered bootstrap two-sided null approximation; ties yield p=1
   pv=float((1+sum(abs(v-estimate)>=abs(estimate) for v in vs))/(len(vs)+1)) if vs and estimate is not None else None
   comparisons.append(dict(group=group,measure=measure,difference_M3_minus_M2=estimate,ci_low=lo,ci_high=hi,bootstrap_valid=len(vs),n_worlds=len(worlds),p_bootstrap=pv,primary=group=='all'))
 prim=[c for c in comparisons if c['primary'] and c['p_bootstrap'] is not None];ordered=sorted(prim,key=lambda c:c['p_bootstrap']);last=0
 for i,c in enumerate(ordered):last=max(last,min(1,c['p_bootstrap']*(len(ordered)-i)));c['p_holm']=last
 csvout('primary_comparisons.csv',comparisons)
 # Predeclared lexicographic cases. Restore contrasts include the deleted atomic outcome.
 categories={'quality_reversal':lambda r:r['quality_reversal'],'efficiency_tradeoff':lambda r:r['efficiency_tradeoff'],'redundancy_failure':lambda r:r['group'] in ['seen_pair','held_pair','held_triple'] and r['delta_L']>0 and 'ev' in r['condition'],'inconsistent_keys':lambda r:'ren' in r['condition'] and r['delta_L']>0,'no_effect':lambda r:r['condition']!='full' and r['delta_L']==0}
 cases=[]
 for category,predicate in categories.items():
  chosen=sorted([r for r in derived if predicate(r)],key=lambda r:(r['query_id'],r['condition']))[:2]
  for r in chosen:cases.append(dict(category=category,**r,payload_hash=lookup[(r['query_id'],r['condition'])]['payload_hash']))
  if not chosen:cases.append(dict(category=category,status='not observed'))
 restores=[]
 for o in out:
  if o['condition']=='restore':
   target=o['audit'][0]['target'];deleted=lookup.get((o['query_id'],target));base=full[o['query_id']]
   if deleted:restores.append(dict(world_id=o['world_id'],query_id=o['query_id'],target=target,deleted_success=deleted['metrics']['joint_success'],restored_success=o['metrics']['joint_success'],repair=o['metrics']['joint_success']-deleted['metrics']['joint_success']))
 csvout('restore_metrics.csv',restores)
 # Frozen condition-to-information rules, reporting paired removal effect rather than universality.
 rules=[]
 for fam,cond,demand,information in [('redundant_evidence','ev3+ev5',1,'B source evidence through C or direct e5'),('qualifier','q1+q4',1,'required year through upstream A or direct A'),('entity_join','ev4+jk1',1,'A identity association through upstream or direct A'),('deferred_disambiguation','ev3+t1',1,'all local candidates or a direct evidence alternative')]:
  rs=[r for r in derived if r['family']==fam and r['condition']==cond and r['demand']==demand];lo,hi=cluster_ci(rs,'delta_L');rules.append(dict(condition=fam+':demand'+str(demand),retain=information,n_worlds=len({r['world_id'] for r in rs}),n_queries=len(rs),removal_delta_L=np.mean([r['delta_L'] for r in rs]) if rs else None,ci_low=lo,ci_high=hi,scope='predefined rule; descriptive all splits, not global necessity'))
 csvout('retention_rules.csv',rules)
 for category,predicate in [('restore_success',lambda r:r['repair']>0),('restore_failure',lambda r:r['restored_success']==0)]:
  chosen=sorted([r for r in restores if predicate(r)],key=lambda r:r['query_id'])[:1];cases.extend([dict(category=category,**r) for r in chosen] or [dict(category=category,status='not observed')])
 jsonl(ROOT/'results/cases.jsonl',cases)
 figures(derived,pairagg,pm,selection)
 report(out,derived,metrics,pairagg,h1agg,pm,selection,comparisons,restores,cases)

def figures(derived,pairs,pm,selection):
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 for field,title,name in [('precision_change','Local precision change vs final loss change','quality_scatter'),('token_saving','Communication saving vs final loss change','efficiency_scatter')]:
  rs=[r for r in derived if r['condition']!='full'];fig,ax=plt.subplots(figsize=(7,4));ax.scatter([r[field] for r in rs],[r['delta_L'] for r in rs],alpha=.08,s=12);ax.set(xlabel=field,ylabel='Delta loss',title=title);fig.tight_layout();fig.savefig(ROOT/'results/figures'/f'{name}.png',dpi=180);plt.close(fig)
 rs=[r for r in pairs if r['split']=='all' and r['subset']=='all'];fig,ax=plt.subplots(figsize=(11,6));im=ax.imshow([[r[k] for k in ['L00','L10','L01','L11','J']] for r in rs],aspect='auto',vmin=-1,vmax=1,cmap='coolwarm');ax.set_yticks(range(len(rs)),[r['condition'] for r in rs]);ax.set_xticks(range(5),['L00','L10','L01','L11','J']);ax.set_title('Observed four-cell losses and interaction');fig.colorbar(im,ax=ax);fig.tight_layout();fig.savefig(ROOT/'results/figures/pair_interactions.png',dpi=180);plt.close(fig)
 rs=[r for r in pm if r['group']=='all'];fig,axs=plt.subplots(1,2,figsize=(9,4));axs[0].bar([r['model'] for r in rs],[r['AUPRC'] or 0 for r in rs]);axs[0].set_title('Harm prediction AUPRC');axs[1].bar([r['model'] for r in rs],[r['Brier'] for r in rs]);axs[1].set_title('Harm prediction Brier');fig.tight_layout();fig.savefig(ROOT/'results/figures/prediction_comparison.png',dpi=180);plt.close(fig)

def report(out,derived,metrics,pairs,h1,pm,selection,comparisons,restores,cases):
 run=ROOT/'runs/pilot-v1';usage=read(run/'resource_usage.json');traces=rows(run/'traces.jsonl');smoke=rows(ROOT/'runs/smoke-v2/traces.jsonl');model=read(ROOT/'configs/model_identity.json');full=[o for o in out if o['condition']=='full'];mods=[r for r in derived if r['condition']!='full'];complete=(run/'completed.json').exists() and len(out)==3600
 def table(rs,fields):
  def fmt(v):return 'N/A' if v is None else f'{v:.4f}' if isinstance(v,(float,np.floating)) else str(v)
  return '| '+' | '.join(fields)+' |\n|'+'|'.join(['---']*len(fields))+'|\n'+'\n'.join('| '+' | '.join(fmt(r.get(k)) for k in fields)+' |' for r in rs)
 failures={c:sum(r['failure_class']==c for r in derived) for c in sorted({r['failure_class'] for r in derived})};cert=rows(ROOT/'results/collision_certificates.jsonl');interesting=sorted(h1,key=lambda r:abs(r['difference']),reverse=True)[:10]
 txt=f'''# 固定 Agent workflow 消息依赖预实验报告

状态：{'预实验完成' if complete else '未完成，仅报告共同已完成部分'}。

1. 实际完成 {len({o['world_id'] for o in out})} 个正式世界、{len(full)} 个查询、{len(out)}/3600 个条件。正式实际节点请求 {len(traces)}（含碰撞诊断），smoke 请求 {len(smoke)}；总预算账本 {usage['requests']} 次请求、{usage['generated_tokens']} 个生成 token、{usage['gpu_seconds']/3600:.3f} GPU 小时。模型 {model['name']}，revision `{model['revision']}`，单张 NVIDIA B300，BF16、无量化、vLLM {model['versions']['vllm']}，关闭 thinking，温度0，固定 JSON 约束解码。文件 hash/模板见 configs/model_identity.json。
2. 按预声明的本侧事实 precision，观察到质量反转 {sum(r['quality_reversal'] for r in mods)} 条；仅节约 token 而损失增加 {sum(r['efficiency_tradeoff'] for r in mods)} 条。二者不混称。所有样本 precision/recall 变化均在 sample_metrics.csv；高抽取 precision 可造成局部质量指标天花板。
3. 需求影响按同世界双版本的 ΔL 差计算，完整见 demand_effects.csv。下表按绝对差排序展示，属于探索性，未按测试结果筛掉样本。
4. 跨边行为交互见完整四格表；正 J 仅代表本流程的额外损失，不是互信息。稳定性需结合世界级区间及样本量，不能把不显著解释为无害。
5. M3/M2/M1 的未见世界、已见 pair、全局留出 pair/triple 分开报告如下；主要比较给出2000次世界聚类 bootstrap 区间及 Holm 校正。不是任意真实 Agent 系统的结论。
6. 预定 restore {len(restores)} 查询；修复改善 {sum(r['repair']>0 for r in restores)}，恢复后仍失败 {sum(r['restored_success']==0 for r in restores)}。恢复定义为发送前删除再精确还原（可与原子删除配对），不是额外 LLM 修复 Agent。失败分类计数：{failures}。无充分性证明的失败保持“不确定”，不强称不可恢复。独立诊断碰撞证书 oracle {sum(c['type']=='oracle' for c in cert)}，实际 LLM {sum(c['type']=='actual_llm' for c in cert)}，仅适用于证书中的完整边界。
7. 本轮支持程度应以以下观测和区间为准；不能预设 H1–H3 成立。下一步最有价值的实验是在一个新模型和新生成的世界上，复验本轮事前预测最危险的跨边组合，并保留同样的四格及恢复对照。

## 执行与审计

正式 full joint_success = {np.mean([o['metrics']['joint_success'] for o in full]):.4f}；full answer accuracy = {np.mean([o['metrics']['answer_accuracy'] for o in full]):.4f}。参考日志成本：{sum(t['condition']=='full' for t in traces)} 次实际节点请求，{sum(t['output_tokens'] for t in traces if t['condition']=='full')} 生成 token。预测基于已有参考日志，绝非零成本在线预测。日志逐条 fsync，缓存 key 含模型、完整可见输入、提示、配置及源代码 hash；A/B 不看另一侧资料，C 只看 e1/e2，D 只看 e3/e4/e5。

split 以world为单位20/10/10每族；test新实体和附加措辞模板。test预测只读快照在干预前完成，hash/时间见 prediction_freeze.json。主样本分母含所有full成功和失败。no-op条件保留；applied子集另列。解析失败计任务失败，基础设施失败单独写failures.jsonl。

## 需求配对结果（探索性）

{table(interesting,['family','condition','n_worlds','demand0_delta','demand1_delta','difference','ci_low','ci_high'])}

## 完整跨边四格

{table([r for r in pairs if r['split']=='all' and r['subset']=='all'],['condition','n','worlds','L00','L10','L01','L11','J','ci_low','ci_high'])}

四格均以相同query对齐；所有查询版本与条件在bootstrap中绑定world。test分表及实际应用子集见 pair_interactions.csv；不能把多条件当作独立样本。

## 预测器

{table(pm,['group','model','n','harm_count','AUPRC','Brier','MAE','precision','recall'])}

类别单一时AUPRC/precision/recall显示N/A。M1–M3使用相同C候选与正则化线性/逻辑回归；超参数和阈值仅validation决定。连续ΔL和有害概率分别拟合。对上游干预的token变化是基于参考消息的事前估计，无法使用未来C重写。test局部gold、最终输出、J未用于特征。

## 主要比较及策略

{table(comparisons,['group','measure','difference_M3_minus_M2','ci_low','ci_high','bootstrap_valid','p_bootstrap','p_holm'])}

全体test候选的三项主要比较作Holm校正；其他切片探索性。bootstrap p值为中心化双侧近似；置信区间宽和不显著都不构成非劣证据。

{table([r for r in selection if r['group']=='all'],['model','n','acceptance','reference_success','policy_success','success_change','ci_low','ci_high','token_saving_fraction','harm_leakage'])}

拒绝则回退到同题full，所有方法面对相同候选。通信token与推理输入/输出token分别保存，不混用。策略通信节省以实际执行payload计；选择判定只用事前预测。

## 条件化保留规则与限制

保留规则的支持世界数及删除效果区间见 retention_rules.csv（每规则只取指定需求版本，每世界一次）。本轮未优化或声称全局最小协议。预声明公共规则：需要证据→保留足以支持答案的来源内容或等价直达备份；需要跨实体关联→保留一致键映射或完整替代路径；指定年份→保留相应限定。经验支持样本数与效应区间逐条件见 condition_metrics.csv / demand_effects.csv / pair_interactions.csv；没有独立完成可行性证据的规则不得宣称普遍必需。

日期子型只含年份有效期，不包含否定或单位。候选删除遵循发送方原始顺序，未用最终答案。单边rename使用公开字符置换加前缀的一一映射；一致rename同时部署到四条边界边。drop_evidence删除实际来源内容及链接，并非只删citation。当前source ID仍可能提供替代线索，负面恢复判定不作信息论证明。

实际LLM输出上的碰撞与oracle碰撞分别保存，证书比较公共问题与e1/e2/e4/e5全部可见字节；不同gold且全部输入一致才颁证。证书诊断不计入正式条件效果分母。

## 可追溯案例

{table(cases,['category','query_id','condition','delta_L','token_saving','status'])}

选择规则为类别内query/condition字典序，所有样本汇总在sample_metrics.csv。未观察到的类别明示，未编造案例。恢复案例的目标原子见restore_metrics.csv；payload和完整节点输入输出通过outcomes.nodes连接traces.cache_key。

## 图与复现

![局部质量](results/figures/quality_scatter.png)
![通信效率](results/figures/efficiency_scatter.png)
![四格](results/figures/pair_interactions.png)
![预测](results/figures/prediction_comparison.png)

底层CSV分别为sample_metrics.csv、pair_interactions.csv、prediction_metrics.csv。README提供生成、验证、smoke、正式、续跑与重新统计命令。所有数据均来自本项目生成和实际推理，未引用其他项目实验。
'''
 (ROOT/'REPORT.md').write_text(txt)
 write(ROOT/'RUN_STATUS.json',dict(status='complete' if complete else 'incomplete',worlds=len({o['world_id'] for o in out}),queries=len(full),conditions=len(out),usage=usage))
 (ROOT/'RUN_STATUS.md').write_text(f"状态：{'预实验完成' if complete else '未完成'}\n正式条件 {len(out)}/3600；实际总请求 {usage['requests']}；GPU小时 {usage['gpu_seconds']/3600:.3f}。\n")
 print('REPORT WRITTEN',len(out),flush=True)
if __name__=='__main__':main()
