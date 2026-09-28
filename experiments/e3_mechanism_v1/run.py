import sys,time,random,copy,os,itertools,hashlib
from pathlib import Path
from protocol_pilot.common import ROOT,canon,digest,read,rows,write,jsonl,append,codehash
from protocol_pilot.generate import make_world,solve
from protocol_pilot.schemas import edge,cedge,validate_edges
from protocol_pilot.protocols import single
from protocol_pilot.oracle import score
from protocol_pilot.agents import Engine,BudgetStop
HERE=Path(__file__).resolve().parent
NAMES=['original','swap_answer','swap_evidence','swap_both','original_without_answer','original_without_evidence','swap_without_answer','swap_without_evidence','no_e3','natural','natural_without_answer','natural_without_evidence','drop_e5','drop_e3_evidence_and_e5']
def execution_hash():return digest({'parent':codehash(),'run':digest(Path(__file__).read_text()),'analysis':digest((HERE/'analyze.py').read_text()),'config':read(HERE/'config.json')})
def document(fs):return '\n'.join(f"Source {f['id']}: {f['name']} (entity key {f['key']}) has {f['kind']} {f['value']}"+(f" valid only in year {f['qualifier']}" if f['qualifier'] else '')+'.' for f in fs)
def prepare():
 assert not (HERE/'freeze.json').exists(),'Already frozen; do not regenerate'
 cfg=read(HERE/'config.json');ws=[];qs=[];gs=[];plan=[]
 old=rows(ROOT/'data/worlds.jsonl');old_symbols={f[k] for w in old for fs in w['records'].values() for f in fs for k in ['key','name','value'] if f[k] not in ['archive','yes','no']}
 for split,n,offset in [('formal',cfg['worlds'],0),('smoke',cfg['smoke_worlds'],10000)]:
  for i in range(n):
   seed=cfg['seed']+offset+i;w,q,g=make_world(random.Random(seed),'redundant_evidence',i,'mechanism-'+split)
   stratum='unique_names' if i%2==0 else 'shared_names'
   if stratum=='shared_names':
    name=w['records']['A'][0]['name']
    for fs in w['records'].values():
     for f in fs:f['name']=name
   w.update(split=split,seed=seed,stratum=stratum,documents={k:document(fs) for k,fs in w['records'].items()})
   syms={f[k] for fs in w['records'].values() for f in fs for k in ['key','name','value']};assert not syms&old_symbols,'Generate a reviewed new seed if symbols collide; never silently reuse'
   w['upstream_question']=q[0]['question'].replace(' Source citations are optional.','')
   for item,gold in zip(q,g):
    item.update(split=split,seed=seed,stratum=stratum)
    gold.update(world_id=w['world_id'],split=split,stratum=stratum)
    assert solve(item,w['records']['A']+w['records']['B'])==gold['answer']
    for cond in NAMES:plan.append({k:item[k] for k in ['world_id','query_id','split','demand','seed','stratum']}|{'condition':cond})
   ws.append(w);qs+=q;gs+=g
 for name,items in [('worlds',ws),('queries',qs),('gold',gs),('plan',plan)]:jsonl(HERE/'data'/f'{name}.jsonl',items)
 write(HERE/'freeze.json',dict(time=time.time(),execution_hash=execution_hash(),parent_execution_hash=codehash(),model_hash=digest(read(ROOT/'configs/model_identity.json')),files={str(p.relative_to(ROOT)):digest(p.read_text()) for p in list((HERE/'data').glob('*.jsonl'))+[HERE/'SPEC.md',HERE/'config.json',ROOT/'configs/pilot.yaml']+list((ROOT/'prompts').glob('*.txt'))},formal_conditions=cfg['worlds']*2*len(NAMES),request_upper_bound=(cfg['worlds']+cfg['smoke_worlds'])*(4+2*len(NAMES)),question_only_demand_change=True))
 print('FROZEN',len(ws),'worlds including debug;',len(plan),'conditions including debug')

def no_answer(p):
 p=copy.deepcopy(p);p.pop('answer',None);return p
def no_evidence(p):
 p=copy.deepcopy(p);p['facts']=[];p['evidence']=[];p['support_links']=[];return p
