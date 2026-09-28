import copy, random, sys, time, json, collections
from pathlib import Path
from protocol_pilot.common import ROOT, canon, digest, read, rows, write, jsonl, append, codehash
from protocol_pilot.generate import make_world, solve
from protocol_pilot.schemas import edge, cedge, EDGE, FACT
from protocol_pilot.agents import Engine, BudgetStop

HERE = Path(__file__).resolve().parent
NAMES = ['P0', 'P1', 'P2', 'P3', 'P4']
GROUP = {'type':'object','properties':{'entity_key':{'type':['string','null']},'records':{'type':'array','items':FACT}},'required':['entity_key','records'],'additionalProperties':False}
GROUPED = copy.deepcopy(EDGE)
GROUPED['properties']['evidence'] = {'type':'array','items':GROUP}

def execution_hash():
    return digest({'parent':codehash(), 'files':{n:digest((HERE/n).read_text()) for n in ['run.py','analyze.py','config.json']}})

def protocols(original):
    """Pure sender-payload transformation. No oracle, question, or other edges."""
    import jsonschema
    jsonschema.validate(original, EDGE)
    assert original['facts'] == [], 'Expected frozen C serializer facts=[]'
    p1 = copy.deepcopy(original)
    p1.pop('answer', None)
    p2 = copy.deepcopy(p1)
    p2['evidence'].sort(key=lambda f:(f['key'] is None, f['key'] or ''))
    p3 = copy.deepcopy(p2)
    groups = []
    for f in p2['evidence']:
        key = f['key']
        if key is not None and groups and groups[-1]['entity_key'] == key:
            groups[-1]['records'].append(copy.deepcopy(f))
        else:
            groups.append({'entity_key':key, 'records':[copy.deepcopy(f)]})
    p3['evidence'] = groups
    result = dict(P0=copy.deepcopy(original), P1=p1, P2=p2, P3=p3, P4=None)
    for name,p in result.items():
        if p is not None:jsonschema.validate(p, GROUPED if name=='P3' else EDGE)
    assert flatten(p3) == p2
    assert collections.Counter(map(canon,p1['evidence'])) == collections.Counter(map(canon,p2['evidence']))
    return result

def flatten(grouped):
    p = copy.deepcopy(grouped)
    p['evidence'] = [f for group in p['evidence'] for f in group['records']]
    return p

def document(fs):
    return '\n'.join(f"Source {f['id']}: {f['name']} (entity key {f['key']}) has {f['kind']} {f['value']}" + (f" valid only in year {f['qualifier']}" if f['qualifier'] else '') + '.' for f in fs)

def symbols(worlds):
    return {f[k] for w in worlds for fs in w['records'].values() for f in fs for k in ['key','name','value'] if f[k] not in ['archive','yes','no']}

def prepare():
    assert not (HERE/'freeze.json').exists(), 'Frozen experiment cannot be regenerated'
    cfg=read(HERE/'config.json'); ws=[]; qs=[]; gs=[]; plan=[]
    previous=[ROOT/'data/worlds.jsonl', ROOT/'experiments/e3_mechanism_v1/data/worlds.jsonl']
    old=symbols([w for path in previous for w in rows(path)])
    for split,n,offset in [('formal',cfg['worlds'],0), ('smoke',cfg['smoke_worlds'],10000)]:
        for i in range(n):
            seed=cfg['seed']+offset+i
            w,qq,gg=make_world(random.Random(seed),'redundant_evidence',i,'organization-'+split)
            stratum='unique_names' if i%2==0 else 'shared_names'
            if stratum=='shared_names':
                name=w['records']['A'][0]['name']
                for fs in w['records'].values():
                    for f in fs:f['name']=name
            assert not symbols([w])&old
            assert not symbols([w])&symbols(ws)
            w.update(split=split,seed=seed,stratum=stratum,documents={side:document(fs) for side,fs in w['records'].items()})
            w['upstream_question']=qq[0]['question'].replace(' Source citations are optional.','')
            for q,g in zip(qq,gg):
                q.update(split=split,seed=seed,stratum=stratum)
                g.update(world_id=w['world_id'],split=split,stratum=stratum)
                assert solve(q,w['records']['A']+w['records']['B'])==g['answer']
                plan.extend({k:q[k] for k in ['world_id','query_id','split','demand','seed','stratum']}|{'condition':c} for c in NAMES)
            ws.append(w);qs.extend(qq);gs.extend(gg)
    for name,items in [('worlds',ws),('queries',qs),('gold',gs),('plan',plan)]:jsonl(HERE/'data'/f'{name}.jsonl',items)
    frozen=list((HERE/'data').glob('*.jsonl'))+[HERE/'SPEC.md',HERE/'config.json',ROOT/'configs/pilot.yaml',ROOT/'configs/model_identity.json']+list((ROOT/'prompts').glob('*.txt'))
    write(HERE/'freeze.json',dict(time=time.time(),execution_hash=execution_hash(),parent_execution_hash=codehash(),model_hash=digest(read(ROOT/'configs/model_identity.json')),files={str(p.relative_to(ROOT)):digest(p.read_text()) for p in frozen},previous_data_hashes={str(p.relative_to(ROOT)):digest(p.read_text()) for p in previous},formal_worlds=100,formal_conditions=1000,request_upper_bound=1352))
    print('FROZEN',len(ws),'worlds including smoke;',len(plan),'conditions')

