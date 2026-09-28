"""Post-outcome descriptive inventory; no protocol changes or new inference."""
import csv, collections, json
from pathlib import Path

HERE=Path(__file__).resolve().parent
def rows(path):return [json.loads(line) for line in path.read_text().splitlines()]
worlds={w['world_id']:w for w in rows(HERE/'data/worlds.jsonl')}
gold={g['world_id']:g for g in rows(HERE/'data/gold.jsonl')}
result=[]
for u in rows(HERE/'runs/formal/upstream.jsonl'):
    fs=u['edges']['e3']['evidence'];groups=collections.defaultdict(list)
    for f in fs:
        if f['key'] is not None:groups[f['key']].append(f)
    truth={f['id']:f for side in worlds[u['world_id']]['records'].values() for f in side}
    authentic={f['id'] for f in fs if f.get('id') in truth and f==truth[f['id']]}
    sufficient=any(set(s)<=authentic for s in gold[u['world_id']]['sufficient_evidence_sets'])
    kinds=collections.Counter(f['kind'] for f in fs)
    result.append(dict(world_id=u['world_id'],scope='post-outcome descriptive inventory',records=len(fs),project_records=kinds['project'],code_records=kinds['code'],same_key_project_code_pair=int(any({'project','code'}<={f['kind'] for f in group} for group in groups.values())),authentic_e3_sufficient=int(sufficient)))
with (HERE/'results/e3_evidence_inventory.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(result[0]),lineterminator='\n');writer.writeheader();writer.writerows(result)
summary={'scope':'post-outcome descriptive; not a preregistered subgroup test','worlds':len(result),'with_project':sum(r['project_records']>0 for r in result),'with_code':sum(r['code_records']>0 for r in result),'same_key_project_code_pair':sum(r['same_key_project_code_pair'] for r in result),'authentic_e3_sufficient':sum(r['authentic_e3_sufficient'] for r in result)}
(HERE/'results/e3_evidence_inventory_summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary))