def swapped(original,upstream):
 # Signature deliberately excludes gold, question metadata, D output, and the other downstream edges.
 upstream={e:upstream[e] for e in ['e1','e2']}
 fs=[f for e in ['e1','e2'] for f in upstream[e]['facts']]
 answer=original.get('answer',[]);current=set(answer) if isinstance(answer,list) else set()
 candidate=next((f for f in fs if f.get('kind')=='code' and f.get('value') and f['value'] not in current and f.get('key')),None)
 if candidate is None:return copy.deepcopy(original),dict(noop=True,rule='first visible code not in original proposal')
 evidence=[copy.deepcopy(f) for f in fs if f.get('key')==candidate['key']]
 return dict(answer=[candidate['value']],facts=[],evidence=evidence,support_links=[{'id':f['id'],'supports':'answer'} for f in evidence]),dict(noop=False,rule='first visible code not in original proposal',selected_source_id=candidate['id'],input_hash=digest(upstream))
def conditions(base,natural):
 O=base['e3'];S,audit=swapped(O,{e:base[e] for e in ['e1','e2']})
 answer_swap=copy.deepcopy(O);answer_swap['answer']=S['answer']
 evidence_swap=copy.deepcopy(S);evidence_swap['answer']=O['answer']
 variants={'original':O,'swap_answer':answer_swap,'swap_evidence':evidence_swap,'swap_both':S,'original_without_answer':no_answer(O),'original_without_evidence':no_evidence(O),'swap_without_answer':no_answer(S),'swap_without_evidence':no_evidence(S),'no_e3':None,'natural':natural,'natural_without_answer':no_answer(natural),'natural_without_evidence':no_evidence(natural),'drop_e5':O,'drop_e3_evidence_and_e5':no_evidence(O)}
 result={}
 for name,p in variants.items():
  es={'e4':copy.deepcopy(base['e4']),'e5':copy.deepcopy(base['e5'])}
  if p is not None:es['e3']=copy.deepcopy(p)
  if name in ['drop_e5','drop_e3_evidence_and_e5']:es['e5']=edge([],'evidence')
  validate_edges(es)
  if name not in ['drop_e5','drop_e3_evidence_and_e5']:assert es['e4']==base['e4'] and es['e5']==base['e5']
  result[name]=(es,dict(swap=audit if name.startswith('swap') else None,noop=es=={e:base[e] for e in ['e3','e4','e5']},direct_hashes={e:digest(es[e]) for e in ['e4','e5']},upstream_recomputed=name.startswith('natural')))
 return result

def source_proof(g,es,records):
 truth={f['id']:f for f in records};exact={};unverified=[]
 for edge_name,p in es.items():
  for f in p.get('facts',[])+p.get('evidence',[]):
   if f.get('id') in truth and f==truth[f['id']]:exact[f['id']]=f
   else:unverified.append({'edge':edge_name,'fact':f})
 witness=next((s for s in g['sufficient_evidence_sets'] if set(s)<=exact.keys()),None)
 return dict(sufficient=witness is not None,witness=witness,authentic_ids=sorted(exact),unverified_facts=unverified)
def score_receiver(q,g,d,es,records):
 legacy=score(q,g,d['parsed'],d['parse_error']);proof=source_proof(g,es,records);direct=source_proof(g,{e:es[e] for e in ['e4','e5']},records)
 ids=set((d['parsed'] or {}).get('evidence_ids',[]));authentic=set(proof['authentic_ids']);cited_sufficient=any(set(s)<=ids&authentic for s in g['sufficient_evidence_sets'])
 strict=int(legacy['answer_accuracy'] and (not q['require_evidence'] or cited_sufficient));proposal=es.get('e3',{}).get('answer');correct_proposal=isinstance(proposal,list) and sorted(set(proposal))==g['answer']
 return dict(**legacy,joint_success_legacy=legacy['joint_success'],joint_success_strict=strict,cited_visible_evidence_sufficient=cited_sufficient,source_evidence_sufficient=proof['sufficient'],direct_evidence_sufficient=direct['sufficient'],source_witness=proof['witness'],direct_witness=direct['witness'],authentic_visible_ids=proof['authentic_ids'],unverified_visible_fact_count=len(proof['unverified_facts']),correct_proposal_present=correct_proposal,proposal=proposal)
class MechanismEngine(Engine):
 def __init__(self,run):
  super().__init__(run)
  cfg=read(HERE/'config.json');self.cfg.update({k:cfg[k] for k in ['max_requests','max_generated_tokens','max_gpu_seconds']})
  self.code=execution_hash();self.usagepath=HERE/'runs/budget_ledger.json';self.usage=read(self.usagepath) if self.usagepath.exists() else dict(requests=0,generated_tokens=0,gpu_seconds=0);self.base_seconds=self.usage['gpu_seconds']

