"""Predictor inputs are question, reference visible edges and declared transforms only."""
import itertools
from .common import *
from .protocols import apply,OPS,units

def features(question,base_edges,condition,count,local_priors=None,pair_priors=None):
 # No gold, outcome, modified node output or hidden task labels in API.
 ops=condition['ops'];es,_=apply(base_edges,ops,condition['control_target'],count)
 local={'n_ops':len(ops),'before_tokens':sum(count(x) for x in base_edges.values()),'estimated_token_saving':sum(count(base_edges[k])-count(es[k]) for k in es)}
 for op in ops:local['operation='+op]=1
 for e in ['e1','e2','e3','e4','e5']:
  local[e+'_before_units']=len(units(base_edges[e]));local[e+'_unit_change']=len(units(es[e]))-len(units(base_edges[e]))
 local['training_precision_gain']=sum((local_priors or {}).get(o,0) for o in ops)
 d={'requires_evidence':int('verifiable evidence' in question),'requires_year':int('valid in year' in question),'requires_eligible':int('eligible yes' in question),'all_codes':int('regardless of project' in question)}
 def ks(edge):return {f.get('key') for f in units(es[edge]) if f.get('key')}
 dep={'upstream_key_overlap':len(ks('e1')&ks('e2')),'direct_key_overlap':len(ks('e4')&ks('e5')),'direct_evidence_paths':int(bool(units(es['e4'])))+int(bool(units(es['e5']))),'candidate_keys_after':len(ks('e1')),'reference_conclusion_evidence_retained':len(units(es['e3'])),'left_key_mismatch':len(ks('e1')^ks('e4')),'right_key_mismatch':len(ks('e2')^ks('e5'))}
 dep['year_retained_upstream']=sum(f.get('qualifier') is not None for f in units(es['e1']))
 dep['year_retained_direct']=sum(f.get('qualifier') is not None for f in units(es['e4']))
 dep['training_pair_interaction']=sum((pair_priors or {}).get('+'.join(sorted(p)),0) for p in itertools.combinations(ops,2))
 dep['missing_both_direct']=int(not units(es['e4']) and not units(es['e5']))
 for k,v in list(dep.items()):
  for dk,dv in d.items():dep[dk+'*'+k]=dv*v
 return {'local':local,'demand':d,'dependency':dep,'estimated_edges_hash':digest(es)}
def flatten(f,level):
 x={}
 for group in ['local','demand','dependency'][:level]:x.update({group+'.'+k:v for k,v in f[group].items()})
 return x
