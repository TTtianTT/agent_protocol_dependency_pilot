import csv,collections,math
from pathlib import Path
import numpy as np
from protocol_pilot.common import ROOT,canon,digest,read,rows,write,jsonl
HERE=Path(__file__).resolve().parent

def savecsv(name,items):
 path=HERE/'results'/name
 if not items:path.write_text('');return
 fields=list(dict.fromkeys(k for row in items for k in row))
 with path.open('w') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(items)
def mean(rs,key):return float(np.mean([r[key] for r in rs])) if rs else None
def bootstrap(rs,key):
 groups=collections.defaultdict(list)
 for r in rs:groups[r['world_id']].append(r[key])
 if not groups:return dict(estimate=None,ci_low=None,ci_high=None,p=None,n=0,worlds=0)
 sums=np.array([sum(v) for v in groups.values()]);ns=np.array([len(v) for v in groups.values()]);estimate=float(sums.sum()/ns.sum());rng=np.random.default_rng(12026);idx=rng.integers(0,len(groups),(5000,len(groups)));samples=sums[idx].sum(1)/ns[idx].sum(1);lo,hi=np.quantile(samples,[.025,.975]);p=(1+np.sum(abs(samples-estimate)>=abs(estimate)))/(len(samples)+1)
 return dict(estimate=estimate,ci_low=float(lo),ci_high=float(hi),p=float(p),n=int(ns.sum()),worlds=len(groups))
def fmt(x):return 'N/A' if x is None else f'{x:.4f}' if isinstance(x,(float,np.floating)) else str(x)
def table(rs,fields):
 return '| '+' | '.join(fields)+' |\n|'+'|'.join(['---']*len(fields))+'|\n'+'\n'.join('| '+' | '.join(fmt(r.get(k)) for k in fields)+' |' for r in rs)


def audit():
 from run import verify_freeze,NAMES
 freeze=verify_freeze();run=HERE/'runs/formal';out=rows(run/'outcomes.jsonl');tr=rows(run/'traces.jsonl');up=rows(run/'upstream.jsonl');plan=[p for p in rows(HERE/'data/plan.jsonl') if p['split']=='formal'];assert len(out)==len(plan)==1400
 assert {(o['query_id'],o['condition']) for o in out}=={(p['query_id'],p['condition']) for p in plan}
 assert len({(o['query_id'],o['condition']) for o in out})==1400
 index={(o['world_id'],o['demand'],o['condition']):o for o in out};nodes={t['cache_key']:t for t in tr}
 for w in {o['world_id'] for o in out}:
  for c in NAMES:
   a=index[w,0,c];b=index[w,1,c];assert a['payload_hash']==b['payload_hash'],'Demand versions changed evidence'
  for d in [0,1]:
   original=index[w,d,'original']
   for c in NAMES:
    o=index[w,d,c];assert o['edge_hashes']['e4']==original['edge_hashes']['e4']
    if c not in ['drop_e5','drop_e3_evidence_and_e5']:assert o['edge_hashes']['e5']==original['edge_hashes']['e5']
    trace=nodes[o['nodes']['D']];visible=__import__('json').loads(trace['visible_input'][1]['content']);assert set(visible)==({'question','e4','e5'} if c=='no_e3' else {'question','e3','e4','e5'});assert trace['dependency_hash']==o['D_dependency_hash'];assert digest(trace['visible_input'])==trace['dependency_hash']
    if 'without_answer' in c:assert 'answer' not in o['edges']['e3']
    assert o['code_hash']==freeze['execution_hash']
 for t in tr:
  assert t['code_hash']==freeze['execution_hash'];v=__import__('json').loads(t['visible_input'][1]['content'])
  if t['role'] in ['A','B']:assert set(v)=={'question','document'}
  if t['role']=='C':assert set(v)=={'question','e1','e2'}
 assert all(u['nodes']['C']!=u['nodes']['C_natural'] for u in up)
 result=dict(passed=True,worlds=50,queries=100,conditions=1400,formal_actual_calls=len(tr),matched_payload_demand_pairs=700,direct_evidence_invariant=True,no_hidden_context=True,source_hash=freeze['execution_hash'],freeze_time=freeze['time'],first_formal_inference_time=min(t['time'] for t in tr),parse_failures=sum(t['parse_error'] is not None for t in tr),length_stops=sum(t['finish_reason']=='length' for t in tr))
 write(HERE/'results/completion_audit.json',result);return result

