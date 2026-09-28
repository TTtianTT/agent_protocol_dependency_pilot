"""Descriptive tables for the two strata already specified before inference."""
from protocol_pilot.common import rows,read,write,digest
from analyze import HERE,savecsv,bootstrap,table

def main():
 out=rows(HERE/'runs/formal/outcomes.jsonl');summ=[];contr=[];idx={(o['world_id'],o['demand'],o['condition']):o for o in out}
 for stratum in ['unique_names','shared_names']:
  for d in [0,1]:
   for c in sorted({o['condition'] for o in out}):
    rs=[o for o in out if o['stratum']==stratum and o['demand']==d and o['condition']==c]
    summ.append(dict(stratum=stratum,demand=d,condition=c,worlds=len(rs),joint_success=sum(o['metrics']['joint_success_strict'] for o in rs)/len(rs),answer_accuracy=sum(o['metrics']['answer_accuracy'] for o in rs)/len(rs),source_sufficient=sum(o['metrics']['source_evidence_sufficient'] for o in rs)/len(rs)))
  for changed,base in [('original','no_e3'),('swap_answer','original'),('swap_evidence','original'),('natural','original'),('natural_without_answer','natural'),('natural_without_evidence','natural')]:
   rs=[]
   for o in out:
    if o['stratum']==stratum and o['condition']==changed:
     b=idx[o['world_id'],o['demand'],base];rs.append(dict(world_id=o['world_id'],delta=b['metrics']['joint_success_strict']-o['metrics']['joint_success_strict']))
   contr.append(dict(stratum=stratum,changed=changed,base=base,**bootstrap(rs,'delta')))
 savecsv('stratum_condition_metrics.csv',summ);savecsv('stratum_paired_contrasts.csv',contr)
 extra='\n## 两个预定实体命名分层（描述性）\n\n不筛样本；共同模型在同名实体上的基线能力可能限制干扰检验。分层设计在正式前固定，以下区间未作额外多重校正。\n\n'+table([r for r in summ if r['condition'] in ['original','no_e3','swap_answer','swap_evidence','natural']],['stratum','demand','condition','worlds','joint_success','answer_accuracy','source_sufficient'])+'\n\n'+table(contr,['stratum','changed','base','n','worlds','estimate','ci_low','ci_high'])+'\n'
 p=HERE/'REPORT.md';p.write_text(p.read_text().split('\n## 两个预定实体命名分层（描述性）\n')[0]+extra)
 print('STRATIFIED PRESENTATION COMPLETE')
if __name__=='__main__':main()
