from collections import Counter
from protocol_pilot.common import *
from protocol_pilot.protocols import apply,units
from protocol_pilot.schemas import edge
qs={q['query_id']:q for q in rows(ROOT/'data/queries.jsonl')};ws={w['world_id']:w for w in rows(ROOT/'data/worlds.jsonl')};cs=read(ROOT/'data/intervention_manifest.json')['conditions'];coverage={}
for c in cs:
 if c['split']=='smoke' or c['group'] not in ['seen_pair','held_pair']:continue
 q=qs[c['query_id']];w=ws[q['world_id']];a=w['records']['A'];b=w['records']['B'];es={'e1':edge(a),'e2':edge(b),'e3':dict(answer=['placeholder'],facts=[],evidence=a+b,support_links=[{'id':f['id'],'supports':'answer'} for f in a+b]),'e4':edge(a,'evidence'),'e5':edge(b,'evidence')}
 _,audit=apply(es,c['ops']);entry=coverage.setdefault(c['condition'],{'group':c['group'],'worlds':set(),'applicable_worlds':set(),'queries':0,'applicable_queries':0});entry['worlds'].add(q['world_id']);entry['queries']+=1
 if all(not x['noop'] for x in audit):entry['applicable_worlds'].add(q['world_id']);entry['applicable_queries']+=1
for c,x in coverage.items():x['worlds']=len(x['worlds']);x['applicable_worlds']=len(x['applicable_worlds'])
write(ROOT/'data/pair_applicability_preregistered.json',coverage)
gs=rows(ROOT/'data/gold.jsonl');assert any(len(g['sufficient_evidence_sets'])>1 for g in gs)
print(json.dumps(coverage,indent=2));print('Multiple legitimate evidence sets verified')