def verify_freeze():
    f=read(HERE/'freeze.json');assert f['execution_hash']==execution_hash()
    for path,h in f['files'].items():assert digest((ROOT/path).read_text())==h,path
    return f

def validate():
    freeze=verify_freeze();ws=rows(HERE/'data/worlds.jsonl');qs=rows(HERE/'data/queries.jsonl');gs={g['query_id']:g for g in rows(HERE/'data/gold.jsonl')};plan=rows(HERE/'data/plan.jsonl')
    assert len(ws)==104 and len(qs)==208 and len(plan)==1040
    assert len({(p['query_id'],p['condition']) for p in plan})==1040
    assert collections.Counter(w['stratum'] for w in ws if w['split']=='formal')=={'unique_names':50,'shared_names':50}
    for w in ws:
        pair=[q for q in qs if q['world_id']==w['world_id']];assert len(pair)==2
        assert gs[pair[0]['query_id']]['answer']==gs[pair[1]['query_id']]['answer']
        fs=w['records']['A']+w['records']['B']
        for q in pair:
            g=gs[q['query_id']];assert solve(q,fs)==g['answer'] and len(g['sufficient_evidence_sets'])>=2
            for support in g['sufficient_evidence_sets']:assert solve(q,[f for f in fs if f['id'] in support])==g['answer']
        source=dict(answer=['sender-proposal'],facts=[],evidence=list(reversed(fs))+fs[:1],support_links=[{'id':'not-a-real-ID','supports':'answer'}])
        before=canon(source);p=protocols(source);assert canon(source)==before
        assert flatten(p['P3'])==p['P2'];assert p['P0']==source and p['P4'] is None
        assert p['P1']['evidence']==source['evidence'] and 'answer' not in p['P1']
        assert p['P2']['support_links']==p['P3']['support_links']==source['support_links']
    nulls=copy.deepcopy(source)
    for f in nulls['evidence']:f['key']=None
    assert len(protocols(nulls)['P3']['evidence'])==len(nulls['evidence'])
    empty=dict(answer='insufficient',facts=[],evidence=[],support_links=[])
    assert protocols(empty)['P3']['evidence']==[]
    result=dict(passed=True,worlds=104,formal_worlds=100,formal_conditions=1000,checks=['world separation','oracle and alternative support sets','stable order and exact multiset','duplicate preservation','null singleton groups','empty evidence','no input mutation','no added facts or IDs','no answer in P1/P2/P3'],execution_hash=freeze['execution_hash'])
    write(HERE/'results/cpu_validation.json',result);print('CPU VALIDATED',result['checks'])

class OrganizationEngine(Engine):
    def __init__(self,run):
        super().__init__(run)
        cfg=read(HERE/'config.json');self.cfg.update({k:cfg[k] for k in ['max_requests','max_generated_tokens','max_gpu_seconds']})
        self.code=execution_hash();self.usagepath=HERE/'runs/budget_ledger.json'
        self.usage=read(self.usagepath) if self.usagepath.exists() else dict(requests=0,generated_tokens=0,gpu_seconds=0)
        self.base_seconds=self.usage['gpu_seconds']

def request(w,question,role,visible,condition,query_id=None,demand='shared'):
    return dict(world_id=w['world_id'],query_id=query_id or w['world_id']+'-shared',split=w['split'],demand=demand,condition=condition,role=role,visible=canon({'question':question,**visible}))

