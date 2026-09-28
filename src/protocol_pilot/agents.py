import time,os,yaml,hashlib,importlib.metadata
from .common import *
from .schemas import parse,AB,CD
from .generate import PUBLIC
class BudgetStop(Exception):pass
class Engine:
 def __init__(self,run):
  from transformers import AutoTokenizer
  self.cfg=yaml.safe_load((ROOT/'configs/pilot.yaml').read_text());self.run=Path(run);self.run.mkdir(exist_ok=True,parents=True)
  self.code=codehash();self.model=read(ROOT/'configs/model_identity.json');self.modelhash=digest(self.model)
  self.tok=AutoTokenizer.from_pretrained(self.cfg['model'],local_files_only=True);self.prompts={r:(ROOT/'prompts'/f'{r}.txt').read_text() for r in 'ABCD'}
  self.cache={r['cache_key']:r for r in rows(self.run/'traces.jsonl')};self.llm=None;self.start=float(os.environ.get("PILOT_ALLOCATION_START",time.time()))
  self.usagepath=ROOT/'runs/budget_ledger.json';self.usage=read(self.usagepath) if self.usagepath.exists() else dict(requests=0,generated_tokens=0,gpu_seconds=0)
  self.base_seconds=self.usage['gpu_seconds'];self.hits=0
 def count(self,x,pretty=False):return len(self.tok.encode(json.dumps(x,ensure_ascii=False,indent=2) if pretty else canon(x),add_special_tokens=False))
 def save_usage(self):
  self.usage['gpu_seconds']=self.base_seconds+time.time()-self.start;write(self.usagepath,self.usage);write(self.run/'resource_usage.json',dict(self.usage,cache_hits=self.hits,job_id=os.environ.get('SLURM_JOB_ID'),pid=os.getpid()))
 def generate(self,requests):
  from vllm import LLM,SamplingParams
  from vllm.sampling_params import StructuredOutputsParams
  results=[None]*len(requests);pending={}
  for i,r in enumerate(requests):
   role=r['role'];visible=r['visible'];messages=[{'role':'system','content':PUBLIC+'\n'+self.prompts[role]},{'role':'user','content':visible}]
   prompt=self.tok.apply_chat_template(messages,tokenize=False,add_generation_prompt=True,enable_thinking=False)
   maxout=self.cfg['max_tokens'][role];plen=len(self.tok.encode(prompt,add_special_tokens=False))
   if plen+maxout>self.cfg['max_model_len']:raise RuntimeError('No truncation permitted: context overflow')
   key=digest(dict(model=self.modelhash,role=role,messages=messages,params=self.cfg,code=self.code))
   if key in self.cache:results[i]=self.cache[key];self.hits+=1
   else:pending.setdefault(key,dict(indices=[],request=r,prompt=prompt,plen=plen,maxout=maxout,messages=messages))['indices'].append(i)
  values=list(pending.items())
  for offset in range(0,len(values),self.cfg['batch_size']):
   batch=values[offset:offset+self.cfg['batch_size']];self.save_usage()
   if self.usage['requests']+len(batch)>self.cfg['max_requests'] or self.usage['generated_tokens']+sum(b['maxout'] for _,b in batch)>self.cfg['max_generated_tokens'] or self.usage['gpu_seconds']>=self.cfg['max_gpu_seconds']-120:raise BudgetStop('budget checkpoint before batch')
   if self.llm is None:
    self.llm=LLM(model=self.cfg['model'],dtype=self.cfg['dtype'],max_model_len=self.cfg['max_model_len'],tensor_parallel_size=1,gpu_memory_utilization=0.3,enforce_eager=True,enable_prefix_caching=True,seed=self.cfg['seed'],max_num_seqs=32,limit_mm_per_prompt={'image':0,'video':0},trust_remote_code=False,attention_backend="TRITON_ATTN",gdn_prefill_backend="triton")
   print("ATTENTION_BACKEND",self.llm.llm_engine.vllm_config.attention_config.backend,flush=True)
   params=[SamplingParams(temperature=0,max_tokens=b['maxout'],seed=41,structured_outputs=StructuredOutputsParams(json=AB if b['request']['role'] in 'AB' else CD)) for _,b in batch]
   start=time.time();self.usage['requests']+=len(batch);self.save_usage()
   try: outputs=self.llm.generate([b['prompt'] for _,b in batch],params,use_tqdm=False)
   except Exception as exc:
    append(self.run/'failures.jsonl',dict(status='infrastructure_failure',time=time.time(),keys=[k for k,_ in batch],error=repr(exc)));raise
   elapsed=time.time()-start
   for (key,b),out in zip(batch,outputs):
    raw=out.outputs[0].text;parsed,error=parse(raw,b['request']['role']);tokens=len(out.outputs[0].token_ids);self.usage['generated_tokens']+=tokens
    t=dict(cache_key=key,dependency_hash=digest(b['messages']),model_hash=self.modelhash,code_hash=self.code,role=b['request']['role'],query_id=b['request']['query_id'],world_id=b['request']['world_id'],condition=b['request']['condition'],split=b['request']['split'],demand=b['request']['demand'],seed=41,visible_input=b['messages'],raw_output=raw,parsed=parsed,parse_error=error,input_tokens=b['plen'],output_tokens=tokens,finish_reason=out.outputs[0].finish_reason,batch_seconds=elapsed,batch_size=len(batch),seconds=elapsed/len(batch),time=time.time(),status='parse_failure' if error else 'ok')
    append(self.run/'traces.jsonl',t);self.cache[key]=t
    for i in b['indices']:results[i]=t
   self.save_usage();print('requests',self.usage['requests'],'tokens',self.usage['generated_tokens'],flush=True)
  return results

def identity():
 import torch,transformers
 cfg=yaml.safe_load((ROOT/'configs/pilot.yaml').read_text());path=Path(cfg['model']);files={}
 for p in sorted(path.iterdir()):
  if p.is_file():
   h=hashlib.sha256()
   with p.open('rb') as f:
    for b in iter(lambda:f.read(16*1024*1024),b''):h.update(b)
   files[p.name]={'bytes':p.stat().st_size,'sha256':h.hexdigest()}
 from transformers import AutoTokenizer
 tok=AutoTokenizer.from_pretrained(path,local_files_only=True)
 x=dict(name=cfg['model_name'],path=str(path),revision=read(ROOT/'configs/model_download.json')['revision'],files=files,file_list_hash=digest(files),tokenizer=type(tok).__name__,chat_template=tok.chat_template,enable_thinking=False,dtype=cfg['dtype'],quantization=None,backend='vllm',versions={n:importlib.metadata.version(n) for n in ['torch','transformers','vllm','scikit-learn','scipy','numpy','matplotlib','jsonschema']})
 write(ROOT/'configs/model_identity.json',x);print('identity',digest(x))
if __name__=='__main__':identity()
