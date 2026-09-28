import collections, csv, json, time
import numpy as np
from scipy.stats import binomtest
from protocol_pilot.common import ROOT, canon, digest, read, rows, write, jsonl
from protocol_pilot.oracle import score
from run import HERE, NAMES, protocols, flatten, verify_freeze

ERRORS=['missing_project_source','missing_code_source','missing_both','cross_entity_mismatch','wrong_target_pair','unknown_source_id','unverified_visible_source','unrelated_source_id']
METRICS=['joint_success','answer_accuracy','correct_answer_incomplete','citation_complete','insufficient','parse_success','source_sufficient','direct_sufficient','e3_tokens','downstream_tokens','total_edge_tokens','D_input_tokens','D_output_tokens']

def savecsv(name,records):
    if not records:(HERE/'results'/name).write_text('');return
    keys=list(dict.fromkeys(k for r in records for k in r))
    with (HERE/'results'/name).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=keys,lineterminator='\n');writer.writeheader();writer.writerows(records)

def bootstrap(records,key):
    groups=collections.defaultdict(list)
    for r in records:groups[r['world_id']].append(r[key])
    if not groups:return dict(n=0,worlds=0,estimate=None,ci_low=None,ci_high=None)
    cfg=read(HERE/'config.json');sums=np.array([sum(v) for v in groups.values()]);ns=np.array([len(v) for v in groups.values()]);rng=np.random.default_rng(cfg['bootstrap_seed'])
    ids=rng.integers(0,len(groups),(cfg['bootstrap'],len(groups)));samples=sums[ids].sum(1)/ns[ids].sum(1);lo,hi=np.quantile(samples,[.025,.975])
    return dict(n=int(ns.sum()),worlds=len(groups),estimate=float(sums.sum()/ns.sum()),ci_low=float(lo),ci_high=float(hi))

def mean(rs,k):return float(np.mean([r[k] for r in rs])) if rs else None

def citation_metrics(q,g,output,es,records):
    truth={f['id']:f for f in records};authentic=set();direct=set();unverified=[]
    for e,p in es.items():
        for f in p['facts']+p['evidence']:
            if f.get('id') in truth and f==truth[f['id']]:
                authentic.add(f['id'])
                if e in ['e4','e5']:direct.add(f['id'])
            else:unverified.append(f)
    ids=set((output or {}).get('evidence_ids',[]));cited=ids&authentic
    sufficient=lambda x:any(set(s)<=x for s in g['sufficient_evidence_sets'])
    relevant=set().union(*(set(s) for s in g['sufficient_evidence_sets']))
    project_ids={i for i in relevant if truth[i]['kind']=='project'};code_ids={i for i in relevant if truth[i]['kind']=='code'}
    projects=[truth[i] for i in cited if truth[i]['kind']=='project'];codes=[truth[i] for i in cited if truth[i]['kind']=='code']
    pairs=[(p,c) for p in projects for c in codes if p['key'] is not None and p['key']==c['key']]
    missing_p=not bool(cited&project_ids);missing_c=not bool(cited&code_ids)
    return dict(citation_complete=int(sufficient(cited)),source_sufficient=int(sufficient(authentic)),direct_sufficient=int(sufficient(direct)),missing_project_source=int(missing_p),missing_code_source=int(missing_c),missing_both=int(missing_p and missing_c),cross_entity_mismatch=int(bool(projects and codes) and not pairs),wrong_target_pair=int(any(p['value']!=q['target'] for p,c in pairs)),unknown_source_id=int(bool(ids-truth.keys())),unverified_visible_source=int(bool((ids&truth.keys())-authentic)),unrelated_source_id=int(bool(cited-relevant)),unverified_fact_count=len(unverified),authentic_ids=sorted(authentic),cited_ids=sorted(ids),source_witness=next((s for s in g['sufficient_evidence_sets'] if set(s)<=authentic),None))

