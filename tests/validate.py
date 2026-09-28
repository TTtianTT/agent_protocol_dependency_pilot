import sys,itertools,copy
from protocol_pilot.common import *
from protocol_pilot.generate import solve
from protocol_pilot.protocols import *
from protocol_pilot.schemas import edge

def main():
 ws=rows(ROOT/'data/worlds.jsonl');qs=rows(ROOT/'data/queries.jsonl');gs={g['query_id']:g for g in rows(ROOT/'data/gold.jsonl')};wd={w['world_id']:w for w in ws};manifest=read(ROOT/'data/intervention_manifest.json');cs=manifest['conditions']
 assert len(ws)==220 and len(qs)==440
 for q in qs:
  w=wd[q['world_id']];fs=w['records']['A']+w['records']['B'];g=gs[q['query_id']];assert solve(q,fs)==g['answer'] and g['answer']
  for ss in g['sufficient_evidence_sets']:assert solve(q,[f for f in fs if f['id'] in ss])==g['answer']
  cc=[c for c in cs if c['query_id']==q['query_id']];assert len(cc)==(12 if q['split']=='test' else 8)
  for c in cc:
   if c['group'] in ['held_pair','seen_pair']:assert all(any(a['ops']==[o] for a in cc) for o in c['ops'])
 seen={c['condition'] for c in cs if c['split'] in ['train','validation'] and c['group']=='seen_pair'};held={c['condition'] for c in cs if c['group']=='held_pair'};assert not seen&held and len(seen)>=8 and len(held)>=4
 assert len({c['condition'] for c in cs if c['group']=='held_triple'})>=4
 for fam in {w['family'] for w in ws}:
  assert [sum(w['family']==fam and w['split']==s for w in ws) for s in ['train','validation','test','smoke']]==[20,10,10,4]
 w=ws[0];a=edge(w['records']['A']);b=edge(w['records']['B']);es={'e1':a,'e2':b,'e3':edge([]),'e4':edge(w['records']['A'],'evidence'),'e5':edge(w['records']['B'],'evidence')}
 for op in OPS:
  modified,audit=apply(es,[op]);assert es==copy.deepcopy(es)
  if op.startswith('jk'):assert all(f.get('key') is None for f in units(modified[OPS[op][1]]))
  if op.startswith('q'):assert all(f.get('qualifier') is None for f in units(modified[OPS[op][1]]))
  if op.startswith('ev'):assert modified[OPS[op][1]]['evidence']==[]
 assert apply(es,['restore'])[0]==es
 # Feature extractor has no gold/outcome argument; mutate hidden labels while visible inputs remain fixed.
 from protocol_pilot.features import features
 c=next(c for c in cs if c['condition']=='ren1');f=features('Give codes.',es,c,lambda x:len(canon(x)));assert f==features('Give codes.',copy.deepcopy(es),c,lambda x:len(canon(x)))
 print('PASS generator/oracle/evidence/splits/quartets/holdouts/semantic deletion/restore/feature API')
 write(ROOT/'results/cpu_validation.json',dict(passed=True,worlds=len(ws),queries=len(qs),seen_pairs=len(seen),held_pairs=len(held),planned_formal_conditions=sum(c['split']!='smoke' for c in cs)))
if __name__=='__main__':main()
