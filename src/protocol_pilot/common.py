import json,hashlib,time,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def canon(x): return json.dumps(x,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def digest(x): return hashlib.sha256((x if isinstance(x,str) else canon(x)).encode()).hexdigest()
def read(p): return json.loads(Path(p).read_text())
def rows(p): return [json.loads(s) for s in Path(p).read_text().splitlines() if s] if Path(p).exists() else []
def write(p,x):
 p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(x,ensure_ascii=False,indent=2))
def append(p,x):
 with open(p,'a') as f: f.write(canon(x)+'\n');f.flush();os.fsync(f.fileno())
def jsonl(p,x): Path(p).write_text(''.join(canon(y)+'\n' for y in x))
def codehash(): return digest({str(p.relative_to(ROOT)):digest(p.read_text()) for p in sorted((ROOT/'src').rglob('*.py'))})