def execute(split):
    freeze=verify_freeze();run=HERE/'runs'/split
    if split=='formal':
        gate=read(HERE/'results/smoke_validation.json');assert gate['passed'] and gate['execution_hash']==freeze['execution_hash']
        assert (HERE/'BUDGET_ESTIMATE.md').exists()
    engine=OrganizationEngine(run)
    ws=[w for w in rows(HERE/'data/worlds.jsonl') if w['split']==split]
    qs={q['query_id']:q for q in rows(HERE/'data/queries.jsonl')}
    # Execution never loads gold. Evaluation and gold-defined strata live in analyze.py only.
    done={(o['query_id'],o['condition']):o for o in rows(run/'outcomes.jsonl')}
    up={u['world_id']:u for u in rows(run/'upstream.jsonl')}
    manifest=dict(split=split,freeze=freeze,started=time.time(),planned_worlds=len(ws),planned_conditions=10*len(ws))
    if not (run/'manifest.json').exists():write(run/'manifest.json',manifest)
    else:append(run/'resume_events.jsonl',manifest)
    try:
        pending=[w for w in ws if w['world_id'] not in up]
        for offset in range(0,len(pending),16):
            batch=pending[offset:offset+16]
            ab=engine.generate([request(w,w['upstream_question'],role,{'document':w['documents'][role]},'shared_upstream') for w in batch for role in 'AB'])
            states=[]
            for i,w in enumerate(batch):
                a,b=ab[2*i:2*i+2];af=(a['parsed'] or {}).get('facts',[]);bf=(b['parsed'] or {}).get('facts',[])
                es={'e1':edge(af),'e2':edge(bf),'e4':edge(af,'evidence'),'e5':edge(bf,'evidence')};states.append((w,a,b,es))
            cs=engine.generate([request(w,w['upstream_question'],'C',{e:es[e] for e in ['e1','e2']},'shared_upstream') for w,a,b,es in states])
            for (w,a,b,es),c in zip(states,cs):
                es['e3']=cedge(c['parsed'] or {},es)
                u=dict(world_id=w['world_id'],split=split,seed=w['seed'],stratum=w['stratum'],question=w['upstream_question'],edges=es,nodes={r:t['cache_key'] for r,t in [('A',a),('B',b),('C',c)]},parse_errors={r:t['parse_error'] for r,t in [('A',a),('B',b),('C',c)]},model_hash=engine.modelhash,code_hash=engine.code,time=time.time())
                append(run/'upstream.jsonl',u);up[w['world_id']]=u
        for w in ws:
            u=up[w['world_id']];ps=protocols(u['edges']['e3']);pending=[]
            for demand in [0,1]:
                q=qs[w['world_id']+f'-d{demand}']
                for cond in NAMES:
                    if (q['query_id'],cond) in done:continue
                    es={e:copy.deepcopy(u['edges'][e]) for e in ['e4','e5']}
                    if ps[cond] is not None:es['e3']=ps[cond]
                    pending.append((q,cond,es))
            ds=engine.generate([request(w,q['question'],'D',es,cond,q['query_id'],q['demand']) for q,cond,es in pending])
            for (q,cond,es),d in zip(pending,ds):
                audit=dict(transform_input_hash=digest(u['edges']['e3']),P2_P3_unflattened_equal=flatten(ps['P3'])==ps['P2'],fact_multiset_hash=digest(sorted(map(canon,ps['P2']['evidence']))),ordered_fact_hash=digest(ps['P2']['evidence']),sort_changed=ps['P1']!=ps['P2'],group_count=len(ps['P3']['evidence']),multi_record_groups=sum(len(g['records'])>1 for g in ps['P3']['evidence']),noop_vs_P0=ps[cond]==ps['P0'],direct_hashes={e:digest(es[e]) for e in ['e4','e5']})
                item={k:q[k] for k in ['world_id','query_id','split','demand','seed','stratum']}
                item.update(condition=cond,question=q['question'],edges=es,payload_hash=digest(es),edge_hashes={e:digest(p) for e,p in es.items()},serialized_payloads={e:canon(p) for e,p in es.items()},edge_tokens={e:engine.count(p) for e,p in es.items()},upstream_edge_tokens={e:engine.count(u['edges'][e]) for e in ['e1','e2']},nodes=dict(u['nodes'],D=d['cache_key']),D_dependency_hash=d['dependency_hash'],D_output=d['parsed'],D_input_tokens=d['input_tokens'],D_output_tokens=d['output_tokens'],D_seconds=d['seconds'],status='parse_failure' if d['parse_error'] else 'completed',audit=audit,upstream_parse_errors=u['parse_errors'],code_hash=engine.code,model_hash=engine.modelhash,time=time.time())
                append(run/'outcomes.jsonl',item);append(run/'intervention_audit.jsonl',{k:item[k] for k in ['world_id','query_id','split','demand','condition','seed','audit','payload_hash']});done[(q['query_id'],cond)]=item
            print('WORLD COMPLETE',w['world_id'],len(done),flush=True)
        engine.save_usage();write(run/'completed.json',dict(time=time.time(),planned=10*len(ws),completed=len(done),worlds=len(ws),queries=2*len(ws),usage=engine.usage,execution_hash=engine.code))
    except BudgetStop as exc:
        write(run/'PAUSED.json',dict(time=time.time(),reason=str(exc),completed=len(done)));raise
    except Exception as exc:
        append(run/'failures.jsonl',dict(time=time.time(),status='infrastructure_or_implementation_error',error=repr(exc),code_hash=engine.code));raise
    finally:engine.save_usage()

if __name__=='__main__':
    cmd=sys.argv[1]
    if cmd=='prepare':prepare()
    elif cmd=='validate':validate()
    elif cmd=='run':execute(sys.argv[2])
    elif cmd=='analyze':
        from analyze import main
        main(sys.argv[2] if len(sys.argv)>2 else 'formal')
