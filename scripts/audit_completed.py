import json,collections
from protocol_pilot.common import *
run=ROOT/'runs/pilot-v1';freeze=read(ROOT/'configs/freeze.json');predfreeze=read(run/'prediction_freeze.json');out=rows(run/'outcomes.jsonl');tr=rows(run/'traces.jsonl');pred=rows(run/'predictions_before_execution.jsonl');plan=[c for c in read(ROOT/'data/intervention_manifest.json')['conditions'] if c['split']!='smoke']
assert len(out)==len(plan)==3600
assert {(o['query_id'],o['condition']) for o in out}=={(c['query_id'],c['condition']) for c in plan}
assert len(out)==len({(o['query_id'],o['condition']) for o in out})
assert len(pred)==1100 and all(p['time']<=predfreeze['time'] for p in pred)
assert digest((run/'predictions_before_execution.jsonl').read_text())==predfreeze['prediction_hash']
assert all(o['time']>=predfreeze['time'] for o in out if o['split']=='test' and o['condition']!='full')
assert all(t['time']>=predfreeze['time'] for t in tr if t['split']=='test' and t['condition']!='full')
assert all(t['code_hash']==freeze['execution_code_hash'] for t in tr)
assert all(o['code_hash']==freeze['execution_code_hash'] for o in out)
assert codehash()==freeze['execution_code_hash']
for p,h in freeze['files'].items():assert digest((ROOT/p).read_text())==h,(p,'changed since freeze')
trace={t['cache_key']:t for t in tr}
for o in out:
 for role,key in o['nodes'].items():
  t=trace[key];visible=json.loads(t['visible_input'][1]['content'])
  assert set(visible)==({'question','document'} if role in 'AB' else {'question','e1','e2'} if role=='C' else {'question','e3','e4','e5'})
  assert t['dependency_hash']==digest(t['visible_input'])
 assert o['payload_hash']==digest(o['edges'])
for c in rows(ROOT/'results/collision_certificates.jsonl'):
 assert c['visible_input0']==c['visible_input1'] and c['gold0']!=c['gold1']
summary=dict(passed=True,planned_conditions=len(plan),completed_conditions=len(out),queries=len({o['query_id'] for o in out}),worlds=len({o['world_id'] for o in out}),test_predictions=len(pred),node_requests_completed=len(tr),code_hash=codehash(),freeze_time=predfreeze['time'],first_test_modified_time=min(o['time'] for o in out if o['split']=='test' and o['condition']!='full'),model_identity=read(ROOT/'configs/model_identity.json')['file_list_hash'])
write(ROOT/'results/completion_audit.json',summary);print(json.dumps(summary,indent=2))