def main():
 aud=audit();run=HERE/'runs/formal';out=rows(run/'outcomes.jsonl');tr=rows(run/'traces.jsonl');up=rows(run/'upstream.jsonl');idx={(o['world_id'],o['demand'],o['condition']):o for o in out};gold={g['query_id']:g for g in rows(HERE/'data/gold.jsonl')};worlds=sorted({o['world_id'] for o in out});names=list(dict.fromkeys(o['condition'] for o in out))
 sample=[]
 for o in out:
  w,d,c=o['world_id'],o['demand'],o['condition'];base=idx[w,d,'original'];none=idx[w,d,'no_e3'];m=o['metrics'];direct=base['metrics']['direct_evidence_sufficient'];joint=m['joint_success_strict'];none_success=none['metrics']['joint_success_strict'];has_proof=m['source_evidence_sufficient']
  if joint:category='success'
  elif not m['parse_success']:category='format_failure'
  elif direct and c not in ['drop_e5','drop_e3_evidence_and_e5'] and none_success:category='paired_e3_interference'
  elif has_proof:category='sufficient_evidence_receiver_failure'
  elif m['correct_proposal_present']:category='correct_proposal_without_source_proof'
  else:category='source_proof_missing_other_information_undetermined'
  sample.append(dict(world_id=w,query_id=o['query_id'],stratum=o['stratum'],demand=d,condition=c,joint_success=joint,joint_success_legacy=m['joint_success_legacy'],answer_accuracy=m['answer_accuracy'],citation_support=int(m['cited_visible_evidence_sufficient']),insufficient=m['insufficient'],parse_success=m['parse_success'],source_evidence_sufficient=int(has_proof),direct_evidence_sufficient=int(direct),current_direct_sufficient=int(m['direct_evidence_sufficient']),correct_proposal_present=int(m['correct_proposal_present']),proposal_insufficient=int(m['proposal']=='insufficient'),original_correct_proposal=int(base['metrics']['correct_proposal_present']),D_follows_proposal=int(sorted(set(o['D_output']['answer']))==sorted(set(m['proposal']))) if isinstance(m['proposal'],list) and o['D_output'] is not None and isinstance(o['D_output'].get('answer'),list) else 0,unverified_facts=m['unverified_visible_fact_count'],loss_delta=base['metrics']['joint_success_strict']-joint,loss_vs_no_e3=none_success-joint,token_saving=sum(base['edge_tokens'].values())-sum(o['edge_tokens'].values()),noop=int(o['audit']['noop']),failure_class=category))
 savecsv('sample_metrics.csv',sample);si={(r['world_id'],r['demand'],r['condition']):r for r in sample}
 metrics=[]
 for subset in ['all','direct_sufficient','direct_insufficient']:
  for d in [0,1]:
   for c in names:
    rs=[r for r in sample if r['condition']==c and r['demand']==d and (subset=='all' or r['direct_evidence_sufficient']==int(subset=='direct_sufficient'))]
    if not rs:continue
    metrics.append(dict(subset=subset,demand=d,condition=c,n=len(rs),**{k:mean(rs,k) for k in ['joint_success','joint_success_legacy','answer_accuracy','citation_support','insufficient','source_evidence_sufficient','correct_proposal_present','D_follows_proposal','loss_delta','loss_vs_no_e3','token_saving']},schema_parse_success=mean(rs,'parse_success'),noops=sum(r['noop'] for r in rs)))
 savecsv('condition_metrics.csv',metrics)
 contrasts=[];contrast_samples=[]
 comparisons=[('original','no_e3'),('swap_answer','original'),('swap_evidence','original'),('swap_both','original'),('original_without_answer','original'),('original_without_evidence','original'),('natural','original'),('natural','no_e3'),('natural_without_answer','natural'),('natural_without_evidence','natural'),('swap_without_answer','swap_both'),('swap_without_evidence','swap_both')]
 for changed,base in comparisons:
  cr=[]
  for w in worlds:
   for d in [0,1]:
    a=si[w,d,changed];b=si[w,d,base];cr.append(dict(world_id=w,demand=d,changed=changed,base=base,direct_sufficient=a['direct_evidence_sufficient'],loss_delta=b['joint_success']-a['joint_success'],answer_loss_delta=b['answer_accuracy']-a['answer_accuracy'],harm=int(b['joint_success']>a['joint_success']),benefit=int(b['joint_success']<a['joint_success'])))
  contrast_samples+=cr
  for subset in ['all','direct_sufficient']:
   for demand in ['all',0,1]:
    rr=[r for r in cr if (subset=='all' or r['direct_sufficient']) and (demand=='all' or r['demand']==demand)]
    if not rr:continue
    contrasts.append(dict(changed=changed,base=base,subset=subset,demand=demand,metric='joint_loss',**bootstrap(rr,'loss_delta'),harm=sum(r['harm'] for r in rr),benefit=sum(r['benefit'] for r in rr)))
 savecsv('paired_contrast_samples.csv',contrast_samples);savecsv('paired_contrasts.csv',contrasts)
 four=['original','original_without_evidence','drop_e5','drop_e3_evidence_and_e5'];pairs=[]
 for w in worlds:
  for d in [0,1]:
   os=[idx[w,d,c] for c in four]
   for metric in ['joint_success_strict','joint_success_legacy','answer_accuracy']:
    losses=[1-o['metrics'][metric] for o in os];pairs.append(dict(world_id=w,stratum=os[0]['stratum'],demand=d,metric=metric,L00=losses[0],L10=losses[1],L01=losses[2],L11=losses[3],J=losses[3]-losses[1]-losses[2]+losses[0],direct_sufficient=os[0]['metrics']['direct_evidence_sufficient'],original_proposal_correct=os[0]['metrics']['correct_proposal_present']))
 savecsv('four_cell_samples.csv',pairs);pairagg=[];diffs=[]
 for metric in ['joint_success_strict','joint_success_legacy','answer_accuracy']:
  for subset in ['all','direct_sufficient']:
   for d in [0,1]:
    rs=[r for r in pairs if r['metric']==metric and r['demand']==d and (subset=='all' or r['direct_sufficient'])];pairagg.append(dict(metric=metric,subset=subset,demand=d,**bootstrap(rs,'J'),**{k:mean(rs,k) for k in ['L00','L10','L01','L11']}))
   rr=[]
   for w in worlds:
    a=next(r for r in pairs if r['world_id']==w and r['metric']==metric and r['demand']==0);b=next(r for r in pairs if r['world_id']==w and r['metric']==metric and r['demand']==1)
    if subset=='direct_sufficient' and not a['direct_sufficient']:continue
    rr.append(dict(world_id=w,metric=metric,subset=subset,J_difference=b['J']-a['J']))
   diffs.append(dict(metric=metric,subset=subset,**bootstrap(rr,'J_difference')))
 savecsv('four_cell_summary.csv',pairagg);savecsv('demand_interaction_difference.csv',diffs)
 primary=[]
 for c,b in [('original','no_e3'),('swap_answer','original'),('swap_evidence','original')]:
  r=next(r for r in contrasts if r['changed']==c and r['base']==b and r['subset']=='all' and r['demand']=='all');primary.append(dict(test=c+'_vs_'+b,**{k:r[k] for k in ['estimate','ci_low','ci_high','p','n','worlds']}))
 r=next(r for r in diffs if r['metric']=='joint_success_strict' and r['subset']=='all');primary.append(dict(test='J_required_minus_optional',**{k:r[k] for k in ['estimate','ci_low','ci_high','p','n','worlds']}))
 prev=0
 for i,r in enumerate(sorted(primary,key=lambda r:r['p'])):prev=max(prev,min(1,r['p']*(len(primary)-i)));r['p_holm']=prev
 savecsv('primary_comparisons.csv',primary)
 # Same realized response cross-scored under optional/required rules to isolate mechanical scoring.
 cross=[]
 for w in worlds:
  for c in four:
   optional=idx[w,0,c];required=idx[w,1,c];a=optional['metrics'];b=required['metrics']
   cross.append(dict(world_id=w,condition=c,optional_answer_accuracy=a['answer_accuracy'],required_answer_accuracy=b['answer_accuracy'],optional_joint=a['joint_success_strict'],required_joint=b['joint_success_strict'],optional_response_scored_as_required=int(a['answer_accuracy'] and a['cited_visible_evidence_sufficient']),required_response_scored_as_optional=b['answer_accuracy'],same_D_output=optional['D_output']==required['D_output'],optional_insufficient=a['insufficient'],required_insufficient=b['insufficient']))
 savecsv('cross_scored_demands.csv',cross)
 crossagg=[]
 for c in four:
  rr=[r for r in cross if r['condition']==c];crossagg.append(dict(condition=c,n=len(rr),**{k:mean(rr,k) for k in rr[0] if k not in ['world_id','condition']}))
 savecsv('demand_behavior_vs_scoring.csv',crossagg)
 breakdown=[]
 for c in names:
  rr=[r for r in sample if r['condition']==c]
  for klass in sorted({r['failure_class'] for r in sample}):breakdown.append(dict(condition=c,failure_class=klass,n=sum(r['failure_class']==klass for r in rr),denominator=len(rr)))
 savecsv('failure_breakdown.csv',breakdown)
 # Natural perturbation and scripted perturbation manipulation checks use no D outcome to choose cases/conditions.
 checks=[]
 for u in up:
  w=u['world_id'];O=u['edges']['e3'];N=u['natural_e3'];g=gold[w+'-d0'];s=idx[w,0,'swap_both']['edges']['e3'];check=lambda p:isinstance(p.get('answer'),list) and sorted(set(p['answer']))==g['answer']
  checks.append(dict(world_id=w,stratum=u['stratum'],original_correct=check(O),natural_correct=check(N),swap_correct=check(s),original_evidence_count=len(O['evidence']),natural_evidence_count=len(N['evidence']),swap_evidence_count=len(s['evidence']),natural_payload_changed=O!=N,swap_noop=idx[w,0,'swap_both']['audit']['swap']['noop'],direct_sufficient=si[w,0,'original']['direct_evidence_sufficient']))
 savecsv('manipulation_checks.csv',checks)
 patterns={
  'original_interference':lambda r:r['condition']=='original' and r['failure_class']=='paired_e3_interference',
  'changed_conclusion_interference':lambda r:r['condition']=='swap_answer' and r['failure_class']=='paired_e3_interference',
  'changed_evidence_interference':lambda r:r['condition']=='swap_evidence' and r['failure_class']=='paired_e3_interference',
  'natural_interference':lambda r:r['condition']=='natural' and r['failure_class']=='paired_e3_interference',
  'remove_conclusion_rescue':lambda r:r['condition']=='natural_without_answer' and r['joint_success']>si[r['world_id'],r['demand'],'natural']['joint_success'],
  'remove_evidence_rescue':lambda r:r['condition']=='natural_without_evidence' and r['joint_success']>si[r['world_id'],r['demand'],'natural']['joint_success'],
  'adequate_but_no_e3_fails':lambda r:r['condition']=='no_e3' and r['direct_evidence_sufficient'] and not r['joint_success'],
  'redundant_paths_fail':lambda r:r['condition']=='drop_e3_evidence_and_e5' and r['demand']==1 and all(si[r['world_id'],1,c]['joint_success'] for c in four[:3]) and not r['joint_success'],
  'extraction_insufficient':lambda r:r['condition']=='original' and not r['direct_evidence_sufficient'],
  'no_effect':lambda r:r['condition']=='swap_both' and r['loss_delta']==0}
 cases=[]
 for name,predicate in patterns.items():
  selected=sorted([r for r in sample if predicate(r)],key=lambda r:(r['world_id'],r['demand'],r['condition']))[:1]
  if not selected:cases.append(dict(category=name,status='not observed'));continue
  r=selected[0];o=idx[r['world_id'],r['demand'],r['condition']];ref=idx[r['world_id'],r['demand'],'original'];none=idx[r['world_id'],r['demand'],'no_e3'];cases.append(dict(category=name,**r,question=o['question'],gold=o['gold_answer'],D=o['D_output'],reference_D=ref['D_output'],no_e3_D=none['D_output'],reference_edges=ref['edges'],modified_edges=o['edges'],source_witness=o['metrics']['source_witness'],nodes=o['nodes'],payload_hash=o['payload_hash']))
 jsonl(HERE/'results/cases.jsonl',cases)
 figures(metrics,contrasts,pairagg,crossagg)
 report(aud,metrics,contrasts,pairagg,diffs,primary,crossagg,checks,sample,cases)
 print('MECHANISM REPORT COMPLETE',flush=True)

