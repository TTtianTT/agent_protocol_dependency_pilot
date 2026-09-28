from protocol_pilot.common import *
editorial=read(ROOT/'results/report_editorial.json');path=ROOT/'runs/pilot-v1/outcomes.jsonl'
assert digest(path.read_text())==editorial['outcomes_sha256'],'Editorial belongs to different outcomes; do not silently reuse.'
p=ROOT/'REPORT.md';text=p.read_text();text=editorial['intro']+'## 执行与审计'+text.split('## 执行与审计',1)[1];text=text.split('\n## 最终验收与解释边界\n')[0]+editorial['final'];p.write_text(text)
print('Final audited report restored')
