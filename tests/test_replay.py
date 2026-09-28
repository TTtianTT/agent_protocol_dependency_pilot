"""CPU unit tests only; synthetic fake nodes never enter experiment outputs."""
import copy,tempfile
from protocol_pilot.common import *
from protocol_pilot.replay import Experiment
from protocol_pilot.schemas import edge,cedge
from protocol_pilot.protocols import apply
class TestEngine:
 def __init__(self,cache):self.cache=cache;self.calls=[]
 def count(self,x):return len(canon(x))
 def generate(self,req):
  self.calls+=req
  return [dict(cache_key='new'+r['role'],parsed={'answer':['CHANGED'],'evidence_ids':['a']}) for r in req]
def check(ops,roles):
 fs=[dict(id='a',key='k',name='n',kind='code',value='old',qualifier='2030')];edges={'e1':edge(fs),'e2':edge(fs),'e4':edge(fs,'evidence'),'e5':edge(fs,'evidence'),'e3':dict(answer=['OLD'],facts=[],evidence=fs,support_links=[{'id':'a','supports':'answer'}])}
 e=object.__new__(Experiment);e.qs={'q':dict(query_id='q',world_id='w',split='train',demand=0,question='Give codes.')};e.done={('q','full'):dict(edges=edges,nodes={r:r for r in 'ABCD'})};e.engine=TestEngine({r:dict(cache_key=r,parsed={'answer':['OLD'],'evidence_ids':['a']}) for r in 'ABCD'});captured=[];e.record=lambda *args:captured.append(args)
 c=dict(query_id='q',condition='+'.join(ops),ops=ops,control_target='jk1',group='seen_pair');e.modified([c]);assert [r['role'] for r in e.engine.calls]==roles
 s,_,audit=captured[0]
 if 'jk1' in ops and 'ev3' in ops:assert s['edges']['e3']['answer']==['CHANGED'] and s['edges']['e3']['evidence']==[]
 assert e.done[('q','full')]['edges']==edges
 assert s['edges']['e4']==edges['e4']
 # D sees no e1/e2 or original documents. C sees no e4/e5.
 for r in e.engine.calls:
  v=json.loads(r['visible']);assert set(v)==({'question','e1','e2'} if r['role']=='C' else {'question','e3','e4','e5'})
check(['jk1','ev3'],['C','D']);check(['ev3'],['D']);check(['restore'],['D'])
# Canonical hash changes with visible messages, role, model, params or protocol version.
base=dict(model='m',role='D',messages='x',params={'temperature':0},code='v1')
for key in base:
 alt=copy.deepcopy(base);alt[key]='changed';assert digest(alt)!=digest(base)
print('PASS descendant recomputation/new-e3 intervention/no hidden context/preserved direct paths/cache dependencies')
