import copy,random,itertools
from .common import *
OPS={
 'jk1':('drop_join_key','e1'),'jk2':('drop_join_key','e2'),
 'q1':('drop_qualifier','e1'),'q4':('drop_qualifier','e4'),
 't1':('top1_candidate','e1'),'t4':('top1_candidate','e4'),
 'ev3':('drop_evidence','e3'),'ev4':('drop_evidence','e4'),'ev5':('drop_evidence','e5'),
 'link3':('drop_support_link','e3'),'ren1':('rename_key','e1'),'ren2':('rename_key','e2')}
QUARTETS=[['jk1','jk2','ev4','ev5'],['q1','q4','ev3','ev5'],['t1','t4','ev3','ev5'],['ren1','ren2','link3','ev4']]
SEEN=[[(0,2),(1,3)],[(0,1),(2,3)],[(0,2),(1,3)],[(0,2),(1,3)]]
HELD=[[(0,3),(1,2)],[(0,2),(1,3)],[(0,3),(1,2)],[(0,1),(2,3)]]
FQ={'independent':3,'entity_join':0,'qualifier':1,'deferred_disambiguation':2,'redundant_evidence':3}
def plan(qs):
 conditions=[]
 for idx,q in enumerate(qs):
  k=1 if q['family']=='redundant_evidence' and int(q['world_id'].split('-')[-1])%2==0 else FQ[q['family']];atoms=QUARTETS[k];cs=[('full',[],'reference')]+[(x,[x],'atom') for x in atoms]
  for ij in SEEN[k]:
   ops=sorted(atoms[j] for j in ij);cs.append(('+'.join(ops),ops,'seen_pair'))
  if q['split']=='test':
   for ij in HELD[k]:
    ops=sorted(atoms[j] for j in ij);cs.append(('+'.join(ops),ops,'held_pair'))
   for ijk in [(0,1,2),(1,2,3)]:
    ops=sorted(atoms[j] for j in ijk);cs.append(('+'.join(ops),ops,'held_triple'))
  control=['format_only','random_drop_matched','consistent_rename','restore'][int(q['world_id'].split('-')[-1])%4]
  cs.append((control,[control], 'control'))
  for cid,ops,group in cs: conditions.append(dict(query_id=q['query_id'],world_id=q['world_id'],split=q['split'],condition=cid,ops=ops,group=group,control_target=('ev4' if k==3 and cid=='random_drop_matched' else atoms[0]),seed=921))
 details={k:{'type':v[0],'edge':v[1],'parameter': 'all key occurrences' if k.startswith('jk') else 'valid year' if k.startswith('q') else 'first entity in sender order' if k.startswith('t') else 'all evidence content and citation links' if k.startswith('ev') else 'conclusion-to-fact links only' if k=='link3' else 'fixed character permutation plus prefix; injective global key namespace', 'applicable':'target present; otherwise noop'} for k,v in OPS.items()}
 write(ROOT/'data/intervention_manifest.json',dict(operations=details,quartets=QUARTETS,seen=SEEN,held=HELD,conditions=conditions,hash=digest(conditions),control_rotation='world numeric index modulo four'))

def rename(s):
 alphabet='ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';mapping=str.maketrans(alphabet,alphabet[13:]+alphabet[:13]);return 'X'+s.translate(mapping)
def units(p):return p.get('facts',[])+p.get('evidence',[])
def single(payload,op):
 p=copy.deepcopy(payload);kind=OPS[op][0]
 if kind in ['drop_join_key','drop_qualifier','rename_key']:
  field='qualifier' if kind=='drop_qualifier' else 'key'
  for u in units(p):
   if field in u and u[field] is not None: u[field]=rename(u[field]) if kind=='rename_key' else None
 elif kind=='top1_candidate':
  us=units(p);first=next((u.get('key') for u in us if u.get('key')),None)
  if first:
   for f in ['facts','evidence']:
    p[f]=[u for u in p.get(f,[]) if u.get('key')==first]
   ids={u['id'] for u in units(p)};p['support_links']=[s for s in p.get('support_links',[]) if s.get('id') in ids]
 elif kind=='drop_evidence':
  p['evidence']=[];p['support_links']=[]
  # e3 has only conclusion plus source evidence; e4/e5 only evidence.
 elif kind=='drop_support_link':p['support_links']=[]
 return p

def apply(edges,ops,target='jk1',tokenize=None):
 es=copy.deepcopy(edges);aud=[]
 for op in ops:
  if op in OPS:
   edge=OPS[op][1];before=copy.deepcopy(es[edge]);es[edge]=single(before,op)
   aud.append(dict(operation=op,edge=edge,before_hash=digest(before),after_hash=digest(es[edge]),noop=before==es[edge],removed_units=len(units(before))-len(units(es[edge]))))
  elif op=='consistent_rename':
   # identical public map deployed across ALL four boundary edges
   for edge in ['e1','e2','e4','e5']:
    before=es[edge];es[edge]=single(before,'ren1');aud.append(dict(operation=op,edge=edge,noop=before==es[edge]))
  elif op=='restore':
   edge=OPS[target][1];before=copy.deepcopy(es[edge]);deleted=single(before,target);es[edge]=before
   aud.append(dict(operation=op,edge=edge,restored_from_hash=digest(deleted),noop=before==deleted,restored=True,target=target))
  elif op=='format_only':
   es={k:dict(reversed(list(v.items()))) for k,v in es.items()};aud.append(dict(operation=op,edge='all',noop=False,semantic_noop=True))
  elif op=='random_drop_matched':
   edge=OPS[target][1];before=copy.deepcopy(es[edge]);desired=single(before,target)
   count=tokenize or (lambda p:len(canon(p)))
   budget=count(before)-count(desired);p=copy.deepcopy(before);rng=random.Random(921)
   slots=[(field,i,key) for field in ['facts','evidence'] for i,u in enumerate(p.get(field,[])) for key in ['name','key','value','qualifier'] if u.get(key) is not None];rng.shuffle(slots)
   best=copy.deepcopy(p);err=abs(budget)
   for field,i,key in slots:
    p[field][i][key]=None;e=abs((count(before)-count(p))-budget)
    if e<err:best=copy.deepcopy(p);err=e
   # Also compare random whole-record deletion prefixes to match large savings.
   slots2=[(field,i) for field in ['facts','evidence'] for i,_ in enumerate(before.get(field,[]))];rng.shuffle(slots2);removed=set()
   for slot in slots2:
    removed.add(slot);candidate=copy.deepcopy(before)
    for field in ['facts','evidence']:candidate[field]=[u for i,u in enumerate(before.get(field,[])) if (field,i) not in removed]
    kept={u['id'] for u in units(candidate)};candidate['support_links']=[s for s in candidate.get('support_links',[]) if s.get('id') in kept]
    e=abs((count(before)-count(candidate))-budget)
    if e<err:best=candidate;err=e
   es[edge]=best;aud.append(dict(operation=op,edge=edge,noop=best==before,target_saving=budget,actual_saving=count(before)-count(best),matching_error=err))
 return es,aud

def downstream_only(ops):return all(o in OPS and OPS[o][1] in ['e3','e4','e5'] or o=='restore' for o in ops)