def audit(split):
    freeze=verify_freeze();run=HERE/'runs'/split;out=rows(run/'outcomes.jsonl');traces=rows(run/'traces.jsonl');up=rows(run/'upstream.jsonl');plan=[p for p in rows(HERE/'data/plan.jsonl') if p['split']==split]
    expected={(p['query_id'],p['condition']) for p in plan};actual={(o['query_id'],o['condition']) for o in out}
    assert len(out)==len(actual) and actual==expected, 'Incomplete/duplicate conditions; no complete report'
    nodes={t['cache_key']:t for t in traces};ui={u['world_id']:u for u in up};oi={(o['world_id'],o['demand'],o['condition']):o for o in out}
    for o in out:
        u=ui[o['world_id']];p=protocols(u['edges']['e3'])[o['condition']]
        expected_edges={e:u['edges'][e] for e in ['e4','e5']}
        if p is not None:expected_edges['e3']=p
        assert o['edges']==expected_edges and o['payload_hash']==digest(expected_edges)
        other=oi[o['world_id'],1-o['demand'],o['condition']];assert other['payload_hash']==o['payload_hash']
        for role in 'ABC':assert o['nodes'][role]==u['nodes'][role]
        d=nodes[o['nodes']['D']];visible=json.loads(d['visible_input'][1]['content'])
        assert visible==dict(question=o['question'],**expected_edges)
        assert d['dependency_hash']==o['D_dependency_hash']==digest(d['visible_input'])
        assert d['input_tokens']==o['D_input_tokens']
        assert o['code_hash']==freeze['execution_hash']
    for t in traces:
        assert t['code_hash']==freeze['execution_hash'] and t['model_hash']==freeze['model_hash']
        v=json.loads(t['visible_input'][1]['content']);role=t['role']
        assert set(v)==({'question','document'} if role in 'AB' else {'question','e1','e2'} if role=='C' else {'question','e4','e5'} if 'e3' not in v else {'question','e3','e4','e5'})
        assert t['time']>freeze['time']
    report=dict(passed=True,split=split,planned_conditions=len(plan),completed_conditions=len(out),coverage=len(out)/len(plan),worlds=len(up),queries=len(up)*2,actual_calls=len(traces),role_calls=dict(collections.Counter(t['role'] for t in traces)),parse_failures=sum(bool(t['parse_error']) for t in traces),length_stops=sum(t['finish_reason']=='length' for t in traces),max_input_tokens=max(t['input_tokens'] for t in traces),max_output_tokens=max(t['output_tokens'] for t in traces),first_request_time=min(t['time'] for t in traces),freeze_time=freeze['time'],execution_hash=freeze['execution_hash'],exact_flatten_equivalence=True,unchanged_direct_edges=True,no_hidden_context=True)
    write(HERE/'results'/f'{split}_audit.json',report);return report,out,up

def sample_rows(out,up):
    ws={w['world_id']:w for w in rows(HERE/'data/worlds.jsonl')};qs={q['query_id']:q for q in rows(HERE/'data/queries.jsonl')};gs={g['query_id']:g for g in rows(HERE/'data/gold.jsonl')};ui={u['world_id']:u for u in up};samples=[];details={}
    for o in out:
        q=qs[o['query_id']];g=gs[o['query_id']];w=ws[o['world_id']];es=dict(o['edges'])
        if o['condition']=='P3':es['e3']=flatten(es['e3'])
        cm=citation_metrics(q,g,o['D_output'],es,w['records']['A']+w['records']['B'])
        base=score(q,g,o['D_output'],o['status']=='parse_failure');answer=base['answer_accuracy'];joint=int(answer and (not q['require_evidence'] or cm['citation_complete']))
        cp=ui[o['world_id']]['edges']['e3'].get('answer');cc=int(isinstance(cp,list) and sorted(set(cp))==g['answer'])
        r={k:o[k] for k in ['world_id','query_id','demand','condition','stratum','seed']}
        r.update(C_correct=cc,joint_success=joint,joint_legacy=base['joint_success'],answer_accuracy=answer,correct_answer_incomplete=int(answer and not cm['citation_complete']),insufficient=base['insufficient'],parse_success=base['parse_success'],**{k:cm[k] for k in ['citation_complete','source_sufficient','direct_sufficient']+ERRORS},e3_tokens=o['edge_tokens'].get('e3',0),downstream_tokens=sum(o['edge_tokens'].values()),total_edge_tokens=sum(o['edge_tokens'].values())+sum(o['upstream_edge_tokens'].values()),D_input_tokens=o['D_input_tokens'],D_output_tokens=o['D_output_tokens'],sort_changed=int(o['audit']['sort_changed']),multi_record_groups=o['audit']['multi_record_groups'])
        samples.append(r);details[q['query_id'],o['condition']]=dict(metrics=r,citation_audit=cm,gold=g,D_output=o['D_output'],payload=o['edges'],payload_hash=o['payload_hash'],nodes=o['nodes'])
    return samples,details

