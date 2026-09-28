import copy,time,sys
from .common import *
from .agents import Engine,BudgetStop
from .schemas import edge,cedge,validate_edges
from .protocols import apply,OPS,downstream_only
from .oracle import score,local_score,recovery

def request(q,cid,role,payload):return dict(query_id=q['query_id'],world_id=q['world_id'],split=q['split'],demand=q['demand'],condition=cid,role=role,visible=payload)
def visible(q,es,role,pretty=False):
 keys=['e1','e2'] if role=='C' else ['e3','e4','e5']
 obj={'question':q['question'],**{k:es[k] for k in keys}}
 return json.dumps(obj,ensure_ascii=False,indent=2) if pretty else canon(obj)
class Experiment:
 def __init__(self,mode):
  self.mode=mode;self.run=ROOT/'runs'/('smoke-v2' if mode=='smoke' else 'pilot-v1');self.engine=Engine(self.run)
  self.qs={q['query_id']:q for q in rows(ROOT/'data/queries.jsonl')};self.ws={w['world_id']:w for w in rows(ROOT/'data/worlds.jsonl')};self.gs={g['query_id']:g for g in rows(ROOT/'data/gold.jsonl')}
  self.conditions=read(ROOT/'data/intervention_manifest.json')['conditions'];self.done={(o['query_id'],o['condition']):o for o in rows(self.run/'outcomes.jsonl')}
 def full(self,qs):
  pending=[q for q in qs if (q['query_id'],'full') not in self.done]
  for off in range(0,len(pending),32):
   batch=pending[off:off+32];req=[]
   for q in batch:
    w=self.ws[q['world_id']]
    for r in 'AB':req.append(request(q,'full',r,canon({'question':q['question'],'document':w['documents'][r]})))
   ab=self.engine.generate(req);states=[]
   for i,q in enumerate(batch):
    a,b=ab[i*2:i*2+2];af=(a['parsed'] or {}).get('facts',[]);bf=(b['parsed'] or {}).get('facts',[])
    states.append(dict(q=q,edges={'e1':edge(af),'e2':edge(bf),'e4':edge(af,'evidence'),'e5':edge(bf,'evidence')},nodes={'A':a,'B':b}))
   cs=self.engine.generate([request(s['q'],'full','C',visible(s['q'],s['edges'],'C')) for s in states])
   for s,c in zip(states,cs):s['nodes']['C']=c;s['edges']['e3']=cedge(c['parsed'] or {},s['edges'])
   ds=self.engine.generate([request(s['q'],'full','D',visible(s['q'],s['edges'],'D')) for s in states])
   for s,d in zip(states,ds):s['nodes']['D']=d;self.record(s,dict(condition='full',ops=[],group='reference'),[])
 def record(self,s,condition,audit):
  q=s['q'];g=self.gs[q['query_id']];d=s['nodes']['D'];es=s['edges'];w=self.ws[q['world_id']]
  # Any malformed node is a workflow format failure (not a lost-information claim).
  parseerr=next((t['parse_error'] for t in s['nodes'].values() if t['parse_error']),None)
  metrics=score(q,g,d['parsed'],parseerr);cmetrics=score(q,g,s['nodes']['C']['parsed'],s['nodes']['C']['parse_error'])
  loc={e:local_score(es[e],w['records']['A' if e in ['e1','e4'] else 'B']) for e in ['e1','e2','e4','e5']}
  o=dict(**{k:q[k] for k in ['query_id','world_id','split','demand','family','seed']},condition=condition['condition'],ops=condition['ops'],group=condition['group'],edges=es,payload_hash=digest(es),serialized_payloads={e:(json.dumps(p,ensure_ascii=False,indent=2) if condition['condition']=='format_only' else canon(p)) for e,p in es.items()},edge_payload_hashes={e:digest(p) for e,p in es.items()},edge_tokens={e:self.engine.count(p,condition['condition']=='format_only') for e,p in es.items()},nodes={r:t['cache_key'] for r,t in s['nodes'].items()},node_tokens={r:{'input':t['input_tokens'],'output':t['output_tokens'],'seconds':t['seconds']} for r,t in s['nodes'].items()},metrics=metrics,c_metrics=cmetrics,local=loc,recovery=recovery(q,g,{e:es[e] for e in ['e3','e4','e5']}),schema_legal=validate_edges(es),model_hash=self.engine.modelhash,code_hash=self.engine.code,status='format_failure' if parseerr else 'completed',time=time.time(),audit=audit)
  append(self.run/'outcomes.jsonl',o);append(self.run/'intervention_audit.jsonl',dict(query_id=q['query_id'],condition=condition['condition'],audit=audit));self.done[(q['query_id'],condition['condition'])]=o
 def modified(self,conditions):
  pending=[c for c in conditions if (c['query_id'],c['condition']) not in self.done]
  for off in range(0,len(pending),32):
   batch=pending[off:off+32];states=[];creqs=[];cidx=[]
   for cond in batch:
    q=self.qs[cond['query_id']];base=self.done[(q['query_id'],'full')];nodes={r:self.engine.cache[k] for r,k in base['nodes'].items()}
    # Apply all non-e3 modifications first. e3 changes apply only after affected C has recomputed.
    upstream_ops=[o for o in cond['ops'] if o not in OPS or OPS[o][1]!='e3'];post=[o for o in cond['ops'] if o in OPS and OPS[o][1]=='e3']
    es,audit=apply(base['edges'],upstream_ops,cond['control_target'],self.engine.count)
    s=dict(q=q,edges=es,nodes=nodes,condition=cond,audit=audit,post=post);states.append(s)
    if any(es[e]!=base['edges'][e] for e in ['e1','e2']) or cond['condition']=='format_only':
     creqs.append(request(q,cond['condition'],'C',visible(q,es,'C',cond['condition']=='format_only')));cidx.append(len(states)-1)
   for idx,c in zip(cidx,self.engine.generate(creqs)):
    s=states[idx];s['nodes']['C']=c;s['edges']['e3']=cedge(c['parsed'] or {},s['edges'])
   for s in states:
    s['edges'],audit=apply(s['edges'],s['post'],s['condition']['control_target'],self.engine.count);s['audit']+=audit
   ds=self.engine.generate([request(s['q'],s['condition']['condition'],'D',visible(s['q'],s['edges'],'D',s['condition']['condition']=='format_only')) for s in states])
   for s,d in zip(states,ds):s['nodes']['D']=d;self.record(s,s['condition'],s['audit'])
 def stage(self,name,planned,completed):
  append(self.run/'stages.jsonl',dict(stage=name,planned=planned,completed=completed,failed=sum(o['status']=='format_failure' for o in self.done.values() if (o['condition']=='full' if name=='full' else o['split']=='test' and o['condition']!='full' if name=='test' else o['split'] in ['train','validation'] and o['condition']!='full')),cached=self.engine.hits,time=time.time(),requests=self.engine.usage['requests'],code_hash=self.engine.code))
 def run_all(self):
  write(self.run/'manifest.json',dict(mode=self.mode,code_hash=self.engine.code,config=self.engine.cfg,data_hash=digest(read(ROOT/'data/intervention_manifest.json')),started=time.time()))
  if self.mode=='smoke':
   qs=[q for q in self.qs.values() if q['split']=='smoke'];self.full(qs)
   full=[self.done[(q['query_id'],'full')] for q in qs];summary={k:sum(o['metrics'][k] for o in full)/len(full) for k in ['joint_success','answer_accuracy','parse_success']}
   summary.update(queries=len(qs),usage=self.engine.usage);write(self.run/'smoke_summary.json',summary);print(summary,flush=True)
   return
  freeze=read(ROOT/'configs/freeze.json');assert freeze['execution_code_hash']==self.engine.code,'Execution code differs from freeze'
  qs=[q for q in self.qs.values() if q['split']!='smoke'];self.full(qs);self.stage('full',len(qs),sum(c=='full' for q,c in self.done))
  train=[c for c in self.conditions if c['split'] in ['train','validation'] and c['condition']!='full'];self.modified(train);self.stage('train_validation',len(train),sum(o['split'] in ['train','validation'] and o['condition']!='full' for o in self.done.values()))
  from .collisions import run as run_collisions
  run_collisions(self)
  from .prediction import freeze_predictions
  freeze_predictions(self)
  test=[c for c in self.conditions if c['split']=='test' and c['condition']!='full'];assert (self.run/'predictions_before_execution.jsonl').exists();self.modified(test);self.stage('test',len(test),sum(o['split']=='test' and o['condition']!='full' for o in self.done.values()))
  write(self.run/'completed.json',dict(time=time.time(),planned=3600,completed=len(self.done),code_hash=self.engine.code));self.engine.save_usage()
  from .reporting import main
  main()
def main():
 e=Experiment(sys.argv[1] if len(sys.argv)>1 else 'smoke')
 try:e.run_all()
 except BudgetStop as exc:
  write(e.run/'PAUSED.json',dict(reason=str(exc),time=time.time(),completed=len(e.done)));print('BUDGET PAUSE',flush=True)
 except Exception as exc:
  append(e.run/'failures.jsonl',dict(status='infrastructure_or_implementation_failure',error=repr(exc),time=time.time(),code_hash=e.engine.code));raise
 finally:e.engine.save_usage()
if __name__=='__main__':main()