def figures(metrics,contrasts,pairagg,crossagg):
 import matplotlib;matplotlib.use('Agg')
 import matplotlib.pyplot as plt
 conditions=['original','swap_answer','swap_evidence','swap_both','original_without_answer','original_without_evidence','no_e3','natural','natural_without_answer','natural_without_evidence']
 fig,ax=plt.subplots(figsize=(12,5));x=np.arange(len(conditions))
 for d in [0,1]:
  vals=[next(r['joint_success'] for r in metrics if r['subset']=='all' and r['demand']==d and r['condition']==c) for c in conditions];ax.bar(x+(d-.5)*.35,vals,width=.35,label=['Citations optional','Evidence required'][d])
 ax.set_xticks(x,conditions,rotation=35,ha='right');ax.set(ylabel='Joint success',ylim=(0,1.05),title='Receiver outcomes with unchanged direct evidence');ax.legend();fig.tight_layout();fig.savefig(HERE/'results/figures/e3_components.png',dpi=180);plt.close(fig)
 fig,axs=plt.subplots(1,2,figsize=(9,4))
 for ax,metric in zip(axs,['joint_success_strict','answer_accuracy']):
  for d in [0,1]:
   r=next(r for r in pairagg if r['metric']==metric and r['subset']=='all' and r['demand']==d);ax.plot(range(4),[r[k] for k in ['L00','L10','L01','L11']],marker='o',label=['optional','required'][d])
  ax.set_xticks(range(4),['00','10','01','11']);ax.set(ylabel='Loss',title=metric);ax.legend()
 fig.tight_layout();fig.savefig(HERE/'results/figures/e3_e5_four_cells.png',dpi=180);plt.close(fig)
 fig,ax=plt.subplots(figsize=(8,5));rr=[r for r in contrasts if r['subset']=='all' and r['demand']=='all'];y=np.arange(len(rr));ax.errorbar([r['estimate'] for r in rr],y,xerr=np.array([[r['estimate']-r['ci_low'] for r in rr],[r['ci_high']-r['estimate'] for r in rr]]),fmt='o');ax.axvline(0,color='grey',lw=1);ax.set_yticks(y,[r['changed']+' − '+r['base'] for r in rr]);ax.set(xlabel='Paired loss change (95% world-bootstrap CI)',title='e3 component contrasts');fig.tight_layout();fig.savefig(HERE/'results/figures/paired_effects.png',dpi=180);plt.close(fig)