def request(w,question,role,visible,condition,query_id=None,demand='shared'):
 return dict(world_id=w['world_id'],query_id=query_id or w['world_id']+'-shared',split=w['split'],demand=demand,condition=condition,role=role,visible=canon({'question':question,**visible}))
def verify_freeze():
 f=read(HERE/'freeze.json');assert f['execution_hash']==execution_hash()
 for path,h in f['files'].items():assert digest((ROOT/path).read_text())==h,path
 return f

def execute(split):
 freeze=verify_freeze();run=HERE/'runs'/split;engine=MechanismEngine(run)
 ws=[w for w in rows(HERE/'data/worlds.jsonl') if w['split']==split];qs={q['query_id']:q for q in rows(HERE/'data/queries.jsonl')};gs={g['query_id']:g for g in rows(HERE/'data/gold.jsonl')}
 done={(o['query_id'],o['condition']):o for o in rows(run/'outcomes.jsonl')};up={x['world_id']:x for x in rows(run/'upstream.jsonl')}
 if split=='formal':
  smoke=read(HERE/'runs/smoke/completed.json');assert smoke['parse_success']>=.95,'Infrastructure/format gate failed; no changing prompt based on formal results'
 write(run/'manifest.json',dict(split=split,freeze=freeze,started=time.time(),planned_worlds=len(ws),planned_conditions=len(ws)*2*len(NAMES)))
 try:
  pending=[w for w in ws if w['world_id'] not in up]
  for offset in range(0,len(pending),16):
   batch=pending[offset:offset+16];requests=[]
   for w in batch:
    for role in 'AB':requests.append(request(w,w['upstream_question'],role,{'document':w['documents'][role]},'shared_upstream'))
   ab=engine.generate(requests);states=[]
   for i,w in enumerate(batch):
    a,b=ab[2*i:2*i+2];af=(a['parsed'] or {}).get('facts',[]);bf=(b['parsed'] or {}).get('facts',[])
    es={'e1':edge(af),'e2':edge(bf),'e4':edge(af,'evidence'),'e5':edge(bf,'evidence')};states.append((w,a,b,es))
   cr=[]
   for w,a,b,es in states:
    cr.append(request(w,w['upstream_question'],'C',{k:es[k] for k in ['e1','e2']},'shared_upstream'))
    cr.append(request(w,w['upstream_question'],'C',{'e1':single(es['e1'],'jk1'),'e2':es['e2']},'natural_drop_join_key_e1'))
   cs=engine.generate(cr)
   for i,(w,a,b,es) in enumerate(states):
    c,n=cs[2*i:2*i+2];es['e3']=cedge(c['parsed'] or {},es);nes={'e1':single(es['e1'],'jk1'),'e2':es['e2']};natural=cedge(n['parsed'] or {},nes)
    item=dict(world_id=w['world_id'],split=split,seed=w['seed'],stratum=w['stratum'],question=w['upstream_question'],edges=es,natural_e3=natural,natural_C_inputs=nes,nodes={'A':a['cache_key'],'B':b['cache_key'],'C':c['cache_key'],'C_natural':n['cache_key']},parse_errors={r:t['parse_error'] for r,t in [('A',a),('B',b),('C',c),('C_natural',n)]},model_hash=engine.modelhash,code_hash=engine.code,time=time.time());append(run/'upstream.jsonl',item);up[w['world_id']]=item
  for w in ws:
   state=up[w['world_id']];variants=conditions(state['edges'],state['natural_e3']);pending=[]
   for demand in [0,1]:
    qid=w['world_id']+f'-d{demand}';q=qs[qid]
    for cond in NAMES:
     if (qid,cond) not in done:
      es,audit=variants[cond];pending.append((q,cond,es,audit))
   outputs=engine.generate([request(w,q['question'],'D',es,cond,q['query_id'],q['demand']) for q,cond,es,audit in pending])
   for (q,cond,es,audit),d in zip(pending,outputs):
    g=gs[q['query_id']];metrics=score_receiver(q,g,d,es,w['records']['A']+w['records']['B']);nodekeys={r:k for r,k in state['nodes'].items() if r!='C_natural'}
    if cond.startswith('natural'):nodekeys['C']=state['nodes']['C_natural']
    if cond=='no_e3':nodekeys.pop('C')
    nodekeys['D']=d['cache_key']
    item={k:q[k] for k in ['world_id','query_id','split','demand','seed','stratum']};item.update(condition=cond,question=q['question'],edges=es,payload_hash=digest(es),edge_hashes={e:digest(p) for e,p in es.items()},serialized_payloads={e:canon(p) for e,p in es.items()},edge_tokens={e:engine.count(p) for e,p in es.items()},D_dependency_hash=d['dependency_hash'],nodes=nodekeys,metrics=metrics,audit=audit,gold_answer=g['answer'],D_output=d['parsed'],status='parse_failure' if d['parse_error'] else 'completed',upstream_parse_errors=state['parse_errors'],code_hash=engine.code,model_hash=engine.modelhash,time=time.time())
    append(run/'outcomes.jsonl',item);append(run/'intervention_audit.jsonl',{k:item[k] for k in ['world_id','query_id','split','demand','condition','seed','audit','payload_hash']});done[(q['query_id'],cond)]=item
   print('WORLD COMPLETE',w['world_id'],len(done),flush=True)
  engine.save_usage();allout=list(done.values());write(run/'completed.json',dict(time=time.time(),planned=len(ws)*2*len(NAMES),completed=len(done),worlds=len(ws),queries=len(ws)*2,parse_success=sum(o['metrics']['parse_success'] for o in allout)/len(allout),original_accuracy=sum(o['metrics']['answer_accuracy'] for o in allout if o['condition']=='original')/(2*len(ws)),usage=engine.usage,code_hash=engine.code))
 except BudgetStop as exc:write(run/'PAUSED.json',dict(time=time.time(),reason=str(exc),completed=len(done)));raise
 except Exception as exc:append(run/'failures.jsonl',dict(time=time.time(),status='infrastructure_or_implementation_error',error=repr(exc),code_hash=engine.code));raise
 finally:engine.save_usage()

