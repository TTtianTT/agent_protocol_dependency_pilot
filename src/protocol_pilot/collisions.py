"""Predeclared four-world key permutation diagnostic; not a task performance condition."""
import copy
from .common import *
from .generate import solve,PUBLIC
from .protocols import apply
from .schemas import edge

def run(exp):
 path=exp.run/'collision_diagnostics.jsonl'
 if path.exists():return
 selected=sorted([q for q in exp.qs.values() if q['split']=='train' and q['family']=='entity_join' and q['demand']==1],key=lambda q:q['query_id'])[:4]
 from .replay import request
 req=[];states=[]
 for q in selected:
  w=exp.ws[q['world_id']];a=copy.deepcopy(w['records']['A']);positive=next(f for f in a if f['value']==q['target']);other=next(f for f in a if f['value']!=q['target']);k1,k2=positive['key'],other['key'];positive['key'],other['key']=k2,k1
  document=w['documents']['A'].replace(k1,'TEMPKEY').replace(k2,k1).replace('TEMPKEY',k2)
  req.append(request(q,'collision-counterfactual','A',canon({'question':q['question'],'document':document})))
  states.append((q,a,w,document))
 outputs=exp.engine.generate(req);cert=[]
 for (q,a,w,document),out in zip(states,outputs):
  base=exp.done[(q['query_id'],'full')];alternate=copy.deepcopy(base['edges']);af=(out['parsed'] or {}).get('facts',[]);alternate.update(e1=edge(af),e4=edge(af,'evidence'))
  ops=['jk1','jk2','ev4','ev5'];boundary=lambda es:{k:es[k] for k in ['e1','e2','e4','e5']}
  bb=boundary(apply(base['edges'],ops)[0]);ab=boundary(apply(alternate,ops)[0]);g0=exp.gs[q['query_id']]['answer'];g1=solve(q,a+w['records']['B'])
  ob={'e1':edge(w['records']['A']),'e2':edge(w['records']['B']),'e4':edge(w['records']['A'],'evidence'),'e5':edge(w['records']['B'],'evidence')};oa=copy.deepcopy(ob);oa['e1']=edge(a);oa['e4']=edge(a,'evidence')
  for typ,x,y in [('oracle',boundary(apply(ob,ops)[0]),boundary(apply(oa,ops)[0])),('actual_llm',bb,ab)]:
   visible0=canon({'public':PUBLIC,'question':q['question'],'boundary':x});visible1=canon({'public':PUBLIC,'question':q['question'],'boundary':y});collision=visible0==visible1 and g0!=g1 and (typ=='oracle' or out['parse_error'] is None)
   record=dict(query_id=q['query_id'],world_id=q['world_id'],type=typ,ops=ops,collision_certificate=collision,visible_hash0=digest(visible0),visible_hash1=digest(visible1),gold0=g0,gold1=g1,visible_input0=visible0,visible_input1=visible1,counterfactual_document=document,counterfactual_node_key=out['cache_key'])
   append(path,record);cert.append(record)
 jsonl(ROOT/'results/collision_certificates.jsonl',[x for x in cert if x['collision_certificate']])
