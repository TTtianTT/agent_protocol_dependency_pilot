import json,re
FACT={'type':'object','properties':{k:{'type':['string','null']} for k in ['id','key','name','kind','value','qualifier']},'required':['id','key','name','kind','value','qualifier'],'additionalProperties':False}
AB={'type':'object','properties':{'facts':{'type':'array','items':FACT}},'required':['facts'],'additionalProperties':False}
CD={'type':'object','properties':{'answer':{'anyOf':[{'type':'array','items':{'type':'string'}},{'type':'string','enum':['insufficient']}]},'evidence_ids':{'type':'array','items':{'type':'string'}}},'required':['answer','evidence_ids'],'additionalProperties':False}
def parse(raw,role):
 import jsonschema
 try:
  # Fixed deterministic fence removal, no repair generation.
  raw=raw.strip();raw=re.sub(r'^```(?:json)?\s*','',raw);raw=re.sub(r'\s*```$','',raw)
  x=json.loads(raw);jsonschema.validate(x,AB if role in ['A','B'] else CD)
  # Canonicalize only the public source-label prefix, never infer an ID.
  norm=lambda v:re.sub(r'^Source\s+(R[0-9]{6})$',r'\1',v) if isinstance(v,str) else v
  if role in ['A','B']:
   for f in x['facts']:f['id']=norm(f['id'])
  else:x['evidence_ids']=[norm(v) for v in x['evidence_ids']]
  return x,None
 except Exception as e:return None,type(e).__name__+': '+str(e)[:300]
def edge(fs,kind='facts'):
 return {'facts':fs if kind=='facts' else [],'evidence':fs if kind=='evidence' else [],'support_links':[{'id':f['id'],'supports':f['id']} for f in fs]}
def cedge(c,upstream):
 # Sender C actually knows the e1/e2 facts; deterministic citation dereference only.
 fs={f['id']:f for e in ['e1','e2'] for f in upstream[e].get('facts',[]) if f.get('id')}
 ids=c.get('evidence_ids',[])
 return dict(answer=c.get('answer','insufficient'),facts=[],evidence=[fs[i] for i in ids if i in fs],support_links=[{'id':i,'supports':'answer'} for i in ids])

EDGE={'type':'object','properties':{'facts':{'type':'array','items':FACT},'evidence':{'type':'array','items':FACT},'support_links':{'type':'array','items':{'type':'object','properties':{'id':{'type':['string','null']},'supports':{'type':['string','null']}},'required':['id','supports'],'additionalProperties':False}},'answer':CD['properties']['answer']},'required':['facts','evidence','support_links'],'additionalProperties':False}
def validate_edges(es):
 import jsonschema
 for p in es.values():jsonschema.validate(p,EDGE)
 return True