def validate():
 f=verify_freeze();ws=rows(HERE/'data/worlds.jsonl');qs=rows(HERE/'data/queries.jsonl');gs={g['query_id']:g for g in rows(HERE/'data/gold.jsonl')};wd={w['world_id']:w for w in ws};p=rows(HERE/'data/plan.jsonl');assert len(p)==1512
 for w in ws:
  qpair=[q for q in qs if q['world_id']==w['world_id']];assert len(qpair)==2 and qpair[0]['question'].split(' Source citations')[0]==w['upstream_question']
  assert gs[qpair[0]['query_id']]['answer']==gs[qpair[1]['query_id']]['answer']
  a=w['records']['A'];b=w['records']['B'];q=qpair[0];g=gs[q['query_id']]
  es={'e1':edge(a),'e2':edge(b),'e4':edge(a,'evidence'),'e5':edge(b,'evidence')};es['e3']=cedge({'answer':g['answer'],'evidence_ids':g['sufficient_evidence_sets'][0]},es)
  variants=conditions(es,dict(answer='insufficient',facts=[],evidence=[],support_links=[]))
  for name,(e,audit) in variants.items():
   if name not in ['drop_e5','drop_e3_evidence_and_e5']:assert source_proof(g,{k:e[k] for k in ['e4','e5']},a+b)['sufficient']
  assert 'e3' not in variants['no_e3'][0]
  assert 'answer' not in variants['original_without_answer'][0]['e3']
  assert variants['original_without_evidence'][0]['e3']['evidence']==[]
  assert not source_proof(g,variants['drop_e3_evidence_and_e5'][0],a+b)['sufficient']
  for ss in g['sufficient_evidence_sets']:assert solve(q,[x for x in a+b if x['id'] in ss])==g['answer']
 # Need actual C input only for swap; direct edges and gold cannot influence it.
 test=copy.deepcopy(es);test['e4']=edge([]);test['e5']=edge([]);assert swapped(es['e3'],es)==swapped(es['e3'],test)
 print('CPU VALIDATED: fresh worlds, equal-answer paired demands, all conditions/four cells, intact direct paths, absent vs insufficient, authentic-source proof, sender-local intervention')
 write(HERE/'results/cpu_validation.json',dict(passed=True,formal_worlds=50,smoke_worlds=4,formal_conditions=1400,conditions_per_query=14,execution_hash=execution_hash()))

if __name__=='__main__':
 command=sys.argv[1]
 if command=='prepare':prepare()
 elif command=='validate':validate()
 elif command=='run':execute(sys.argv[2])
 elif command=='analyze':
  from analyze import main
  main()
