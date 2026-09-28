import time,sys
from protocol_pilot.common import *
from protocol_pilot.protocols import OPS
summary=read(ROOT/'runs/smoke-v2/smoke_summary.json')
assert summary['parse_success']>=.95 and summary['answer_accuracy']>=.60,'Smoke threshold failed'
assert not (ROOT/'configs/freeze.json').exists(),'Already frozen; cannot overwrite'
conditions=[c for c in read(ROOT/'data/intervention_manifest.json')['conditions'] if c['split']!='smoke']
tr=rows(ROOT/'runs/smoke-v2/traces.jsonl');elapsed=sum(t['seconds'] for t in tr);total_output=sum(t['output_tokens'] for t in tr)
# Upper request bound ignores all cache reuse and counts C+D for every modified condition.
upper_requests=1600+2*sum(c['condition']!='full' for c in conditions)+4
# Empirical role-weighted rate, not a completion-time promise.
role_s={r:sum(t['seconds'] for t in tr if t['role']==r)/sum(t['role']==r for t in tr) for r in 'ABCD'}
estimated=400*sum(role_s.values())+sum(c['condition']!='full' for c in conditions)*(role_s['C']+role_s['D'])
record=dict(time=time.time(),execution_code_hash=codehash(),files={str(p.relative_to(ROOT)):digest(p.read_text()) for root in ['data','prompts','configs'] for p in (ROOT/root).glob('*') if p.is_file()},plan_conditions=len(conditions),request_upper_bound=upper_requests,smoke=summary,smoke_inference_seconds=elapsed,smoke_generated_tokens=total_output,estimated_inference_seconds_conservative=estimated,estimate_not_guarantee=True,scope='200 formal worlds / 400 queries / 3600 conditions; no scaling')
write(ROOT/'configs/freeze.json',record)
(ROOT/'EXPERIMENT_SPEC.md').open('a').write('\n## 正式冻结\n见 configs/freeze.json。正式预算估计 '+str(round(estimated/3600,3))+' GPU小时（另加初始化及smoke），请求上界 '+str(upper_requests)+'，不作完成时间保证。未缩减世界。局部precision、需求与依赖特征在代码中固定。额外诊断预定为train entity_join demand1字典序首4个世界，键置换反事实，完整边界移除jk1+jk2+ev4+ev5；不进入正式效果分母。\n')
print(json.dumps(record,indent=2))