def contrasts(samples):
    index={(r['world_id'],r['demand'],r['condition']):r for r in samples};worlds=sorted({r['world_id'] for r in samples});result=[];per=[]
    pairs=[('P3','P2'),('P1','P0'),('P2','P1'),('P3','P1'),('P2','P0'),('P3','P0'),('P3','P4')]
    strata=[('all',lambda r:True),('unique_names',lambda r:r['stratum']=='unique_names'),('shared_names',lambda r:r['stratum']=='shared_names'),('C_correct',lambda r:r['C_correct']==1),('C_incorrect',lambda r:r['C_correct']==0)]
    strata += [(f'{s}/C_{c}',lambda r,s=s,c=c:r['stratum']==s and r['C_correct']==c) for s in ['unique_names','shared_names'] for c in [0,1]]
    for a,b in pairs:
        for d in [0,1]:
            for w in worlds:
                x=index[w,d,a];y=index[w,d,b]
                for metric in ['joint_success','answer_accuracy','correct_answer_incomplete','citation_complete','e3_tokens','total_edge_tokens','D_input_tokens']:
                    per.append(dict(world_id=w,demand=d,stratum=x['stratum'],C_correct=x['C_correct'],changed=a,base=b,metric=metric,delta=x[metric]-y[metric],benefit=int(x[metric]>y[metric]),harm=int(x[metric]<y[metric])))
            for s,predicate in strata:
                if s!='all' and (a,b)!=('P3','P2'):continue
                for metric in ['joint_success','answer_accuracy','correct_answer_incomplete','citation_complete','e3_tokens','total_edge_tokens','D_input_tokens']:
                    rr=[r for r in per if r['changed']==a and r['base']==b and r['demand']==d and r['metric']==metric and predicate(r)]
                    info=bootstrap(rr,'delta');wins=sum(r['benefit'] for r in rr);losses=sum(r['harm'] for r in rr)
                    p=float(binomtest(wins,wins+losses,.5).pvalue) if metric in ['joint_success','answer_accuracy','correct_answer_incomplete','citation_complete'] and wins+losses else 1.0 if metric in ['joint_success','answer_accuracy','correct_answer_incomplete','citation_complete'] else None
                    result.append(dict(changed=a,base=b,demand=d,stratum=s,metric=metric,**info,increases=wins,decreases=losses,exact_mcnemar_p=p,primary=a=='P3' and b=='P2' and d==1 and s=='all' and metric=='joint_success'))
    savecsv('paired_samples.csv',per);savecsv('paired_comparisons.csv',result);return result

def aggregate(samples):
    result=[];errors=[]
    for d in [0,1]:
        for c in NAMES:
            rr=[r for r in samples if r['demand']==d and r['condition']==c];correct=sum(r['answer_accuracy'] for r in rr)
            result.append(dict(demand=d,condition=c,n=len(rr),**{k:mean(rr,k) for k in METRICS},correct_n=correct,correct_incomplete_n=sum(r['correct_answer_incomplete'] for r in rr),incomplete_given_correct=sum(r['correct_answer_incomplete'] for r in rr)/correct if correct else None))
            incomplete=[r for r in rr if not r['citation_complete']]
            for kind in ERRORS:
                errors.append(dict(demand=d,condition=c,error=kind,count=sum(r[kind] for r in rr),denominator=len(rr),rate=mean(rr,kind),among_incomplete_count=sum(r[kind] for r in incomplete),incomplete_denominator=len(incomplete)))
    savecsv('condition_metrics.csv',result);savecsv('citation_errors.csv',errors);return result,errors

def cases(samples,details):
    ii={(r['world_id'],r['condition']):r for r in samples if r['demand']==1};worlds=sorted({w for w,c in ii});out=[]
    def v(w,c,k='joint_success'):return ii[w,c][k]
    tests={
      'P3_rescues_P2':lambda w:v(w,'P3')>v(w,'P2'),
      'P3_harms_P2':lambda w:v(w,'P3')<v(w,'P2'),
      'P2_rescues_P1':lambda w:v(w,'P2')>v(w,'P1'),
      'P1_rescues_P0':lambda w:v(w,'P1')>v(w,'P0'),
      'P3_repairs_citation_only':lambda w:v(w,'P2','correct_answer_incomplete') and v(w,'P3'),
      'P3_answer_only_incomplete':lambda w:not v(w,'P2','answer_accuracy') and v(w,'P3','correct_answer_incomplete'),
      'P3_repairs_cross_entity_citation':lambda w:v(w,'P2','cross_entity_mismatch') and v(w,'P3'),
      'P4_beats_P3':lambda w:v(w,'P4')>v(w,'P3'),
      'all_success':lambda w:all(v(w,c) for c in NAMES),
      'all_failure':lambda w:not any(v(w,c) for c in NAMES)}
    for label,predicate in tests.items():
        w=next((w for w in worlds if predicate(w)),None)
        out.append(dict(category=label,status='observed' if w else 'not observed',world_id=w,protocols={c:details[w+'-d1',c] for c in NAMES} if w else {}))
    jsonl(HERE/'results/cases.jsonl',out);return out