def report(aud,metrics,contrasts,pairagg,diffs,primary,crossagg,checks,sample,cases):
 usage=read(HERE/'runs/budget_ledger.json');direct=sum(r['direct_sufficient'] for r in checks);base=[r for r in metrics if r['subset']=='all'];cond=lambda c,d:next(r for r in base if r['condition']==c and r['demand']==d)
 observed_original=sum(r['condition']=='original' and r['failure_class']=='paired_e3_interference' for r in sample);observed_nat=sum(r['condition']=='natural' and r['failure_class']=='paired_e3_interference' for r in sample);observed_swap_a=sum(r['condition']=='swap_answer' and r['failure_class']=='paired_e3_interference' for r in sample);observed_swap_e=sum(r['condition']=='swap_evidence' and r['failure_class']=='paired_e3_interference' for r in sample)
 p4=next(r for r in primary if r['test']=='J_required_minus_optional');answer_diff=next(r for r in diffs if r['metric']=='answer_accuracy' and r['subset']=='all');legacy_diff=next(r for r in diffs if r['metric']=='joint_success_legacy' and r['subset']=='all');prior=(HERE/'results/resource_accounting.json');acct=read(prior) if prior.exists() else None
 outcome='在本轮得到校正后的正向复现证据' if p4['ci_low']>0 and p4['p_holm']<.05 else '本轮没有获得校正后的正向复现证据'
 text=f'''# e3干扰与需求依赖：50个全新世界机制复验

状态：完成。保持Qwen3.5-4B与原角色提示、生成设置不变；50全新正式世界、100查询、1400条件，另4个独立debug世界。正式实际节点请求 {aud['formal_actual_calls']}；本轮总请求 {usage['requests']}，生成token {usage['generated_tokens']}，预算账本GPU时间 {usage['gpu_seconds']/3600:.4f} 小时。正式失败/截断 {aud['parse_failures']}/{aud['length_stops']}。最终Slurm资源账单见results/resource_accounting.json（若尚无该文件，上述时间为引擎账本而非最终调度账单）。

**先回答机制问题。** e4/e5实际输出在 {direct}/50 世界拥有程序验证的完整真实支持集合；两需求、所有e3诊断条件的直达证据hash一致，不用oracle补充漏抽。充分路径存在且no_e3成功、但带e3失败的配对实例：原始e3 {observed_original}，真实上游删键后的e3 {observed_nat}，仅替换结论 {observed_swap_a}，仅替换证据 {observed_swap_e}（查询条件计数，非独立世界数）。这些是消息干扰的个案证据，均值与不确定性见配对表；不能把所有D错误都归于e3。

**需求改变交互：{outcome}。** 严格joint loss的 J_required−J_optional={p4['estimate']:.4f}，95%世界聚类区间 [{p4['ci_low']:.4f},{p4['ci_high']:.4f}]，Holm校正p={p4['p_holm']:.4f}。以answer accuracy定义的差值为 {answer_diff['estimate']:.4f}，区间 [{answer_diff['ci_low']:.4f},{answer_diff['ci_high']:.4f}]；第一轮ID评分口径的差值为 {legacy_diff['estimate']:.4f}。必须同时看这三者与拒答变化，不能仅凭严格证据评分的主效果推断行为机制。

本轮没有训练预测器，也没有第二模型；判断范围仅是证据充分性和消息对固定接收者的干扰。第一轮预测特征未据本轮结果更新。

## 设计与处理语义

50个新世界分25唯一姓名、25同名实体，两侧各5记录。资料、答案、多个充分证据集合及计划在首个模型请求前冻结。A/B/C对同一基础问题只生成一次，D的问题只在是否必须给可核验证据上不同。这是有意隔离D需求，**不是**让四个角色都响应需求的端到端复刻。两个版本必须输出相同code答案；需求变化主要关乎验证责任，而非另一道答案不同的问题。

original是真实C输出。swap_*是受控消息修改：按C已见事实的原顺序选择首个不同于C原结论的code；证据取同一候选key的已有事实。没有gold驱动选错答案，也没有伪造事实或ID；可能是与问题无关的真实证据。自然干预natural则先删e1关联键，再实际重跑C，直达e4/e5不动。删除结论使用absent，区别于C主动输出insufficient；完全屏蔽e3时D连e3键都不收到。

受控swap结论实际正确 {sum(r['swap_correct'] for r in checks)}/50，原始C正确 {sum(r['original_correct'] for r in checks)}/50，natural C正确 {sum(r['natural_correct'] for r in checks)}/50；swap noop {sum(r['swap_noop'] for r in checks)}，natural payload改变 {sum(r['natural_payload_changed'] for r in checks)}/50。全部条件保留，不只挑成功污染或baseline成功的世界。

## e3分量对照（e4/e5未改）

{table([r for r in base if r['condition'] not in ['drop_e5','drop_e3_evidence_and_e5']],['demand','condition','n','joint_success','answer_accuracy','insufficient','source_evidence_sufficient','D_follows_proposal'])}

需求0=证据可选，需求1=证据必需。完整、直达证据充分/不充分子集分别在condition_metrics.csv，不能将充分子集替换全部世界主分母。

## 主要比较与配对效应

{table(primary,['test','n','worlds','estimate','ci_low','ci_high','p','p_holm'])}

前三项正值代表前者增加loss；最后一项正值代表证据必需时额外组合损失更大。5000次world聚类bootstrap，同世界两个需求及全部条件绑定。四项主要检验作Holm校正；其他对照和子集为探索性。均值为0或区间跨零不等于安全或非劣。

{table([r for r in contrasts if r['subset']=='all' and r['demand']=='all'],['changed','base','n','worlds','estimate','ci_low','ci_high','harm','benefit'])}

## e3/e5四格

00=original，10=只去e3证据但保留结论，01=去e5，11=两条证据路径同时去除。e4不变。

{table([r for r in pairagg if r['subset']=='all'],['metric','demand','n','worlds','L00','L10','L01','L11','estimate','ci_low','ci_high'])}

其中estimate=J。J为行为交互，不是互信息或普遍因果定律。各需求间配对J差见demand_interaction_difference.csv。

## 行为变化与评分变化分开

{table(crossagg,['condition','n','optional_answer_accuracy','required_answer_accuracy','optional_joint','required_joint','optional_response_scored_as_required','required_response_scored_as_optional','optional_insufficient','required_insufficient','same_D_output'])}

交叉评分不重新运行LLM：同一个回答按另一证据规则评分，可显示“输出相同但评价不同”的机械部分；不同问题下真实D答案/拒答变化才属于行为部分。它不是一个独立因果中介分解。

## 证据充分性与失败归因

逐条真实来源事实按完整六字段匹配，记录一个可用支持集合witness；多个合法集合均接受。严格joint要求D引用集合中实际可见且真实的事实，而非只命中gold ID。两种评分不同的样本数 {sum(r['joint_success']!=r['joint_success_legacy'] for r in sample)}/1400。不能把规则未找到witness当成不可恢复证明；正确proposal存在也不等于具备可核验证据。

{table([dict(category=k,n=v) for k,v in sorted(collections.Counter(r['failure_class'] for r in sample).items())],['category','n'])}

这些类别互斥，按当前可用证据及配对no_e3结果归类。`paired_e3_interference`仅指不改变直达路径、无e3能成功而带某e3失败的配对情形；并非总体平均有害的显著性声明。`sufficient_evidence_receiver_failure`包括无e3也失败的接收者使用困难。证据不充分但结论仍可见的情况单列，不自动叫信息丢失。A/B抽取不完整导致的direct_insufficient属于前置机制限制。

## 按事前规则选择的案例

{table(cases,['category','world_id','demand','condition','joint_success','source_evidence_sufficient','status'])}

完整问题、gold、D前后输出、no_e3输出、证据witness、边payload和节点keys见results/cases.jsonl；按类别字典序首例，未出现则明示，不挑有利故事。

## 图与可复现性

![e3分量](results/figures/e3_components.png)
![证据四格](results/figures/e3_e5_four_cells.png)
![配对差](results/figures/paired_effects.png)

底层CSV为condition_metrics.csv、four_cell_summary.csv、paired_contrasts.csv。执行输入输出保存在runs/formal，freeze.json与completion_audit.json验证版本与逐条件完整性。完整计划1400/1400；未重跑挑选条件、未动第一轮源码。实验只覆盖单模型、小型合成关联任务，不能保证复杂真实workflow同样表现。
'''
 (HERE/'REPORT.md').write_text(text);write(HERE/'STATUS.json',dict(status='complete',worlds=50,queries=100,conditions=1400,formal_actual_calls=aud['formal_actual_calls'],usage=usage,primary=primary));print('primary',primary,flush=True)

if __name__=='__main__':main()
