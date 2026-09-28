import os,time,itertools
import numpy as np
import joblib
from sklearn.feature_extraction import DictVectorizer
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression,Ridge
from sklearn.metrics import brier_score_loss,mean_absolute_error
from .common import *
from .features import features,flatten

def pred(model,fs):
 if model['level']==0:return np.full(len(fs),model['p']),np.full(len(fs),model['delta'])
 x=model['scaler'].transform(model['vectorizer'].transform([flatten(f,model['level']) for f in fs]))
 p=model['classifier'].predict_proba(x)[:,1] if model['classifier'] is not None else np.full(len(fs),model['p'])
 return p,np.clip(model['regressor'].predict(x),-1,1)
def freeze_predictions(exp):
 path=exp.run/'predictions_before_execution.jsonl';mpath=exp.run/'predictors.joblib'
 if path.exists():
  meta=read(exp.run/'prediction_freeze.json');assert digest(path.read_text())==meta['prediction_hash'];assert digest(mpath.read_bytes().hex())==meta['model_hash'];return
 assert not any(o['split']=='test' and o['condition']!='full' for o in exp.done.values()),'Test interventions already observed'
 full={q:o for (q,c),o in exp.done.items() if c=='full'}
 prior={};pairprior={}
 for op in read(ROOT/'data/intervention_manifest.json')['operations']:
  vals=[]
  for (qid,c),o in exp.done.items():
   if o['split']=='train' and c==op:
    b=full[qid];vals.append(np.mean([o['local'][e]['precision']-b['local'][e]['precision'] for e in o['local']]))
  prior[op]=float(np.mean(vals)) if vals else 0
 for (qid,c),o in exp.done.items():
  if o['split']=='train' and o['group']=='seen_pair':
   a,b=o['ops'];base=full[qid];ja=exp.done[(qid,a)];jb=exp.done[(qid,b)]
   j=-o['metrics']['joint_success']+ja['metrics']['joint_success']+jb['metrics']['joint_success']-base['metrics']['joint_success'];pairprior.setdefault(c,[]).append(j)
 pairprior={k:float(np.mean(v)) for k,v in pairprior.items()}
 def f(c):return features(exp.qs[c['query_id']]['question'],full[c['query_id']]['edges'],c,exp.engine.count,prior,pairprior)
 cs={s:[c for c in exp.conditions if c['split']==s and c['condition']!='full'] for s in ['train','validation','test']}
 fs={s:[f(c) for c in cs[s]] for s in cs};ys={};deltas={}
 for s in ['train','validation']:
  deltas[s]=np.array([full[c['query_id']]['metrics']['joint_success']-exp.done[(c['query_id'],c['condition'])]['metrics']['joint_success'] for c in cs[s]])
  ys[s]=(deltas[s]>0).astype(int)
 models=[];valid=[]
 for level in range(4):
  m={'level':level,'p':float(ys['train'].mean()),'delta':float(deltas['train'].mean())}
  if level:
   vector=DictVectorizer(sparse=False);xt=vector.fit_transform([flatten(f,level) for f in fs['train']]);scaler=StandardScaler();xt=scaler.fit_transform(xt);xv=scaler.transform(vector.transform([flatten(f,level) for f in fs['validation']]))
   bestc=None;bestr=None
   for C in [0.1,1.0]:
    classifier=LogisticRegression(C=C,max_iter=2000,random_state=41) if len(set(ys['train']))>1 else None
    if classifier is not None:classifier.fit(xt,ys['train'])
    prob=classifier.predict_proba(xv)[:,1] if classifier is not None else np.full(len(xv),m['p']);loss=brier_score_loss(ys['validation'],prob)
    if bestc is None or loss<bestc[0]:bestc=(loss,classifier,C)
    reg=Ridge(alpha=1/C).fit(xt,deltas['train']);loss=mean_absolute_error(deltas['validation'],reg.predict(xv))
    if bestr is None or loss<bestr[0]:bestr=(loss,reg,C)
   m.update(vectorizer=vector,scaler=scaler,classifier=bestc[1],regressor=bestr[1],classifier_C=bestc[2],regressor_C=bestr[2])
  p,delta=pred(m,fs['validation']);options=[]
  for threshold in [0.1,0.25,0.5]:
   accept=p<threshold;success=np.mean([full[c['query_id']]['metrics']['joint_success'] for c in cs['validation']])-np.mean(accept*deltas['validation']);savings=np.mean([fs['validation'][i]['local']['estimated_token_saving']*accept[i] for i in range(len(accept))]);options.append((success,savings,-threshold,threshold))
  m['threshold']=max(options)[3];models.append(m);valid.append(dict(model='M'+str(level),threshold=m['threshold'],harm_train_count=int(ys['train'].sum()),harm_validation_count=int(ys['validation'].sum()),validation_Brier=float(brier_score_loss(ys['validation'],p)),validation_MAE=float(mean_absolute_error(deltas['validation'],delta))))
 joblib.dump(dict(models=models,local_priors=prior,pair_priors=pairprior,validation=valid),mpath)
 mh=digest(mpath.read_bytes().hex());predictions=[];preds=[pred(m,fs['test']) for m in models]
 for i,c in enumerate(cs['test']):
  predictions.append(dict(**c,time=time.time(),features=fs['test'][i],model_hash=mh,code_hash=exp.engine.code,reference_payload_hash=full[c['query_id']]['payload_hash'],predictions={f'M{k}':dict(harm_probability=float(preds[k][0][i]),delta_L=float(preds[k][1][i]),threshold=models[k]['threshold'],accept=bool(preds[k][0][i]<models[k]['threshold'])) for k in range(4)}))
 with path.open('x') as fp:
  for p in predictions:fp.write(canon(p)+'\n')
  fp.flush();os.fsync(fp.fileno())
 os.chmod(path,0o444);os.chmod(mpath,0o444)
 write(exp.run/'prediction_freeze.json',dict(time=time.time(),prediction_hash=digest(path.read_text()),model_hash=mh,code_hash=exp.engine.code,validation=valid,test_outcomes_executed=0,test_predictions=len(predictions),feature_scope='question, reference visible logs, declared operations, train priors only'))
 print('FROZEN TEST PREDICTIONS',len(predictions),flush=True)