def figures(metrics,errors,comparisons):
    import matplotlib;matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    rr=[r for r in metrics if r['demand']==1];x=np.arange(5)
    fig,ax=plt.subplots(figsize=(8,4))
    for i,(key,label) in enumerate([('answer_accuracy','Answer correct'),('joint_success','Joint success'),('correct_answer_incomplete','Correct, citations incomplete')]):ax.bar(x+(i-1)*.25,[r[key] for r in rr],.25,label=label)
    ax.set_xticks(x,NAMES);ax.set(ylabel='Fraction of all 100 required-evidence queries',ylim=(0,1),title='Evidence-required outcomes');ax.legend(fontsize=8);fig.tight_layout();fig.savefig(HERE/'results/figures/outcomes.png',dpi=180);plt.close(fig)
    fig,axs=plt.subplots(1,2,figsize=(10,4))
    for key in ['missing_project_source','missing_code_source','cross_entity_mismatch']:
        axs[0].plot(x,[next(r['rate'] for r in errors if r['demand']==1 and r['condition']==c and r['error']==key) for c in NAMES],marker='o',label=key)
    axs[0].set_xticks(x,NAMES);axs[0].set(ylabel='Fraction of all queries',title='Citation error indicators');axs[0].legend(fontsize=7)
    axs[1].bar(x,[r['e3_tokens'] for r in rr]);axs[1].set_xticks(x,NAMES);axs[1].set(ylabel='Mean serialized e3 tokens',title='Communication cost');fig.tight_layout();fig.savefig(HERE/'results/figures/errors_and_tokens.png',dpi=180);plt.close(fig)
    selected=[r for r in comparisons if r['changed']=='P3' and r['base']=='P2' and r['demand']==1 and r['metric']=='joint_success' and r['n']]
    fig,ax=plt.subplots(figsize=(8,5));y=np.arange(len(selected));ax.errorbar([r['estimate'] for r in selected],y,xerr=np.array([[r['estimate']-r['ci_low'] for r in selected],[r['ci_high']-r['estimate'] for r in selected]]),fmt='o');ax.axvline(0,color='gray');ax.set_yticks(y,[r['stratum']+' (n='+str(r['n'])+')' for r in selected]);ax.set(xlabel='P3 − P2 joint success (95% paired world CI)',title='Primary contrast and exploratory strata');fig.tight_layout();fig.savefig(HERE/'results/figures/paired_effects.png',dpi=180);plt.close(fig)

def table(rs,fields):
    def f(x):return 'N/A' if x is None else f'{x:.4f}' if isinstance(x,float) else str(x)
    return '| '+' | '.join(fields)+' |\n|'+'|'.join(['---']*len(fields))+'|\n'+'\n'.join('| '+' | '.join(f(r.get(k)) for k in fields)+' |' for r in rs)

