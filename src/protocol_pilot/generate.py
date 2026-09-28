import random,itertools
from .common import *
FAMILIES=['independent','entity_join','qualifier','deferred_disambiguation','redundant_evidence']
PUBLIC='Records describe fictional entities. Only an identical entity key establishes identity across documents; identical names alone do not. A null field is unknown, an absent field was not supplied, and [] explicitly contains no entries. For answering roles, the requested answer consists of code strings, not names or project values. A request for evidence requires source record IDs sufficient to derive the entire answer. Never invent missing facts. If the answer cannot be established, use answer="insufficient".'
def solve(q,fs):
 def get(kind): return [f for f in fs if f.get('kind')==kind and f.get('value') is not None]
 if q['mode']=='independent':
  selected=[f for f in get('code') if f.get('name') in q['targets']];return sorted({f['value'] for f in selected}) if len(selected)>=2 else None
 if q['mode']=='all_codes': return sorted({f['value'] for f in get('code')}) or None
 a=[f for f in get('project') if f.get('value')==q['target'] and (q['year'] is None or f.get('qualifier')==str(q['year']))]
 keys={f.get('key') for f in a}-{None}
 if q['eligible']: keys&={f.get('key') for f in get('eligible') if f.get('value')=='yes'}
 return sorted({f['value'] for f in get('code') if f.get('key') in keys}) or None

def make_world(r,fam,i,split):
 wid=f'{split}-{fam}-{i:03d}'; keys=['K'+''.join(r.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789',k=7)) for _ in range(4)]
 names=[''.join(r.choices('abcdefghijklmnopqrstuvwxyz',k=7)).title() for _ in keys]
 if fam=='entity_join': names=[names[0]]*4
 codes=['V'+''.join(r.choices('ABCDEFGHJKLMNPQRSTUVWXYZ23456789',k=5)) for _ in keys];project='P'+''.join(r.choices('abcdefghjkmnpqrstuvwxyz',k=6)); other='P'+''.join(r.choices('abcdefghjkmnpqrstuvwxyz',k=6))
 ids=r.sample(range(100000,999999),20);n=iter(ids)
 def fact(j,kind,value,qual=None): return dict(id='R'+str(next(n)),key=keys[j],name=names[j],kind=kind,value=value,qualifier=qual)
 order=list(range(4));r.shuffle(order); selected=i%4
 A=[];B=[]
 if fam=='independent':
  A=[fact(j,'code',codes[j]) for j in order[:2]];B=[fact(j,'code',codes[j]) for j in order[2:]]
  A += [fact(order[0],'code',codes[order[0]]),fact(order[1],'note','archive')]; B += [fact(order[2],'code',codes[order[2]]),fact(order[3],'note','archive')]
 elif fam=='qualifier':
  A=[fact(j,'project',project if j in [selected,(selected+1)%4] else other,'2030' if j==selected else '2020') for j in order]
  B=[fact(j,'code',codes[j]) for j in order]
 elif fam=='deferred_disambiguation':
  A=[fact(j,'project',project if j in [selected,(selected+1)%4] else other) for j in order]
  B=[fact(j,'code',codes[j]) for j in order]+[fact(j,'eligible','yes' if j==selected else 'no') for j in order]
 else:
  A=[fact(j,'project',project if j==selected else other) for j in order];B=[fact(j,'code',codes[j]) for j in order]
 if fam=='redundant_evidence':
  A.append(fact(selected,'project',project));B.append(fact(selected,'code',codes[selected]))
 r.shuffle(A);r.shuffle(B)
 if fam=='deferred_disambiguation':
  correct=next(f for f in A if f['key']==keys[selected]);A.remove(correct);A.insert(i%4,correct)
 def document(fs):
  return '\n'.join((f"Source {f['id']}: {f['name']} (entity key {f['key']}) has {f['kind']} {f['value']}"+(f" valid only in year {f['qualifier']}" if f['qualifier'] else '')+'.') for f in fs)
 w=dict(world_id=wid,family=fam,split=split,documents={'A':document(A),'B':document(B)},records={'A':A,'B':B})
 qs=[];gs=[]
 for d in [0,1]:
  q=dict(world_id=wid,query_id=wid+f'-d{d}',split=split,family=fam,demand=d,seed=20260928,target=project,year=2030 if fam=='qualifier' and d else None,eligible=fam=='deferred_disambiguation' and bool(d),require_evidence=bool(d) if fam in ['independent','redundant_evidence'] else False,mode='independent' if fam=='independent' else 'all_codes' if fam=='entity_join' and not d else 'join',targets=[names[order[0]],names[order[2]]])
  if fam=='independent': question=f"Give the codes for {q['targets'][0]} and {q['targets'][1]}."
  elif q['mode']=='all_codes': question='Give all codes listed in document B, regardless of project.'
  else:
   question=f'Give the codes of all entities assigned to project {project}'
   question+= (' valid in year 2030' if q['year'] else ' in any year') if fam=='qualifier' else ''
   question+= ' that have eligible yes' if q['eligible'] else ''
   question+='.'
  if split=='test': question='Using the supplied records, '+question[0].lower()+question[1:]
  question+= ' Include sufficient source record IDs as verifiable evidence.' if q['require_evidence'] else ' Source citations are optional.'
  q['question']=question;answer=solve(q,A+B)
  sufficient=[]
  for k in range(1,len(A+B)+1):
   for sub in itertools.combinations(A+B,k):
    ss={f['id'] for f in sub}
    if any(set(s)<=ss for s in sufficient):continue
    if solve(q,sub)==answer:sufficient.append(sorted(ss))
  gs.append(dict(query_id=q['query_id'],answer=answer,sufficient_evidence_sets=sufficient,requirements={k:q[k] for k in ['mode','year','eligible','require_evidence']},necessity_change={'independent':'source evidence','entity_join':'project identity mapping','qualifier':'valid year','deferred_disambiguation':'eligibility','redundant_evidence':'source evidence'}[fam]));qs.append(q)
 return w,qs,gs

def main():
 r=random.Random(20260928);ws=[];qs=[];gs=[]
 for fam in FAMILIES:
  splits=['train']*20+['validation']*10+['test']*10;random.Random(718).shuffle(splits)
  for i,split in enumerate(splits):
   w,q,g=make_world(r,fam,i,split);ws.append(w);qs+=q;gs+=g
 for fam in FAMILIES:
  for i in range(4):
   w,q,g=make_world(random.Random(9090+FAMILIES.index(fam)*100+i),fam,i,'smoke');ws.append(w);qs+=q;gs+=g
 for name,data in [('worlds',ws),('queries',qs),('gold',gs)]:jsonl(ROOT/'data'/f'{name}.jsonl',data)
 write(ROOT/'data/split_manifest.json',{s:[w['world_id'] for w in ws if w['split']==s] for s in ['train','validation','test','smoke']})
 from .protocols import plan
 plan(qs)
 print('Generated',len(ws),'worlds',len(qs),'queries')
if __name__=='__main__':main()
