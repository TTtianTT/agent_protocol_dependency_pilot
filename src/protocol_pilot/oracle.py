from .generate import solve
from .protocols import units

def score(q,g,output,parse_error=None):
 if output is None or parse_error:return dict(joint_success=0,answer_accuracy=0,evidence_validity=0,evidence_coverage=0,insufficient=0,parse_success=0)
 a=output.get('answer');correct=isinstance(a,list) and sorted(set(a))==g['answer'];ids=set(output.get('evidence_ids',[]));ss=g['sufficient_evidence_sets']
 sufficient=any(set(s)<=ids for s in ss)
 valid_ids=set().union(*(set(s) for s in ss));valid=len(ids&valid_ids)/len(ids) if ids else 0
 coverage=max([len(set(s)&ids)/len(s) for s in ss] or [0])
 return dict(joint_success=int(correct and (not q['require_evidence'] or sufficient)),answer_accuracy=int(correct),evidence_validity=valid,evidence_coverage=coverage,insufficient=int(a=='insufficient'),parse_success=1)
def local_score(payload,records):
 us=payload.get('facts',[]) or payload.get('evidence',[])
 fields=['id','key','name','kind','value','qualifier']
 truth={tuple(f.get(k) for k in fields) for f in records};actual={tuple(f.get(k) for k in fields) for f in us}
 tp=len(truth&actual);p=tp/len(actual) if actual else 0;r=tp/len(truth) if truth else 0
 return dict(precision=p,recall=r,f1=2*p*r/(p+r) if p+r else 0)
def recovery(q,g,edges):
 fs=list({tuple(sorted(f.items())):f for e in edges.values() for f in units(e)}.values())
 # Positive certificate of sufficient observed facts, not a negative proof.
 ans=solve(q,fs)
 ids={f.get('id') for f in fs};sufficient=ans==g['answer'] and (not q['require_evidence'] or any(set(s)<=ids for s in g['sufficient_evidence_sets']))
 return {'oracle_visible_sufficient':sufficient,'unrecoverability_proven':False,'negative_interpretation':'absence of this solver proof is not a collision certificate'}