def main(split='formal'):
    aud,out,up=audit(split);samples,details=sample_rows(out,up)
    if split=='smoke':
        gate=dict(passed=aud['parse_failures']==0 and aud['length_stops']==0,execution_hash=aud['execution_hash'],audit=aud,baseline_answer_accuracy=mean([r for r in samples if r['condition']=='P0'],'answer_accuracy'),baseline_required_joint=mean([r for r in samples if r['condition']=='P0' and r['demand']==1],'joint_success'),sort_changed_worlds=sum(protocols(u['edges']['e3'])['P1']!=protocols(u['edges']['e3'])['P2'] for u in up),multi_record_group_worlds=sum(any(len(g['records'])>1 for g in protocols(u['edges']['e3'])['P3']['evidence']) for u in up),time=time.time())
        write(HERE/'results/smoke_validation.json',gate);savecsv('smoke_metrics.csv',samples);print(json.dumps(gate,indent=2));return
    savecsv('sample_metrics.csv',samples);metrics,errors=aggregate(samples);comp=contrasts(samples);selected=cases(samples,details);figures(metrics,errors,comp)
    primary=next(r for r in comp if r['primary']);write(HERE/'results/primary.json',primary)
    required=[r for r in metrics if r['demand']==1];by={r['condition']:r for r in required};baseline=next(r for r in comp if r['changed']=='P3' and r['base']=='P0' and r['demand']==1 and r['stratum']=='all' and r['metric']=='joint_success')
    if primary['ci_low']>0 and baseline['estimate']>0:
        decision='P3相对P2有明确正向联合成功收益，且相对P0改善；有理由验证本具体分组协议的跨模型/真实文本可迁移性，尚不能宣称普遍可靠。'
    elif by['P2']['joint_success']>by['P1']['joint_success'] and by['P3']['joint_success']>by['P1']['joint_success']:
        decision='P2/P3相对P1均有正向点估计，但分组独立收益须以主区间为准；若跨零，则与顺序解释相容，不能声称等效或独立分组收益。'
    elif by['P3']['answer_accuracy']>by['P2']['answer_accuracy'] and by['P3']['joint_success']<=by['P2']['joint_success']:
        decision='分组仅改善答案点估计，没有改善联合成功；不能宣称核验可靠性提高。暂停当前分组格式路线，下一项应是独立的D核验提示能力对照。'
    else:
        decision='没有得到分组能修复联合成功的明确证据。暂停当前格式优化路线，下一项应是独立的D核验提示能力对照；不显著不等于等效或无害。'
    usage=read(HERE/'runs/budget_ledger.json');account=read(HERE/'results/resource_accounting.json') if (HERE/'results/resource_accounting.json').exists() else None
    elapsed=account['gpu_seconds'] if account else usage['gpu_seconds'];smoke=read(HERE/'results/smoke_validation.json')
    checks=[dict(world_id=u['world_id'],stratum=u['stratum'],C_correct=next(r['C_correct'] for r in samples if r['world_id']==u['world_id']),sort_changed=protocols(u['edges']['e3'])['P1']!=protocols(u['edges']['e3'])['P2'],evidence_count=len(u['edges']['e3']['evidence']),groups=len(protocols(u['edges']['e3'])['P3']['evidence']),multi_record_groups=sum(len(g['records'])>1 for g in protocols(u['edges']['e3'])['P3']['evidence'])) for u in up]
    savecsv('manipulation_checks.csv',checks)
    direct=sum(r['direct_sufficient'] for r in samples if r['condition']=='P0' and r['demand']==1)
    text=f'''# e3消息组织方式：100个全新世界的协议干预

已完成100世界、200查询、1000/1000条件；保持Qwen3.5-4B、D及其他角色提示、workflow不变。正式实际请求{aud['actual_calls']}，含4个debug世界共{usage['requests']}请求、{usage['generated_tokens']}生成token；单GPU累计{elapsed:.2f}秒（{'Slurm最终账单' if account else '引擎预算账本，待Slurm核对'}）。正式解析失败{aud['parse_failures']}、截断{aud['length_stops']}。所有样本保留。

**主要答案：** 证据必需时P3−P2联合成功率差为{primary['estimate']:+.3f}，95%世界配对区间[{primary['ci_low']:+.3f},{primary['ci_high']:+.3f}]；改善{primary['increases']}世界、损害{primary['decreases']}世界，精确双侧McNemar p={primary['exact_mcnemar_p']:.4f}。主分母100个世界，不筛基线成功或C正确。{decision}

## 五协议及受控范围

P0原消息；P1仅删结论；P2在P1上按entity key稳定排序平铺证据；P3使用P2完全相同的事实和展开顺序，加entity_key/records分组外层；P4完全屏蔽e3。P3每条事实仍保留原六字段和来源id，未增加或计算支持事实。support_links在P1/P2/P3一致。所有100世界均验证展开P3逐条等于P2，重复事实也保留。e4/e5在所有条件完全不变，两需求payload hash相同。

仅从原e3转换，不访问gold、问题或另一边；D提示及公共说明没有增加分组解读提示。P3同时增加JSON结构、重复key及token，因此检验的是此具体组织方式，不是排除一切表达因素的抽象关系效应。

50唯一姓名、50同名世界；每侧5条记录、有多个合法支持集合。新数据与前两轮实体key/name/project/code无交集。A/B/C每世界共享一次基础问题执行，只在D问题改变证据需求。同世界需求版本并非独立样本。

## 证据必需：全部100查询

{table(required,['condition','n','answer_accuracy','joint_success','correct_answer_incomplete','correct_n','correct_incomplete_n','incomplete_given_correct','citation_complete','insufficient'])}

correct_answer_incomplete分母是全部100题；incomplete_given_correct才以正确答案为分母。joint要求正确答案与实际可见、真实、完整来源集合；多个合法证据集合都认可。额外无关引用单报，不改变沿用的成功定义。

## 配对差与通信成本

{table([r for r in comp if r['stratum']=='all' and r['demand']==1 and r['metric'] in ['joint_success','answer_accuracy','correct_answer_incomplete']],['changed','base','metric','n','estimate','ci_low','ci_high','increases','decreases'])}

仅P3−P2的required joint为预指定主检验；其他差、端点、分层均探索性。5000次世界配对bootstrap，相同抽样种子，需求和条件绑定；正差对于correct_answer_incomplete代表变差。一个主要检验无需多重主要检验校正；不以次要显著性代替主要结论。

{table(required,['condition','e3_tokens','downstream_tokens','total_edge_tokens','D_input_tokens','D_output_tokens'])}

e3_tokens为实际tokenizer对线上序列化payload计数，downstream=e3/e4/e5，total_edge_tokens为五边之和，D_input_tokens为实际chat template输入。独立边token之和与完整prompt token不同，不混用。缓存节省推理请求，但通信比较按每次部署协议完整边通信计量，未靠删除事实匹配长度。

## 引用错误（可重叠标签）

{table([r for r in errors if r['demand']==1],['condition','error','count','denominator','among_incomplete_count','incomplete_denominator'])}

缺project/code指未引用可验证且支持目标答案的该类来源；跨实体不匹配指引用两类真实事实但无共同key，不推断模型内部意图；错误目标配对单列。未知ID与真实但未在消息中可验证的ID分开。多标签可以重叠，不能相加为总错误率。完整真实直达支持存在{direct}/100世界；其余世界亦保留主分析，未用oracle补抽取。

## 预指定辅助分层：P3−P2的required联合成功

{table([r for r in comp if r['changed']=='P3' and r['base']=='P2' and r['demand']==1 and r['metric']=='joint_success'],['stratum','n','estimate','ci_low','ci_high','increases','decreases'])}

原C正确{sum(r['C_correct'] for r in checks)}/100，P2实际重排{sum(r['sort_changed'] for r in checks)}/100，P3含至少一个多记录组{sum(r['multi_record_groups']>0 for r in checks)}/100。C正误只在离线分析定义，不能用于运行选择。没有可合并事实的世界也保留。

## 证据可选需求

{table([r for r in metrics if r['demand']==0],['condition','n','answer_accuracy','joint_success','correct_answer_incomplete','citation_complete','insufficient'])}

## 案例、审计与限制

{table(selected,['category','world_id','status'])}

cases.jsonl保存按冻结规则所取首例的五协议输入、输出、gold、来源审计、payload及节点hash；sample_metrics.csv包含全部1000样本。主结果并不只来自这些案例。

freeze.json锁定协议/数据/评分/提示；formal_audit.json验证每条真实D输入、需求payload一致、上游复用、e4/e5不变、P2/P3完全可逆、模型代码hash、全部条件覆盖。正式调用角色数：{aud['role_calls']}；最大实际输入/输出token：{aud['max_input_tokens']}/{aud['max_output_tokens']}。旧实验文件未修改。debug原始答案准确率{smoke['baseline_answer_accuracy']:.3f}，只用于格式/实现检查，不按测试调格式。

本实验单模型、100个合成关联世界，依赖C实际输出的有限证据；不保证真实长文本上复现。没有证明最小协议，也没有训练预测器。下一步按上面决策执行，本轮未追加格式消融、未改变D核验提示。

![答案与联合成功](results/figures/outcomes.png)
![引用错误及token](results/figures/errors_and_tokens.png)
![主差及探索性分层](results/figures/paired_effects.png)

底层数据：condition_metrics.csv、citation_errors.csv、paired_comparisons.csv。运行与重新统计命令见README.md。
'''
    (HERE/'REPORT.md').write_text(text)
    write(HERE/'STATUS.json',dict(status='complete',worlds=100,queries=200,conditions=1000,usage=usage,primary=primary,decision=decision,audit=aud));print('COMPLETE',json.dumps(primary),decision)

if __name__=='__main__':
    import sys
    main(sys.argv[1] if len(sys.argv)>1 else 'formal')
